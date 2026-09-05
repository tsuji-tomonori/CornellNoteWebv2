#!/usr/bin/env python3
"""Run an installed repository's Quint contracts with a pinned local runtime.

The installer commitment is checked before any command. Quint is installed
from the distributed lockfile into an immutable version directory; repository
``node_modules`` and ambient Quint binaries are never used.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


class PortableQuintError(RuntimeError):
    """A portable runtime, installation, or formal contract was refused."""


def _lexical_script() -> Path:
    return Path(os.path.abspath(__file__))


def _open_absolute_directory(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise PortableQuintError(f"pinned directory path is not absolute and lexical: {path}")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current = os.open(os.sep, flags)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = next_fd
        return current
    except BaseException:
        os.close(current)
        raise


def _load_pinned_tool(name: str) -> types.ModuleType:
    """Load one exact sibling module through a pinned repository-root FD."""

    if not name.isidentifier():
        raise PortableQuintError(f"invalid pinned tool name: {name!r}")
    script = _lexical_script()
    root = script.parent.parent
    descriptors: list[int] = []
    try:
        root_fd = _open_absolute_directory(root)
        descriptors.append(root_fd)
        tools_fd = os.open(
            "tools",
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
        descriptors.append(tools_fd)
        source_fd = os.open(
            f"{name}.py",
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=tools_fd,
        )
        descriptors.append(source_fd)
        if not stat.S_ISREG(os.fstat(source_fd).st_mode):
            raise PortableQuintError(f"tools/{name}.py is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(source_fd, 1024 * 1024):
            chunks.append(chunk)
    except OSError as exc:
        raise PortableQuintError(f"cannot load pinned tools/{name}.py: {exc}") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    module_name = f"_dev_standard_portable_{name}"
    module = types.ModuleType(module_name)
    module.__file__ = str(root / "tools" / f"{name}.py")
    module.__package__ = ""
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(compile(b"".join(chunks), module.__file__, "exec"), module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


# These literal calls are the source of truth for the installer's automatically
# derived local import closure. Do not replace them with ambient imports.
safe_io = _load_pinned_tool("safe_io")
spec_mapping = _load_pinned_tool("spec_mapping")
render_requirements = _load_pinned_tool("render_requirements")
render_skills = _load_pinned_tool("render_skills")

ROOT = _lexical_script().parent.parent
QUINT_VERSION = "0.32.0"
RUNTIME_SOURCE = ROOT / ".dev-standard/quint/source"
RUNTIME_PARENT = ROOT / ".dev-standard/quint/runtime"
RUNTIME = RUNTIME_PARENT / QUINT_VERSION
RUNTIME_MARKER = ".dev-standard-runtime.json"
QUINT_CLI_RELATIVE = Path("node_modules/@informalsystems/quint/dist/src/cli.js")
REQUIREMENTS_QNT = ROOT / "spec/requirements/requirements.qnt"
REQUIREMENTS_JSON = ROOT / "spec/requirements/requirements.json"
REQUIREMENTS_DOC = ROOT / "docs/requirements/REQUIREMENTS.md"
SKILLS_QNT = ROOT / "spec/skills/skills.qnt"
SKILLS_JSON = ROOT / "spec/skills/skills.json"
COMMITMENT = ROOT / ".dev-standard/install/commitment.json"
RECEIPT = ROOT / ".dev-standard/install/receipt.json"
REQUIREMENT_INVARIANTS = ["catalogWellFormed", "lifecycleRefinesCatalog"]
SKILL_INVARIANTS = [
    "formalContractsHold",
    "workflowOrderIsConsistent",
    "portablePolicyIsUntouched",
]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _read_json_nofollow(path: Path, *, root_fd: int | None = None) -> Any:
    try:
        content = (
            safe_io.read_bytes_nofollow_pinned(path, root=ROOT, root_fd=root_fd)
            if root_fd is not None
            else safe_io.read_bytes_nofollow(path, root=ROOT)
        )
        return json.loads(content.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, safe_io.SafeIOError) as exc:
        with contextlib.suppress(ValueError):
            path = path.relative_to(ROOT)
        raise PortableQuintError(f"cannot read {path}: {exc}") from exc


def _receipt(*, root_fd: int | None = None) -> dict[str, Any]:
    """Verify commitment -> receipt -> asset bytes, then return the receipt."""

    @contextlib.contextmanager
    def root_descriptor() -> Any:
        if root_fd is None:
            with safe_io.trusted_root(ROOT) as descriptor:
                yield descriptor
        else:
            descriptor = os.dup(root_fd)
            try:
                yield descriptor
            finally:
                os.close(descriptor)

    with root_descriptor() as descriptor:
        try:
            commitment_bytes = safe_io.read_bytes_nofollow_pinned(
                COMMITMENT, root=ROOT, root_fd=descriptor
            )
            receipt_bytes = safe_io.read_bytes_nofollow_pinned(
                RECEIPT, root=ROOT, root_fd=descriptor
            )
            commitment = json.loads(commitment_bytes)
            receipt = json.loads(receipt_bytes)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, safe_io.SafeIOError) as exc:
            raise PortableQuintError(f"installer commitment is missing or invalid: {exc}") from exc
        if not isinstance(commitment, dict) or set(commitment) != {
            "schema_version",
            "managed_by",
            "receipt",
            "receipt_sha256",
            "assets_sha256",
        }:
            raise PortableQuintError("installer commitment schema is invalid")
        if (
            commitment.get("schema_version") != 2
            or commitment.get("managed_by") != "dev-standard-reference-installer"
            or commitment.get("receipt") != ".dev-standard/install/receipt.json"
            or commitment.get("receipt_sha256") != hashlib.sha256(receipt_bytes).hexdigest()
        ):
            raise PortableQuintError("installer commitment does not bind the receipt")
        expected_receipt_fields = {
            "schema_version",
            "managed_by",
            "host",
            "interface_policy",
            "profiles",
            "skills",
            "quint_version",
            "assets",
        }
        if not isinstance(receipt, dict) or set(receipt) != expected_receipt_fields:
            raise PortableQuintError("installer receipt schema is invalid")
        expected_policy = {"codex": "required", "claude-code": "canonical-omitted"}
        host = receipt.get("host")
        if (
            receipt.get("schema_version") != 2
            or receipt.get("managed_by") != "dev-standard-reference-installer"
            or not isinstance(host, str)
            or host not in expected_policy
            or receipt.get("interface_policy") != expected_policy.get(host)
        ):
            raise PortableQuintError("installer receipt identity is invalid")
        profiles = receipt.get("profiles")
        skills = receipt.get("skills")
        if (
            not isinstance(profiles, list)
            or not all(isinstance(value, str) for value in profiles)
            or profiles != sorted(set(profiles))
            or not isinstance(skills, list)
            or not all(isinstance(value, str) for value in skills)
            or skills != sorted(set(skills))
        ):
            raise PortableQuintError("installer receipt profile or Skill subset is invalid")
        if receipt.get("quint_version") != QUINT_VERSION:
            raise PortableQuintError("this profile has no matching portable Quint runtime")
        assets = receipt.get("assets")
        if not isinstance(assets, list):
            raise PortableQuintError("installer receipt assets are invalid")
        canonical_assets = json.dumps(
            assets, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ) + "\n"
        if commitment.get("assets_sha256") != hashlib.sha256(canonical_assets.encode()).hexdigest():
            raise PortableQuintError("installer commitment does not bind its asset inventory")
        seen: set[str] = set()
        ordered_paths: list[str] = []
        for entry in assets:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
                raise PortableQuintError("installer asset entry is invalid")
            relative = entry.get("path")
            digest = entry.get("sha256")
            pure = PurePosixPath(relative) if isinstance(relative, str) else PurePosixPath("/")
            if (
                not isinstance(relative, str)
                or relative in seen
                or pure.is_absolute()
                or any(part in {"", ".", ".."} for part in pure.parts)
                or not isinstance(digest, str)
                or not all(character in "0123456789abcdef" for character in digest)
                or len(digest) != 64
            ):
                raise PortableQuintError("installer asset path or digest is invalid")
            seen.add(relative)
            path = ROOT.joinpath(*pure.parts)
            try:
                content = safe_io.read_bytes_nofollow_pinned(
                    path, root=ROOT, root_fd=descriptor
                )
            except (OSError, safe_io.SafeIOError) as exc:
                raise PortableQuintError(f"installed asset is missing or unsafe: {relative}: {exc}") from exc
            if hashlib.sha256(content).hexdigest() != digest:
                raise PortableQuintError(f"installed asset digest drift: {relative}")
            ordered_paths.append(relative)
        if ordered_paths != sorted(ordered_paths):
            raise PortableQuintError("installer asset inventory is not canonical")
        return receipt


def _skill_root(receipt: dict[str, Any]) -> Path:
    return ROOT / (".agents/skills" if receipt["host"] == "codex" else ".claude/skills")


def _requirements_template(receipt: dict[str, Any]) -> Path:
    return (
        _skill_root(receipt)
        / "maintain-canonical-requirements/assets/requirements.template.qnt"
    )


def _verify_installed_skills(receipt: dict[str, Any]) -> None:
    try:
        catalog = _read_json_nofollow(SKILLS_JSON)
        render_skills.validate_contract_catalog(catalog["contracts"])
        contracts = {item["name"]: item for item in catalog["contracts"]}
    except (KeyError, TypeError, ValueError) as exc:
        raise PortableQuintError(f"generated Skill contract view is invalid: {exc}") from exc
    selected = receipt.get("skills")
    if not isinstance(selected, list) or selected != sorted(set(selected)):
        raise PortableQuintError("receipt Skill subset is invalid")
    unknown = set(selected) - set(contracts)
    if unknown:
        raise PortableQuintError(f"receipt selects unknown Skills: {sorted(unknown)}")
    root = _skill_root(receipt)
    policy_errors: list[str] = []
    for name in selected:
        skill = root / name
        try:
            safe_io.validate_tree_nofollow(skill, root=ROOT)
            manual_path = skill / "SKILL.md"
            manual = safe_io.read_bytes_nofollow(manual_path, root=ROOT).decode("utf-8")
            contract = contracts[name]
            actual = {
                "manualBodySha256": render_skills.manual_body_sha256(manual),
                "payloadSha256": render_skills.payload_sha256(contract, skill),
            }
            interface = skill / "agents/openai.yaml"
            if receipt["interface_policy"] == "required":
                actual["interfaceSha256"] = render_skills.interface_sha256(skill)
            elif safe_io.snapshot_file(interface, root=ROOT).exists:
                raise PortableQuintError(f"{name}: host adapter must omit agents/openai.yaml")
            mismatches = {
                key: {"contract": contract.get(key), "actual": value}
                for key, value in actual.items()
                if contract.get(key) != value
            }
            if mismatches:
                raise PortableQuintError(f"{name}: Skill binding drift: {mismatches}")
            if render_skills.render_skill_manual(manual, contract) != manual:
                raise PortableQuintError(f"{name}: generated Quint contract block drift")
            policy_errors.extend(render_skills.validate_skill_tree(skill))
        except (OSError, UnicodeDecodeError, ValueError, safe_io.SafeIOError) as exc:
            raise PortableQuintError(f"{name}: installed Skill is invalid: {exc}") from exc
    if policy_errors:
        raise PortableQuintError("installed Skill repository-policy violation:\n" + "\n".join(policy_errors))


def _runtime_digest(path: Path, root_fd: int) -> str:
    return safe_io.tree_digest_nofollow_pinned(
        path, root=ROOT, root_fd=root_fd, exclude=frozenset({RUNTIME_MARKER})
    )


def validate_runtime(path: Path | None = None, *, root_fd: int | None = None) -> Path:
    """Validate version, digest, and every filesystem entry in the runtime."""

    path = path or RUNTIME

    @contextlib.contextmanager
    def root_descriptor() -> Any:
        if root_fd is None:
            with safe_io.trusted_root(ROOT) as descriptor:
                yield descriptor
        else:
            descriptor = os.dup(root_fd)
            try:
                yield descriptor
            finally:
                os.close(descriptor)

    with root_descriptor() as descriptor:
        try:
            marker = _read_json_nofollow(path / RUNTIME_MARKER, root_fd=descriptor)
            package = _read_json_nofollow(
                path / "node_modules/@informalsystems/quint/package.json", root_fd=descriptor
            )
            cli = path / QUINT_CLI_RELATIVE
            safe_io.read_bytes_nofollow_pinned(cli, root=ROOT, root_fd=descriptor)
        except (FileNotFoundError, NotADirectoryError, safe_io.SafeIOError) as exc:
            raise PortableQuintError(f"pinned Quint runtime is missing or unsafe: {exc}") from exc
        if not isinstance(marker, dict) or set(marker) != {
            "schema_version",
            "quint_version",
            "tree_sha256",
        }:
            raise PortableQuintError("pinned Quint runtime marker is invalid")
        if marker["schema_version"] != 1 or marker["quint_version"] != QUINT_VERSION:
            raise PortableQuintError("pinned Quint runtime version marker is invalid")
        if package.get("name") != "@informalsystems/quint" or package.get("version") != QUINT_VERSION:
            raise PortableQuintError("pinned Quint package version does not match")
        if marker["tree_sha256"] != _runtime_digest(path, descriptor):
            raise PortableQuintError("pinned Quint runtime content digest does not match")
        return cli


def _command_path(name: str, variable: str) -> Path:
    explicit = os.environ.get(variable)
    if explicit and not Path(explicit).is_absolute():
        raise PortableQuintError(f"{variable} must be an absolute path")
    discovered = explicit or shutil.which(name)
    if not discovered:
        raise PortableQuintError(f"{name} is unavailable; install it outside the target repository")
    try:
        # Resolve a packaging symlink once, then pin and execute the real file FD.
        return Path(discovered).resolve(strict=True)
    except OSError as exc:
        raise PortableQuintError(f"{name} is unavailable: {exc}") from exc


@contextlib.contextmanager
def _pinned_command(path: Path) -> Any:
    parent_fd = _open_absolute_directory(path.parent)
    try:
        descriptor = os.open(path.name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
            raise PortableQuintError(f"command is not a regular executable: {path}")
        if sys.platform.startswith("linux"):
            yield descriptor, f"/proc/self/fd/{descriptor}"
        elif sys.platform == "darwin":
            yield descriptor, f"/dev/fd/{descriptor}"
        else:  # pragma: no cover
            raise PortableQuintError("pinned command execution is unsupported on this platform")
    finally:
        os.close(descriptor)


def _npm_install(candidate_fd: int) -> None:
    npm = _command_path("npm", "DEV_STANDARD_NPM_BIN")
    with _pinned_command(npm) as (npm_fd, npm_command):
        cwd = f"/proc/self/fd/{candidate_fd}" if sys.platform.startswith("linux") else f"/dev/fd/{candidate_fd}"
        result = subprocess.run(
            [npm_command, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=cwd,
            pass_fds=(candidate_fd, npm_fd),
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode:
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        raise PortableQuintError(f"isolated Quint setup failed ({result.returncode}): {output}")


def setup() -> bool:
    """Install the exact lockfile runtime in an isolated, no-follow stage."""

    _receipt()
    with safe_io.trusted_root(ROOT) as root_fd:
        package_json = safe_io.read_bytes_nofollow_pinned(
            RUNTIME_SOURCE / "package.json", root=ROOT, root_fd=root_fd
        )
        package_lock = safe_io.read_bytes_nofollow_pinned(
            RUNTIME_SOURCE / "package-lock.json", root=ROOT, root_fd=root_fd
        )
        try:
            package = json.loads(package_json)
            lock = json.loads(package_lock)
        except json.JSONDecodeError as exc:
            raise PortableQuintError(f"pinned npm metadata is invalid: {exc}") from exc
        if (
            package.get("devDependencies", {}).get("@informalsystems/quint") != QUINT_VERSION
            or lock.get("packages", {}).get("node_modules/@informalsystems/quint", {}).get("version")
            != QUINT_VERSION
        ):
            raise PortableQuintError("pinned npm metadata does not select Quint 0.32.0 exactly")

        with safe_io.locked_repository_pinned(
            ROOT, root_fd, ".dev-standard/quint/runtime/.setup.lock"
        ):
            try:
                validate_runtime(root_fd=root_fd)
                print(f"Quint {QUINT_VERSION} runtime already installed")
                return False
            except PortableQuintError:
                try:
                    with safe_io.directory_nofollow_pinned(RUNTIME, root=ROOT, root_fd=root_fd):
                        raise PortableQuintError(
                            "existing pinned runtime is invalid; review and remove that exact directory"
                        )
                except FileNotFoundError:
                    pass

            with safe_io.directory_nofollow_pinned(
                RUNTIME_PARENT, root=ROOT, root_fd=root_fd, create=True
            ) as parent_fd:
                candidate_name = f".{QUINT_VERSION}.stage-{uuid.uuid4().hex}"
                os.mkdir(candidate_name, mode=0o700, dir_fd=parent_fd)
            candidate = RUNTIME_PARENT / candidate_name
            try:
                updates = {
                    candidate / "package.json": package_json,
                    candidate / "package-lock.json": package_lock,
                }
                safe_io.atomic_batch_write_cas(
                    updates,
                    {path: safe_io.MISSING for path in updates},
                    root=ROOT,
                    lock_name=".dev-standard/quint/runtime/.stage-write.lock",
                    pinned_root_fd=root_fd,
                )
                with safe_io.directory_nofollow_pinned(
                    candidate, root=ROOT, root_fd=root_fd
                ) as candidate_fd:
                    _npm_install(candidate_fd)
                safe_io.remove_named_entries_nofollow(
                    candidate,
                    root=ROOT,
                    names=frozenset({".bin"}),
                    pinned_root_fd=root_fd,
                )
                installed = _read_json_nofollow(
                    candidate / "node_modules/@informalsystems/quint/package.json",
                    root_fd=root_fd,
                )
                if installed.get("name") != "@informalsystems/quint" or installed.get("version") != QUINT_VERSION:
                    raise PortableQuintError("isolated npm stage installed an unexpected Quint package")
                marker_path = candidate / RUNTIME_MARKER
                marker = _canonical_json(
                    {
                        "schema_version": 1,
                        "quint_version": QUINT_VERSION,
                        "tree_sha256": _runtime_digest(candidate, root_fd),
                    }
                ).encode()
                safe_io.atomic_batch_write_cas(
                    {marker_path: marker},
                    {marker_path: safe_io.MISSING},
                    root=ROOT,
                    lock_name=".dev-standard/quint/runtime/.stage-write.lock",
                    pinned_root_fd=root_fd,
                )
                safe_io.atomic_publish_directory_noreplace(
                    candidate, RUNTIME, root=ROOT, pinned_root_fd=root_fd
                )
                validate_runtime(root_fd=root_fd)
                print(f"installed Quint {QUINT_VERSION} runtime")
                return True
            finally:
                safe_io.remove_tree_nofollow(
                    candidate, root=ROOT, pinned_root_fd=root_fd
                )


def run_quint(
    *arguments: str,
    capture: bool = False,
    pinned_inputs: tuple[Path, ...] = (),
    root_fd: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run pinned Node and Quint CLI files through open descriptors."""

    _receipt(root_fd=root_fd)
    node = _command_path("node", "DEV_STANDARD_NODE_BIN")

    @contextlib.contextmanager
    def root_descriptor() -> Any:
        if root_fd is None:
            with safe_io.trusted_root(ROOT) as descriptor:
                yield descriptor
        else:
            descriptor = os.dup(root_fd)
            try:
                yield descriptor
            finally:
                os.close(descriptor)

    with root_descriptor() as descriptor:
        cli = validate_runtime(root_fd=descriptor)
        with contextlib.ExitStack() as stack:
            node_fd, node_command = stack.enter_context(_pinned_command(node))
            cli_fd = stack.enter_context(
                safe_io.open_file_nofollow_pinned(cli, root=ROOT, root_fd=descriptor)
            )
            cli_command = f"/proc/self/fd/{cli_fd}" if sys.platform.startswith("linux") else f"/dev/fd/{cli_fd}"
            cwd = (
                f"/proc/self/fd/{descriptor}"
                if sys.platform.startswith("linux")
                else f"/dev/fd/{descriptor}"
            )
            descriptors = [descriptor, node_fd, cli_fd]
            replacements: dict[str, str] = {}
            for path in pinned_inputs:
                source_fd = stack.enter_context(
                    safe_io.open_file_nofollow_pinned(
                        path, root=ROOT, root_fd=descriptor
                    )
                )
                content, _ = safe_io._read_open_file(source_fd)
                immutable = stack.enter_context(tempfile.TemporaryFile())
                immutable.write(content)
                immutable.flush()
                os.fsync(immutable.fileno())
                immutable.seek(0)
                descriptor = immutable.fileno()
                descriptors.append(descriptor)
                replacements[str(path.relative_to(ROOT))] = (
                    f"/proc/self/fd/{descriptor}"
                    if sys.platform.startswith("linux")
                    else f"/dev/fd/{descriptor}"
                )
            pinned_arguments = [replacements.get(argument, argument) for argument in arguments]
            result = subprocess.run(
                [node_command, cli_command, *pinned_arguments],
                cwd=cwd,
                pass_fds=tuple(descriptors),
                text=True,
                capture_output=capture,
                check=False,
            )
    if result.returncode:
        diagnostics = [(result.stdout or ""), (result.stderr or "")]
        for argument in arguments:
            if not argument.startswith("--out="):
                continue
            output_path = Path(argument.removeprefix("--out="))
            try:
                diagnostics.append(output_path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        output = "\n".join(value for value in diagnostics if value).strip()
        if len(output) > 12_000:
            output = output[:12_000] + "\n... diagnostic truncated ..."
        raise PortableQuintError(f"Quint failed ({result.returncode}): {output}")
    return result


def _normalize_itf(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_itf(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"#bigint"}:
            return int(value["#bigint"])
        return {key: _normalize_itf(item) for key, item in value.items()}
    return value


def _extract_state(spec: Path, variable: str, *, root_fd: int | None = None) -> Any:
    with tempfile.TemporaryDirectory(prefix="dev-standard-portable-quint-") as directory:
        trace = Path(directory) / "trace.itf.json"
        run_quint(
            "run",
            str(spec.relative_to(ROOT)),
            "--backend=typescript",
            "--max-samples=1",
            "--max-steps=0",
            "--verbosity=0",
            f"--out-itf={trace}",
            pinned_inputs=(spec,),
            root_fd=root_fd,
        )
        try:
            return _normalize_itf(json.loads(trace.read_text(encoding="utf-8"))["states"][0][variable])
        except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise PortableQuintError(f"cannot extract {variable}: {exc}") from exc


def _skills_view(*, root_fd: int | None = None) -> dict[str, Any]:
    contracts = _extract_state(SKILLS_QNT, "contracts", root_fd=root_fd)
    return {
        "schema_version": 1,
        "quint_version": QUINT_VERSION,
        "source": "spec/skills/skills.qnt",
        "contracts": sorted(contracts, key=lambda item: item["name"]),
        "invariants": [
            "contractsAreComplete",
            "threePillarsOnly",
            "repositoryPolicyIsHostOwned",
            "defaultPortableSetIsMinimal",
            "dependenciesAreClosed",
            "runnerConformanceIsExplicit",
            "workflowOrderIsConsistent",
            "portablePolicyIsUntouched",
        ],
    }


def _load_specflow(
    receipt: dict[str, Any], *, root_fd: int | None = None
) -> types.ModuleType:
    path = _skill_root(receipt) / "maintain-canonical-requirements/scripts/specflow.py"
    if root_fd is None:
        return safe_io.load_module_nofollow(
            path, root=ROOT, module_name="_dev_standard_portable_specflow"
        )
    return safe_io.load_module_nofollow_pinned(
        path,
        root=ROOT,
        root_fd=root_fd,
        module_name="_dev_standard_portable_specflow",
    )


def _derived(
    receipt: dict[str, Any],
    *,
    catalog: dict[str, Any] | None = None,
    root_fd: int | None = None,
) -> dict[Path, bytes]:
    if safe_io.snapshot_file(REQUIREMENTS_QNT, root=ROOT) == safe_io.MISSING:
        raise PortableQuintError(
            "spec/requirements/requirements.qnt is missing; copy the installed requirements.template.qnt once"
        )
    try:
        catalog = catalog or spec_mapping.assert_bijective_catalog(
            _extract_state(REQUIREMENTS_QNT, "catalog", root_fd=root_fd)
        )
        serialized = _canonical_json(catalog)
        specflow = _load_specflow(receipt, root_fd=root_fd)
        specflow.validate_catalog(catalog, trace_root=ROOT)
        documentation = render_requirements.render_serialized_json(serialized, specflow)
    except (ValueError, RuntimeError) as exc:
        raise PortableQuintError(f"requirements mapping/render failed: {exc}") from exc
    return {REQUIREMENTS_JSON: serialized.encode(), REQUIREMENTS_DOC: documentation.encode()}


def _preflight(receipt: dict[str, Any], *, root_fd: int | None = None) -> None:
    """Reject invalid models and bindings before publishing derived output."""

    _verify_installed_skills(receipt)
    template = _requirements_template(receipt)
    for spec in (REQUIREMENTS_QNT, template, SKILLS_QNT):
        run_quint(
            "typecheck",
            str(spec.relative_to(ROOT)),
            pinned_inputs=(spec,),
            root_fd=root_fd,
        )
    for spec in (REQUIREMENTS_QNT, template):
        run_quint(
            "run",
            str(spec.relative_to(ROOT)),
            "--backend=typescript",
            "--max-samples=1",
            "--max-steps=0",
            "--invariants",
            *REQUIREMENT_INVARIANTS,
            "--verbosity=0",
            capture=True,
            pinned_inputs=(spec,),
            root_fd=root_fd,
        )
    run_quint(
        "run",
        str(SKILLS_QNT.relative_to(ROOT)),
        "--backend=typescript",
        "--max-samples=1",
        "--max-steps=0",
        "--invariants",
        *SKILL_INVARIANTS,
        "--verbosity=0",
        capture=True,
        pinned_inputs=(SKILLS_QNT,),
        root_fd=root_fd,
    )


def _managed_read_preconditions(
    receipt: dict[str, Any], root_fd: int
) -> dict[Path, Any]:
    """Snapshot every receipt-bound input plus adopter-owned requirements."""

    result: dict[Path, Any] = {}
    for path in (COMMITMENT, RECEIPT, REQUIREMENTS_QNT):
        result[path] = safe_io.snapshot_file_pinned(
            path, root=ROOT, root_fd=root_fd
        )
    for entry in receipt["assets"]:
        pure = PurePosixPath(entry["path"])
        path = ROOT.joinpath(*pure.parts)
        snapshot = safe_io.snapshot_file_pinned(path, root=ROOT, root_fd=root_fd)
        if not snapshot.exists or snapshot.sha256 != entry["sha256"]:
            raise PortableQuintError(
                f"installed asset changed while capturing read set: {entry['path']}"
            )
        result[path] = snapshot
    return result


def _trace_read_preconditions(
    catalog: dict[str, Any],
    root_fd: int,
    *,
    output_paths: frozenset[Path],
) -> dict[Path, Any]:
    """Snapshot repository file traces whose existence validates the catalog."""

    result: dict[Path, Any] = {}
    try:
        requirements = catalog["requirements"]
        values = [
            value
            for requirement in requirements
            for key, traces in requirement["traces"].items()
            if key != "standards"
            for value in traces
        ]
    except (KeyError, TypeError) as exc:
        raise PortableQuintError(f"requirements trace read set is invalid: {exc}") from exc
    for value in sorted(set(values)):
        pure = PurePosixPath(value)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise PortableQuintError(f"requirements trace path is unsafe: {value}")
        path = ROOT.joinpath(*pure.parts)
        if path in output_paths:
            # Output CAS already binds this circular self-trace.
            continue
        try:
            result[path] = safe_io.snapshot_file_pinned(
                path, root=ROOT, root_fd=root_fd
            )
        except safe_io.UnsafePathError as exc:
            raise PortableQuintError(
                f"requirements trace must name a regular file for atomic generation: {value}"
            ) from exc
    return result


def generate() -> None:
    output_paths = frozenset({REQUIREMENTS_JSON, REQUIREMENTS_DOC})
    with safe_io.trusted_root(ROOT) as root_fd:
        receipt = _receipt(root_fd=root_fd)
        expected = {
            path: safe_io.snapshot_file_pinned(path, root=ROOT, root_fd=root_fd)
            for path in output_paths
        }
        read_preconditions = _managed_read_preconditions(receipt, root_fd)
        _preflight(receipt, root_fd=root_fd)
        catalog = spec_mapping.assert_bijective_catalog(
            _extract_state(REQUIREMENTS_QNT, "catalog", root_fd=root_fd)
        )
        read_preconditions.update(
            _trace_read_preconditions(
                catalog, root_fd, output_paths=output_paths
            )
        )
        outputs = _derived(receipt, catalog=catalog, root_fd=root_fd)
        safe_io.atomic_batch_write_cas(
            outputs,
            expected,
            root=ROOT,
            lock_name=".devflow/run/quintflow-generate.lock",
            pinned_root_fd=root_fd,
            read_preconditions=read_preconditions,
        )
    print("generated requirements JSON and Markdown from serialized Quint-derived JSON")


def check() -> None:
    receipt = _receipt()
    _preflight(receipt)
    actual_skills = safe_io.read_bytes_nofollow(SKILLS_JSON, root=ROOT)
    expected_skills = _canonical_json(_skills_view()).encode()
    if actual_skills != expected_skills:
        raise PortableQuintError("formal Skill JSON is not the exact Quint-derived view")
    for path, expected in _derived(receipt).items():
        try:
            actual = safe_io.read_bytes_nofollow(path, root=ROOT)
        except FileNotFoundError as exc:
            raise PortableQuintError(f"generated output is missing: {path.relative_to(ROOT)}") from exc
        if actual != expected:
            raise PortableQuintError(f"generated output drift: {path.relative_to(ROOT)}")
    print("portable Quint requirements, Skill contracts, bindings, and policy are current")


def test() -> None:
    check()
    for spec in (REQUIREMENTS_QNT, _requirements_template(_receipt()), SKILLS_QNT):
        run_quint(
            "test",
            str(spec.relative_to(ROOT)),
            "--backend=typescript",
            "--max-samples=100",
            "--verbosity=1",
            pinned_inputs=(spec,),
        )
    run_quint(
        "run",
        str(SKILLS_QNT.relative_to(ROOT)),
        "--backend=typescript",
        "--max-samples=500",
        "--max-steps=3",
        "--invariants",
        *SKILL_INVARIANTS,
        "--verbosity=1",
        pinned_inputs=(SKILLS_QNT,),
    )


def verify() -> None:
    """Run optional Apalache bounded checking without making it an adoption gate."""

    test()
    with tempfile.TemporaryDirectory(prefix="dev-standard-portable-verify-") as directory:
        try:
            for spec, invariants, steps in [
                (REQUIREMENTS_QNT, REQUIREMENT_INVARIANTS, 4),
                (SKILLS_QNT, SKILL_INVARIANTS, 3),
            ]:
                output = Path(directory) / f"{spec.stem}-verification.json"
                run_quint(
                    "verify",
                    str(spec.relative_to(ROOT)),
                    "--backend=apalache",
                    f"--max-steps={steps}",
                    "--invariants",
                    *invariants,
                    f"--out={output}",
                    capture=True,
                    pinned_inputs=(spec,),
                )
        except PortableQuintError as exc:
            raise PortableQuintError(
                "optional external Apalache verification is unavailable or failed; "
                "Java/Apalache setup belongs to the invoking environment and is not "
                f"a target-repository CI requirement: {exc}"
            ) from exc
    print("optional portable Quint/Apalache bounded verification completed")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("command", choices=["setup", "generate", "check", "test", "verify"])
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        globals()[args.command]()
        return 0
    except (PortableQuintError, OSError, safe_io.SafeIOError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
