#!/usr/bin/env python3
"""Set up and run Skill Python dependencies without changing the target venv.

The installer receipt is the authority for both the selected Skills and their
exact ``requirements.txt`` files.  Dependencies are installed into an
immutable repository-local directory, then the requested installed Skill
script is executed with both the runtime and script pinned by file
descriptors.  The target repository's virtualenv and ambient ``PYTHONPATH``
are never modified.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import types
import uuid
from collections.abc import Iterator
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any


class PortablePythonError(RuntimeError):
    """An installation, runtime, or requested script was refused."""


def _lexical_script() -> Path:
    return Path(os.path.abspath(__file__))


def _open_absolute_directory(path: Path) -> int:
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise PortablePythonError(f"pinned directory path is not lexical: {path}")
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
    """Load an exact sibling module without ambient import resolution."""

    if not name.isidentifier():
        raise PortablePythonError(f"invalid pinned tool name: {name!r}")
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
            raise PortablePythonError(f"tools/{name}.py is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(source_fd, 1024 * 1024):
            chunks.append(chunk)
    except OSError as exc:
        raise PortablePythonError(f"cannot load pinned tools/{name}.py: {exc}") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    module_name = f"_dev_standard_portable_python_{name}"
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


# The installer derives this local module closure from the literal call.
safe_io = _load_pinned_tool("safe_io")

ROOT = _lexical_script().parent.parent
COMMITMENT = ROOT / ".dev-standard/install/commitment.json"
RECEIPT = ROOT / ".dev-standard/install/receipt.json"
RUNTIME_PARENT = ROOT / ".dev-standard/python/runtime"
RUNTIME_MARKER = ".dev-standard-python-runtime.json"
_REQUIREMENT = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)=="
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)"
)
_DIRECTORY_FLAGS = (
    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _fd_path(descriptor: int) -> str:
    if sys.platform.startswith("linux"):
        return f"/proc/self/fd/{descriptor}"
    if sys.platform == "darwin":
        return f"/dev/fd/{descriptor}"
    raise PortablePythonError("pinned runtime execution is unsupported on this platform")


def _read_json(content: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PortablePythonError(f"{label} is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PortablePythonError(f"{label} must be a JSON object")
    return value


def _receipt(root_fd: int) -> tuple[dict[str, Any], dict[str, str]]:
    """Verify commitment -> receipt -> every asset through one root FD."""

    try:
        commitment_bytes = safe_io.read_bytes_nofollow_pinned(
            COMMITMENT, root=ROOT, root_fd=root_fd
        )
        receipt_bytes = safe_io.read_bytes_nofollow_pinned(
            RECEIPT, root=ROOT, root_fd=root_fd
        )
    except (OSError, safe_io.SafeIOError) as exc:
        raise PortablePythonError(f"installer commitment is missing or unsafe: {exc}") from exc
    commitment = _read_json(commitment_bytes, "installer commitment")
    receipt = _read_json(receipt_bytes, "installer receipt")
    if set(commitment) != {
        "schema_version",
        "managed_by",
        "receipt",
        "receipt_sha256",
        "assets_sha256",
    } or (
        commitment.get("schema_version") != 2
        or commitment.get("managed_by") != "dev-standard-reference-installer"
        or commitment.get("receipt") != ".dev-standard/install/receipt.json"
        or commitment.get("receipt_sha256") != hashlib.sha256(receipt_bytes).hexdigest()
    ):
        raise PortablePythonError("installer commitment does not bind a valid receipt")
    if set(receipt) != {
        "schema_version",
        "managed_by",
        "host",
        "interface_policy",
        "profiles",
        "skills",
        "quint_version",
        "assets",
    } or receipt.get("schema_version") != 2:
        raise PortablePythonError("installer receipt schema is invalid")
    expected_policy = {"codex": "required", "claude-code": "canonical-omitted"}
    host = receipt.get("host")
    if (
        receipt.get("managed_by") != "dev-standard-reference-installer"
        or not isinstance(host, str)
        or host not in expected_policy
        or receipt.get("interface_policy") != expected_policy.get(host)
        or receipt.get("quint_version") not in {None, "0.32.0"}
    ):
        raise PortablePythonError("installer receipt identity is invalid")
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
        raise PortablePythonError("installer receipt profile or Skill subset is invalid")
    assets = receipt.get("assets")
    if not isinstance(assets, list):
        raise PortablePythonError("installer receipt assets are invalid")
    canonical_assets = (
        json.dumps(assets, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    if commitment.get("assets_sha256") != hashlib.sha256(canonical_assets).hexdigest():
        raise PortablePythonError("installer commitment does not bind the asset inventory")
    records: dict[str, str] = {}
    ordered_paths: list[str] = []
    for entry in assets:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise PortablePythonError("installer asset entry is invalid")
        relative = entry.get("path")
        digest = entry.get("sha256")
        pure = PurePosixPath(relative) if isinstance(relative, str) else PurePosixPath("/")
        if (
            not isinstance(relative, str)
            or relative in records
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise PortablePythonError("installer asset path or digest is invalid")
        path = ROOT.joinpath(*pure.parts)
        try:
            content = safe_io.read_bytes_nofollow_pinned(path, root=ROOT, root_fd=root_fd)
        except (OSError, safe_io.SafeIOError) as exc:
            raise PortablePythonError(f"installed asset is missing or unsafe: {relative}: {exc}") from exc
        if hashlib.sha256(content).hexdigest() != digest:
            raise PortablePythonError(f"installed asset digest drift: {relative}")
        records[relative] = digest
        ordered_paths.append(relative)
    if ordered_paths != sorted(ordered_paths):
        raise PortablePythonError("installer asset inventory is not canonical")
    return receipt, records


def _requirements(
    receipt: dict[str, Any], records: dict[str, str], root_fd: int
) -> dict[str, str]:
    skill_prefix = ".agents/skills" if receipt["host"] == "codex" else ".claude/skills"
    selected = set(receipt["skills"])
    requirements: dict[str, str] = {}
    found = False
    for skill in sorted(selected):
        relative = f"{skill_prefix}/{skill}/requirements.txt"
        path = ROOT / relative
        recorded = relative in records
        exists = safe_io.snapshot_file_pinned(path, root=ROOT, root_fd=root_fd).exists
        if exists != recorded:
            raise PortablePythonError(f"Skill requirements must be installer-managed: {relative}")
        if not recorded:
            continue
        found = True
        try:
            content = safe_io.read_bytes_nofollow_pinned(
                path, root=ROOT, root_fd=root_fd
            )
            if hashlib.sha256(content).hexdigest() != records[relative]:
                raise PortablePythonError(
                    f"Skill requirements changed after receipt validation: {relative}"
                )
            lines = content.decode("utf-8").splitlines()
        except (OSError, UnicodeDecodeError, safe_io.SafeIOError) as exc:
            raise PortablePythonError(f"cannot read exact Skill requirements: {relative}: {exc}") from exc
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                continue
            match = _REQUIREMENT.fullmatch(stripped)
            if match is None:
                raise PortablePythonError(
                    f"{relative}:{number}: only exact Name==version requirements are portable"
                )
            name = _normalize_name(match.group("name"))
            version = match.group("version")
            previous = requirements.get(name)
            if previous is not None and previous != version:
                raise PortablePythonError(
                    f"conflicting exact Skill requirements: {name}=={previous}, {name}=={version}"
                )
            requirements[name] = version
    if not found or not requirements:
        raise PortablePythonError("the installed Skill subset has no Python dependency runtime")
    return dict(sorted(requirements.items()))


def _runtime_identity(requirements: dict[str, str]) -> tuple[str, dict[str, Any]]:
    identity = {
        "requirements": [f"{name}=={version}" for name, version in requirements.items()],
        "python_implementation": sys.implementation.name,
        "python_cache_tag": sys.implementation.cache_tag,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return digest, identity


def _read_regular_at(directory_fd: int, relative: str) -> bytes:
    parts = PurePosixPath(relative).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise PortablePythonError(f"invalid runtime path: {relative}")
    descriptors: list[int] = [os.dup(directory_fd)]
    try:
        for part in parts[:-1]:
            descriptors.append(os.open(part, _DIRECTORY_FLAGS, dir_fd=descriptors[-1]))
        descriptor = os.open(parts[-1], _FILE_FLAGS, dir_fd=descriptors[-1])
        try:
            content, _ = safe_io._read_open_file(descriptor)
            return content
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise PortablePythonError(f"runtime file is missing or unsafe: {relative}: {exc}") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _installed_distributions(site_fd: int) -> dict[str, str]:
    installed: dict[str, str] = {}
    for entry in sorted(os.listdir(site_fd)):
        if not entry.endswith(".dist-info"):
            continue
        info = os.stat(entry, dir_fd=site_fd, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise PortablePythonError(f"installed distribution metadata is unsafe: {entry}")
        metadata_fd = os.open(entry, _DIRECTORY_FLAGS, dir_fd=site_fd)
        try:
            metadata = BytesParser().parsebytes(_read_regular_at(metadata_fd, "METADATA"))
        finally:
            os.close(metadata_fd)
        raw_name = metadata.get("Name")
        version = metadata.get("Version")
        if not raw_name or not version:
            raise PortablePythonError(f"installed distribution metadata is incomplete: {entry}")
        name = _normalize_name(raw_name)
        if name in installed:
            raise PortablePythonError(f"duplicate installed distribution metadata: {name}")
        installed[name] = version
    return installed


def _validate_runtime_fd(
    runtime_fd: int,
    runtime_id: str,
    identity: dict[str, Any],
    requirements: dict[str, str],
) -> int:
    marker = _read_json(
        _read_regular_at(runtime_fd, RUNTIME_MARKER), "Python runtime marker"
    )
    if set(marker) != {
        "schema_version",
        "runtime_id",
        "requirements",
        "python_implementation",
        "python_cache_tag",
        "tree_sha256",
    } or marker != {
        "schema_version": 1,
        "runtime_id": runtime_id,
        **identity,
        "tree_sha256": marker.get("tree_sha256"),
    }:
        raise PortablePythonError("isolated Python runtime identity marker is invalid")
    tree_digest = safe_io.tree_digest_fd_nofollow(
        runtime_fd, display=RUNTIME_PARENT / runtime_id, exclude=frozenset({RUNTIME_MARKER})
    )
    if marker["tree_sha256"] != tree_digest:
        raise PortablePythonError("isolated Python runtime content digest does not match")
    try:
        site_fd = os.open("site-packages", _DIRECTORY_FLAGS, dir_fd=runtime_fd)
    except OSError as exc:
        raise PortablePythonError(f"isolated Python site-packages is unsafe: {exc}") from exc
    try:
        installed = _installed_distributions(site_fd)
        if installed != requirements:
            raise PortablePythonError(
                f"isolated Python packages differ: expected={requirements} actual={installed}"
            )
        return site_fd
    except BaseException:
        os.close(site_fd)
        raise


@contextlib.contextmanager
def _validated_runtime(
    root_fd: int,
    runtime: Path,
    runtime_id: str,
    identity: dict[str, Any],
    requirements: dict[str, str],
) -> Iterator[tuple[int, int]]:
    try:
        with safe_io.directory_nofollow_pinned(
            runtime, root=ROOT, root_fd=root_fd
        ) as runtime_fd:
            site_fd = _validate_runtime_fd(
                runtime_fd, runtime_id, identity, requirements
            )
            try:
                yield runtime_fd, site_fd
            finally:
                os.close(site_fd)
    except FileNotFoundError as exc:
        raise PortablePythonError("isolated Python runtime is not set up") from exc


@contextlib.contextmanager
def _pinned_python() -> Iterator[tuple[int, str]]:
    try:
        executable = Path(sys.executable).resolve(strict=True)
        parent_fd = _open_absolute_directory(executable.parent)
        try:
            descriptor = os.open(executable.name, _FILE_FLAGS, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
            raise PortablePythonError(f"current Python is not a regular executable: {executable}")
    except OSError as exc:
        raise PortablePythonError(f"cannot pin the current Python executable: {exc}") from exc
    try:
        yield descriptor, _fd_path(descriptor)
    finally:
        os.close(descriptor)


def _pip_install(candidate_fd: int, root_fd: int, requirements: dict[str, str]) -> None:
    os.mkdir("site-packages", mode=0o700, dir_fd=candidate_fd)
    target = f"{_fd_path(candidate_fd)}/site-packages"
    packages = [f"{name}=={version}" for name, version in requirements.items()]
    with _pinned_python() as (python_fd, command):
        result = subprocess.run(
            [
                command,
                "-I",
                "-m",
                "pip",
                "install",
                "--target",
                target,
                "--no-deps",
                "--only-binary=:all:",
                "--no-compile",
                "--no-input",
                "--disable-pip-version-check",
                *packages,
            ],
            cwd=_fd_path(root_fd),
            pass_fds=(candidate_fd, root_fd, python_fd),
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode:
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        if len(output) > 12_000:
            output = output[:12_000] + "\n... diagnostic truncated ..."
        raise PortablePythonError(
            f"isolated Python dependency setup failed ({result.returncode}): {output}"
        )


def _write_exclusive(directory_fd: int, name: str, content: bytes) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name, dir_fd=directory_fd)
        raise
    finally:
        os.close(descriptor)
    os.fsync(directory_fd)


def _set_tree_writable(descriptor: int, *, writable: bool) -> None:
    """Seal a prepared runtime, or reopen a failed stage for safe cleanup."""

    for name in sorted(os.listdir(descriptor)):
        info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            raise PortablePythonError(f"Python runtime contains a symlink: {name}")
        if stat.S_ISDIR(info.st_mode):
            child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
            try:
                _set_tree_writable(child_fd, writable=writable)
            finally:
                os.close(child_fd)
            os.chmod(
                name,
                0o700 if writable else 0o555,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
        elif stat.S_ISREG(info.st_mode):
            os.chmod(
                name,
                0o600 if writable else 0o444,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
        else:
            raise PortablePythonError(f"Python runtime contains an unsafe entry: {name}")
    os.fchmod(descriptor, 0o700 if writable else 0o555)


def setup() -> bool:
    """Install the selected Skills' exact dependency closure once."""

    with safe_io.trusted_root(ROOT) as root_fd:
        receipt, records = _receipt(root_fd)
        requirements = _requirements(receipt, records, root_fd)
        runtime_id, identity = _runtime_identity(requirements)
        runtime = RUNTIME_PARENT / runtime_id
        with safe_io.locked_repository_pinned(
            ROOT, root_fd, ".dev-standard/python/runtime/.setup.lock"
        ):
            try:
                with _validated_runtime(
                    root_fd, runtime, runtime_id, identity, requirements
                ):
                    print(f"isolated Python runtime already installed: {runtime_id}")
                    return False
            except PortablePythonError:
                try:
                    with safe_io.directory_nofollow_pinned(
                        runtime, root=ROOT, root_fd=root_fd
                    ):
                        raise PortablePythonError(
                            "existing isolated Python runtime is invalid; review and remove that exact directory"
                        )
                except FileNotFoundError:
                    pass

            with safe_io.directory_nofollow_pinned(
                RUNTIME_PARENT, root=ROOT, root_fd=root_fd, create=True
            ) as parent_fd:
                candidate_name = f".{runtime_id}.stage-{uuid.uuid4().hex}"
                os.mkdir(candidate_name, mode=0o700, dir_fd=parent_fd)
                candidate_fd = os.open(candidate_name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
            candidate = RUNTIME_PARENT / candidate_name
            published = False
            try:
                _pip_install(candidate_fd, root_fd, requirements)
                tree_digest = safe_io.tree_digest_fd_nofollow(
                    candidate_fd,
                    display=candidate,
                    exclude=frozenset({RUNTIME_MARKER}),
                )
                marker = _canonical_json(
                    {
                        "schema_version": 1,
                        "runtime_id": runtime_id,
                        **identity,
                        "tree_sha256": tree_digest,
                    }
                )
                _write_exclusive(candidate_fd, RUNTIME_MARKER, marker)
                validation_fd = _validate_runtime_fd(
                    candidate_fd, runtime_id, identity, requirements
                )
                os.close(validation_fd)
                _set_tree_writable(candidate_fd, writable=False)
                safe_io.atomic_publish_directory_noreplace(
                    candidate,
                    runtime,
                    root=ROOT,
                    pinned_root_fd=root_fd,
                )
                published = True
                with safe_io.directory_nofollow_pinned(
                    runtime, root=ROOT, root_fd=root_fd
                ) as published_fd:
                    before = os.fstat(candidate_fd)
                    after = os.fstat(published_fd)
                    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                        raise PortablePythonError("published Python runtime identity changed")
                    site_fd = _validate_runtime_fd(
                        published_fd, runtime_id, identity, requirements
                    )
                    os.close(site_fd)
                print(f"installed isolated Python runtime: {runtime_id}")
                return True
            finally:
                if not published:
                    with contextlib.suppress(OSError, PortablePythonError):
                        _set_tree_writable(candidate_fd, writable=True)
                os.close(candidate_fd)
                safe_io.remove_tree_nofollow(
                    candidate, root=ROOT, pinned_root_fd=root_fd
                )


def _script_relative(value: str, receipt: dict[str, Any], records: dict[str, str]) -> str:
    pure = PurePosixPath(value)
    if (
        not value
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.suffix != ".py"
    ):
        raise PortablePythonError("run requires a lexical repository-relative Python script")
    prefix = ".agents/skills" if receipt["host"] == "codex" else ".claude/skills"
    parts = pure.parts
    if (
        len(parts) < 5
        or "/".join(parts[:2]) != prefix
        or parts[2] not in receipt["skills"]
        or parts[3] != "scripts"
        or value not in records
    ):
        raise PortablePythonError("run only accepts an installer-managed selected Skill script")
    return value


_BOOTSTRAP = """\
import hashlib
import json
import os
import stat
import sys
import types

site_packages, requested, serialized_assets, *arguments = sys.argv[1:]
envelope = json.loads(serialized_assets)
assets = envelope["assets"]
root_identity = tuple(envelope["root_identity"])

def read_snapshot(relative):
    record = assets.get(relative)
    if not isinstance(record, dict) or set(record) != {"fd", "logical", "sha256"}:
        raise ImportError(f"asset is outside the pinned receipt closure: {relative}")
    descriptor = record["fd"]
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise ImportError(f"pinned asset is not regular: {relative}")
    chunks = []
    offset = 0
    while True:
        chunk = os.pread(descriptor, 1024 * 1024, offset)
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
    after = os.fstat(descriptor)
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise ImportError(f"pinned asset changed while read: {relative}")
    content = b"".join(chunks)
    if hashlib.sha256(content).hexdigest() != record["sha256"]:
        raise ImportError(f"pinned asset digest changed: {relative}")
    return content, record["logical"]

class PinnedImports(types.ModuleType):
    def __init__(self):
        super().__init__("_dev_standard_portable_imports")
        self._cache = {}
        self.root_identity = root_identity

    def load_relative(self, relative, module_name):
        if not isinstance(relative, str) or not isinstance(module_name, str):
            raise ImportError("pinned Python module request is invalid")
        if not module_name or any(not part.isidentifier() for part in module_name.split(".")):
            raise ImportError(f"pinned Python module name is invalid: {module_name!r}")
        key = (relative, module_name)
        if key in self._cache:
            return self._cache[key]
        source, logical = read_snapshot(relative)
        module = types.ModuleType(module_name)
        module.__file__ = logical
        module.__package__ = module_name.rpartition(".")[0]
        module._bootstrap_root_identity = root_identity
        previous = sys.modules.get(module_name)
        sys.modules[module_name] = module
        try:
            exec(compile(source, logical, "exec"), module.__dict__)
        except BaseException:
            if previous is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous
            raise
        self._cache[key] = module
        return module

    def read_relative(self, relative):
        return read_snapshot(relative)[0]

    def contains(self, relative):
        return relative in assets

runtime = PinnedImports()
sys.modules[runtime.__name__] = runtime

# No installed Skill directory is importable.  Only exact receipt-bound Python
# snapshots are available through ``runtime.load_relative``; this prevents both
# unmanaged shadow modules and recorded-sibling path swaps after validation.
sys.path.insert(0, site_packages)
source, logical = read_snapshot(requested)
sys.argv = [logical, *arguments]
namespace = {
    "__name__": "__main__",
    "__file__": logical,
    "__package__": None,
    "__spec__": None,
    "__cached__": None,
}
exec(compile(source, logical, "exec"), namespace)
"""


def run(script_value: str, arguments: list[str]) -> int:
    """Execute one receipt-bound Skill script with the pinned runtime."""

    with safe_io.trusted_root(ROOT) as root_fd:
        receipt, records = _receipt(root_fd)
        requirements = _requirements(receipt, records, root_fd)
        runtime_id, identity = _runtime_identity(requirements)
        runtime = RUNTIME_PARENT / runtime_id
        relative = _script_relative(script_value, receipt, records)
        with _validated_runtime(
            root_fd, runtime, runtime_id, identity, requirements
        ) as (_, site_fd):
            with contextlib.ExitStack() as stack:
                snapshots: dict[str, dict[str, Any]] = {}
                snapshot_fds: list[int] = []
                for asset, digest in sorted(records.items()):
                    path = ROOT.joinpath(*PurePosixPath(asset).parts)
                    with safe_io.open_file_nofollow_pinned(
                        path, root=ROOT, root_fd=root_fd
                    ) as source_fd:
                        content, _ = safe_io._read_open_file(source_fd)
                    if hashlib.sha256(content).hexdigest() != digest:
                        raise PortablePythonError(
                            f"installed asset changed after receipt validation: {asset}"
                        )
                    snapshot = stack.enter_context(tempfile.TemporaryFile())
                    snapshot.write(content)
                    snapshot.flush()
                    os.fsync(snapshot.fileno())
                    snapshot_fds.append(snapshot.fileno())
                    snapshots[asset] = {
                        "fd": snapshot.fileno(),
                        "logical": str(path),
                        "sha256": digest,
                    }
                if relative not in snapshots:
                    raise PortablePythonError(
                        "requested Skill script is absent from the pinned Python closure"
                    )
                envelope = json.dumps(
                    {
                        "assets": snapshots,
                        "root_identity": [
                            os.fstat(root_fd).st_dev,
                            os.fstat(root_fd).st_ino,
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                python_fd, command = stack.enter_context(_pinned_python())
                result = subprocess.run(
                    [
                        command,
                        "-I",
                        "-B",
                        "-c",
                        _BOOTSTRAP,
                        _fd_path(site_fd),
                        relative,
                        envelope,
                        *arguments,
                    ],
                    cwd=_fd_path(root_fd),
                    pass_fds=(
                        root_fd,
                        site_fd,
                        python_fd,
                        *snapshot_fds,
                    ),
                    check=False,
                )
                return result.returncode


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="install the exact isolated dependency runtime")
    execute = commands.add_parser("run", help="run an installed Skill Python script")
    execute.add_argument("script")
    execute.add_argument("arguments", nargs=argparse.REMAINDER)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "setup":
            setup()
            return 0
        arguments = list(args.arguments)
        if arguments[:1] == ["--"]:
            arguments.pop(0)
        return run(args.script, arguments)
    except (PortablePythonError, OSError, safe_io.SafeIOError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
