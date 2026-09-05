#!/usr/bin/env python3
"""Run only commands selected from an explicit target-owned local registry."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any

# Avoid shadowing the standard-library inspect module when this file is run.
_SCRIPT_DIRECTORY = Path(__file__).absolute().parent
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").absolute() != _SCRIPT_DIRECTORY]

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
MAX_CHECKS = 32
MAX_ARGUMENTS = 64
MAX_ARGUMENT_LENGTH = 1_024
MAX_TEXT = 2_000
MAX_TAGS = 64
MAX_TIMEOUT_SECONDS = 3_600
ALLOWED_EFFECTS = {"read-only", "repository-build-artifacts", "target-declared-external"}


class InspectError(RuntimeError):
    """A registry, plan, path, or selected command violated its boundary."""


def _bootstrap_module(path: Path, *, root: Path) -> types.ModuleType:
    root = root.absolute()
    path = path.absolute()
    try:
        parts = path.relative_to(root).parts
    except ValueError as exc:
        raise InspectError(f"runtime escapes repository root: {path}") from exc
    portable = sys.modules.get("_dev_standard_portable_imports")
    if portable is not None:
        return portable.load_relative(
            "/".join(parts),
            "dev_standard_inspect_safe_io",
        )
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(os.sep, directory_flags)
    try:
        for component in root.parts[1:]:
            next_descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        root_identity = (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino)
        for part in parts[:-1]:
            next_descriptor = os.open(part, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        source_descriptor = os.open(parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
        try:
            if not stat.S_ISREG(os.fstat(source_descriptor).st_mode):
                raise InspectError(f"runtime is not a regular file: {path}")
            chunks: list[bytes] = []
            while chunk := os.read(source_descriptor, 1024 * 1024):
                chunks.append(chunk)
        finally:
            os.close(source_descriptor)
    finally:
        os.close(descriptor)
    module = types.ModuleType("dev_standard_inspect_safe_io")
    module.__file__ = str(path)
    module._bootstrap_root_identity = root_identity
    sys.modules[module.__name__] = module
    exec(compile(b"".join(chunks), str(path), "exec"), module.__dict__)
    return module


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _bounded(label: str, value: Any, *, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise InspectError(f"{label} must be text")
    value = value.strip()
    if not value or len(value) > maximum:
        raise InspectError(f"{label} must contain 1..{maximum} characters")
    return value


def _bounded_ids(label: str, value: Any, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_TAGS:
        raise InspectError(f"{label} must be a bounded array")
    normalized: list[str] = []
    for item in value:
        item = _bounded(f"{label} entry", item, maximum=128)
        if not ID_PATTERN.fullmatch(item):
            raise InspectError(f"{label} entries must be portable identifiers")
        normalized.append(item)
    if len(set(normalized)) != len(normalized):
        raise InspectError(f"{label} entries must be unique")
    if not allow_empty and not normalized:
        raise InspectError(f"{label} may not be empty")
    return normalized


def _repo_path(root: Path, raw: str, *, output: bool = False) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise InspectError("paths must be relative without dot segments")
    path = root.absolute() / candidate
    if output and (len(candidate.parts) <= 2 or candidate.parts[:2] != (".devflow", "run")):
        raise InspectError("result output must be below .devflow/run")
    return path


def _load_object(
    path: Path,
    *,
    root: Path,
    safe_io: types.ModuleType,
    root_fd: int,
    label: str,
) -> tuple[dict[str, Any], Any]:
    before = safe_io.snapshot_file_pinned(path, root=root, root_fd=root_fd)
    if not before.exists:
        raise InspectError(f"{label} does not exist")
    try:
        value = json.loads(safe_io.read_bytes_nofollow_pinned(path, root=root, root_fd=root_fd))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InspectError(f"{label} must be valid UTF-8 JSON") from exc
    if safe_io.snapshot_file_pinned(path, root=root, root_fd=root_fd) != before:
        raise InspectError(f"{label} changed while reading")
    if not isinstance(value, dict):
        raise InspectError(f"{label} must be an object")
    return value, before


def _load_registry(
    path: Path,
    *,
    root: Path,
    safe_io: types.ModuleType,
    root_fd: int,
) -> tuple[dict[str, dict[str, Any]], str, Any]:
    value, snapshot = _load_object(path, root=root, safe_io=safe_io, root_fd=root_fd, label="registry")
    if set(value) != {"schema_version", "checks"} or value["schema_version"] != 1:
        raise InspectError("registry must contain exactly schema_version=1 and checks")
    checks = value["checks"]
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS:
        raise InspectError(f"registry must contain 1..{MAX_CHECKS} checks")
    registry: dict[str, dict[str, Any]] = {}
    fields = {"command_id", "command", "acceptance_ids", "risk_tags", "effect", "authority", "authority_reference", "output_roots"}
    for item in checks:
        if not isinstance(item, dict) or set(item) != fields:
            raise InspectError("registry check fields must be exact")
        command_id = _bounded("command_id", item["command_id"], maximum=128)
        if not ID_PATTERN.fullmatch(command_id) or command_id in registry:
            raise InspectError("command_id must be a unique portable identifier")
        command = item["command"]
        if (
            not isinstance(command, list)
            or not 1 <= len(command) <= MAX_ARGUMENTS
            or any(not isinstance(argument, str) or not argument or len(argument) > MAX_ARGUMENT_LENGTH for argument in command)
        ):
            raise InspectError(f"{command_id}: command must be a bounded non-empty argv array")
        acceptance = _bounded_ids(f"{command_id} acceptance_ids", item["acceptance_ids"])
        risks = _bounded_ids(f"{command_id} risk_tags", item["risk_tags"])
        if not acceptance and not risks:
            raise InspectError(f"{command_id}: acceptance_ids and risk_tags may not both be empty")
        if item["effect"] not in ALLOWED_EFFECTS:
            raise InspectError(f"{command_id}: irreversible or undeclared effects are forbidden")
        if item["authority"] != "target-repository":
            raise InspectError(f"{command_id}: authority must be target-repository")
        authority_reference = item["authority_reference"]
        if item["effect"] == "target-declared-external":
            authority_reference = _bounded(f"{command_id} authority_reference", authority_reference, maximum=512)
        elif authority_reference is not None:
            raise InspectError(f"{command_id}: local effects must use authority_reference=null")
        output_roots = item["output_roots"]
        if not isinstance(output_roots, list) or len(output_roots) > 16:
            raise InspectError(f"{command_id}: output_roots must be a bounded array")
        normalized_roots: list[str] = []
        for raw_output in output_roots:
            raw_output = _bounded(f"{command_id} output root", raw_output, maximum=256)
            candidate = Path(raw_output)
            if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
                raise InspectError(f"{command_id}: output roots must be relative without dot segments")
            normalized = candidate.as_posix().rstrip("/")
            if normalized == ".git" or normalized.startswith(".git/") or normalized == ".devflow" or normalized.startswith(".devflow/"):
                raise InspectError(f"{command_id}: output roots may not hide repository control or runner state")
            normalized_roots.append(normalized)
        if len(set(normalized_roots)) != len(normalized_roots):
            raise InspectError(f"{command_id}: output roots must be unique")
        if item["effect"] == "repository-build-artifacts" and not normalized_roots:
            raise InspectError(f"{command_id}: build-artifact effects require explicit output_roots")
        if item["effect"] != "repository-build-artifacts" and normalized_roots:
            raise InspectError(f"{command_id}: only build-artifact effects may declare output_roots")
        registry[command_id] = {
            "command_id": command_id,
            "command": list(command),
            "acceptance_ids": acceptance,
            "risk_tags": risks,
            "effect": item["effect"],
            "authority": item["authority"],
            "authority_reference": authority_reference,
            "output_roots": normalized_roots,
        }
    return registry, _digest(value), snapshot


def _load_plan(
    path: Path,
    *,
    root: Path,
    safe_io: types.ModuleType,
    root_fd: int,
    registry: dict[str, dict[str, Any]],
) -> tuple[str, list[str], str | None, list[dict[str, Any]], str, Any]:
    value, snapshot = _load_object(path, root=root, safe_io=safe_io, root_fd=root_fd, label="plan")
    if set(value) != {"schema_version", "scope", "residual_risks", "no_applicable_reason", "checks"} or value["schema_version"] != 1:
        raise InspectError("plan fields must be exactly schema_version=1, scope, residual_risks, no_applicable_reason, checks")
    scope = _bounded("scope", value["scope"])
    residual = _bounded_ids("residual_risks", value["residual_risks"])
    checks = value["checks"]
    if not isinstance(checks, list) or len(checks) > MAX_CHECKS:
        raise InspectError(f"plan must select 0..{MAX_CHECKS} checks")
    no_applicable_reason = value["no_applicable_reason"]
    if checks and no_applicable_reason is not None:
        raise InspectError("no_applicable_reason must be null when checks are selected")
    if not checks:
        no_applicable_reason = _bounded("no_applicable_reason", no_applicable_reason)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    required = {"command_id", "acceptance_ids", "risk_tags"}
    allowed = {*required, "timeout_seconds"}
    for item in checks:
        if not isinstance(item, dict) or not required <= set(item) <= allowed:
            raise InspectError("plan checks may contain only command_id, acceptance_ids, risk_tags, and timeout_seconds")
        command_id = item["command_id"]
        if not isinstance(command_id, str) or command_id not in registry or command_id in seen:
            raise InspectError("plan command_id must be unique and present in the target-owned registry")
        acceptance = _bounded_ids(f"{command_id} acceptance_ids", item["acceptance_ids"])
        risks = _bounded_ids(f"{command_id} risk_tags", item["risk_tags"])
        if not acceptance and not risks:
            raise InspectError(f"{command_id}: plan relevance may not be empty")
        registered = registry[command_id]
        if not set(acceptance).issubset(registered["acceptance_ids"]) or not set(risks).issubset(registered["risk_tags"]):
            raise InspectError(f"{command_id}: plan relevance exceeds the registry")
        timeout = item.get("timeout_seconds", 300)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
            raise InspectError(f"{command_id}: timeout_seconds must be 1..{MAX_TIMEOUT_SECONDS}")
        normalized.append({**registered, "acceptance_ids": acceptance, "risk_tags": risks, "timeout_seconds": timeout})
        seen.add(command_id)
    return scope, residual, no_applicable_reason, normalized, _digest(value), snapshot


def _inventory(root: Path, safe_io: types.ModuleType, root_fd: int, output_roots: list[str]) -> str:
    excluded = frozenset({".git", ".devflow/run", *output_roots})
    return safe_io.tree_digest_nofollow_pinned(root, root=root, root_fd=root_fd, exclude=excluded)


def _pinned_cwd(root: Path, root_fd: int) -> str:
    proc_path = f"/proc/self/fd/{root_fd}"
    return proc_path if os.name == "posix" and Path(proc_path).exists() else str(root)


def _resolve_executable(command: list[str], *, root: Path) -> list[str]:
    executable = command[0]
    if os.sep in executable:
        candidate = Path(executable)
        if candidate.is_absolute():
            resolved = str(candidate)
        else:
            _repo_path(root, executable)  # lexical confinement check; cwd is the pinned root FD.
            resolved = executable
    else:
        resolved = shutil.which(executable, path=os.defpath)
        if resolved is None:
            raise InspectError(f"registered executable was not found on the fixed system path: {executable}")
    return [resolved, *command[1:]]


def _executable_identity(descriptor: int) -> dict[str, Any]:
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        raise InspectError("registered executable must resolve to a regular file")
    if not info.st_mode & 0o111:
        raise InspectError("registered executable is not executable")
    digest = hashlib.sha256()
    offset = 0
    while True:
        if hasattr(os, "pread"):
            chunk = os.pread(descriptor, 1024 * 1024, offset)
        else:  # pragma: no cover - exercised on platforms without pread.
            os.lseek(descriptor, offset, os.SEEK_SET)
            chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        offset += len(chunk)
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "mode": stat.S_IMODE(info.st_mode),
        "size": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


@contextlib.contextmanager
def _pinned_executable(
    command: list[str],
    *,
    root: Path,
    root_fd: int,
    safe_io: types.ModuleType,
) -> Any:
    resolved_command = _resolve_executable(command, root=root)
    resolved = Path(resolved_command[0])
    manager: Any
    if os.sep in command[0] and not Path(command[0]).is_absolute():
        manager = safe_io.open_file_nofollow_pinned(
            _repo_path(root, command[0]),
            root=root,
            root_fd=root_fd,
        )
    else:
        try:
            final = resolved.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise InspectError(f"registered executable cannot be resolved: {command[0]}") from exc

        @contextlib.contextmanager
        def open_external() -> Any:
            descriptor = os.open(final, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                yield descriptor
            finally:
                os.close(descriptor)

        manager = open_external()
    with manager as descriptor:
        identity = _executable_identity(descriptor)
        proc_path = f"/proc/self/fd/{descriptor}"
        pinned = os.name == "posix" and Path(proc_path).exists()
        yield {
            "descriptor": descriptor,
            "launch_path": proc_path if pinned else resolved_command[0],
            "pinned": pinned,
            "requested": command[0],
            "resolved": resolved_command[0],
            "identity": identity,
            "command": resolved_command,
        }


def _kill_group(process: subprocess.Popen[bytes], *, force: bool) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:  # pragma: no cover - exercised on Windows.
        process.kill() if force else process.terminate()


def _group_exists(process: subprocess.Popen[bytes]) -> bool:
    if os.name != "posix":  # pragma: no cover - exercised on Windows.
        return process.poll() is None
    try:
        os.killpg(process.pid, 0)
        return True
    except ProcessLookupError:
        return False


def _drain_group(process: subprocess.Popen[bytes]) -> bool:
    _kill_group(process, force=False)
    deadline = time.monotonic() + 0.5
    while _group_exists(process) and time.monotonic() < deadline:
        time.sleep(0.02)
    if _group_exists(process):
        _kill_group(process, force=True)
        deadline = time.monotonic() + 1.0
        while _group_exists(process) and time.monotonic() < deadline:
            time.sleep(0.02)
    return not _group_exists(process)


def _run_check(
    check: dict[str, Any],
    *,
    root: Path,
    root_fd: int,
    scope: str,
    safe_io: types.ModuleType,
) -> dict[str, Any]:
    before = _inventory(root, safe_io, root_fd, check["output_roots"])
    started = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    descendants_drained = True
    executable_record: dict[str, Any] | None = None
    executable_identity_stable: bool | None = None
    try:
        with _pinned_executable(
            check["command"],
            root=root,
            root_fd=root_fd,
            safe_io=safe_io,
        ) as executable:
            executable_record = {
                "requested": executable["requested"],
                "resolved": executable["resolved"],
                "fd_pinned": executable["pinned"],
                "identity": executable["identity"],
            }
            popen_options: dict[str, Any] = {"executable": executable["launch_path"]}
            if os.name == "posix":
                popen_options["pass_fds"] = (root_fd, executable["descriptor"])
            process = subprocess.Popen(
                executable["command"],
                cwd=_pinned_cwd(root, root_fd),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
                **popen_options,
            )
            try:
                exit_code = process.wait(timeout=check["timeout_seconds"])
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(process, force=False)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    _kill_group(process, force=True)
                    process.wait(timeout=2)
            finally:
                descendants_drained = _drain_group(process)
            executable_identity_stable = _executable_identity(executable["descriptor"]) == executable["identity"]
    except (InspectError, OSError):
        exit_code = None
    duration = round(time.monotonic() - started, 3)
    source_changed = _inventory(root, safe_io, root_fd, check["output_roots"]) != before
    status = "pass"
    if timed_out:
        status = "timeout"
    elif exit_code != 0:
        status = "fail" if exit_code is not None else "cannot-start"
    if source_changed:
        status = "declaration-violation"
    if not descendants_drained:
        status = "cleanup-failed"
    if executable_identity_stable is False:
        status = "executable-identity-changed"
    return {
        "command_id": check["command_id"],
        "scope": scope,
        "relevance": {"acceptance_ids": check["acceptance_ids"], "risk_tags": check["risk_tags"]},
        "effect": check["effect"],
        "authority": check["authority"],
        "authority_reference": check["authority_reference"],
        "declared_output_roots": check["output_roots"],
        "status": status,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_seconds": duration,
        "source_mutation_detected": source_changed,
        "repository_mutation_outside_declared_outputs_detected": source_changed,
        "process_effect_isolated": False,
        "process_effect_detection": "not-provided",
        "executable": executable_record,
        "executable_identity_stable": executable_identity_stable,
        "descendants_drained": descendants_drained,
    }


def _write_result(
    path: Path,
    result: dict[str, Any],
    *,
    root: Path,
    safe_io: types.ModuleType,
    root_fd: int,
    read_preconditions: dict[Path, Any],
) -> None:
    before = safe_io.snapshot_file_pinned(path, root=root, root_fd=root_fd)
    if before.exists:
        raise InspectError("result output already exists")
    safe_io.atomic_batch_write_cas(
        {path: json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"},
        {path: before},
        root=root,
        lock_name=".devflow/run/selected-check.lock",
        pinned_root_fd=root_fd,
        read_preconditions=read_preconditions,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--registry", required=True, help="target-owned repository-confined registry JSON")
    parser.add_argument("--plan", required=True, help="repository-confined selected-check plan JSON")
    parser.add_argument("--json-out", help="optional .devflow/run result summary JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).absolute()
    try:
        safe_io = _bootstrap_module(root / "tools" / "safe_io.py", root=root)
        with safe_io.trusted_root(root) as root_fd:
            identity = (os.fstat(root_fd).st_dev, os.fstat(root_fd).st_ino)
            if identity != safe_io._bootstrap_root_identity:
                raise InspectError("repository root changed after runtime bootstrap")
            registry_path = _repo_path(root, args.registry)
            plan_path = _repo_path(root, args.plan)
            registry, registry_digest, registry_snapshot = _load_registry(
                registry_path,
                root=root,
                safe_io=safe_io,
                root_fd=root_fd,
            )
            scope, declared_residual, no_applicable_reason, checks, plan_digest, plan_snapshot = _load_plan(
                plan_path,
                root=root,
                safe_io=safe_io,
                root_fd=root_fd,
                registry=registry,
            )
            results = [_run_check(check, root=root, root_fd=root_fd, scope=scope, safe_io=safe_io) for check in checks]
            input_snapshots = {registry_path: registry_snapshot, plan_path: plan_snapshot}
            if any(
                safe_io.snapshot_file_pinned(path, root=root, root_fd=root_fd) != snapshot
                for path, snapshot in input_snapshots.items()
            ):
                raise InspectError("registry or plan changed after selection")
            failed = [item["command_id"] for item in results if item["status"] != "pass"]
            covered = sorted({acceptance for item in results if item["status"] == "pass" for acceptance in item["relevance"]["acceptance_ids"]})
            residual = set(declared_residual).union(risk for item in results if item["status"] != "pass" for risk in item["relevance"]["risk_tags"])
            residual.update(f"process-effect-not-isolated:{item['command_id']}" for item in results)
            status = "skipped" if not checks else ("pass" if not failed else "fail")
            result = {
                "schema_version": 2,
                "registry_digest": registry_digest,
                "plan_digest": plan_digest,
                "scope": scope,
                "selected_count": len(results),
                "status": status,
                "no_applicable_reason": no_applicable_reason,
                "covered_acceptance": covered,
                "residual_risk": sorted(residual),
                "results": results,
                "raw_output_persisted": False,
                "process_effect_isolation_provided": False,
                "process_effect_detection_provided": False,
                "unselected_claim": False,
                "repair_handoff": None
                if not failed
                else {
                    "failed_command_ids": failed,
                    "instruction": "repair under an authorized implementation Skill, then rerun only affected registered commands",
                },
            }
            if args.json_out:
                _write_result(
                    _repo_path(root, args.json_out, output=True),
                    result,
                    root=root,
                    safe_io=safe_io,
                    root_fd=root_fd,
                    read_preconditions=input_snapshots,
                )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if not failed else 1
    except Exception as exc:  # CLI boundary: dynamic safe-I/O errors become bounded rejections.
        print(json.dumps({"error": str(exc), "status": "rejected"}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
