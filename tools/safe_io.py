#!/usr/bin/env python3
"""Symlink-safe, compare-and-swap file I/O inside a trusted root.

The helpers in this module deliberately operate through directory file
descriptors.  A caller therefore cannot replace an already-checked path
component with a symlink and redirect a write outside ``root``.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import hashlib
import os
import stat
import sys
import types
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

try:  # pragma: no cover - Windows is exercised by the fallback below.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


class SafeIOError(RuntimeError):
    """Base error for a refused or failed safe I/O operation."""


class UnsafePathError(SafeIOError):
    """A path escaped its root or contained an unsafe filesystem object."""


class ConcurrentModificationError(SafeIOError):
    """A compare-and-swap precondition no longer matched."""


@dataclass(frozen=True)
class FileSnapshot:
    """Identity and content observed for one regular file."""

    exists: bool
    device: int | None = None
    inode: int | None = None
    mode: int | None = None
    size: int | None = None
    mtime_ns: int | None = None
    sha256: str | None = None


MISSING = FileSnapshot(exists=False)
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_FILE_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_FILE_CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
_RENAME_NOREPLACE = 1
_RENAME_EXCHANGE = 2
_RENAME_SWAP_DARWIN = 0x00000002
_RENAME_EXCL_DARWIN = 0x00000004
_EXPECTED_ROOT_IDENTITIES: dict[str, tuple[int, int]] = {}


def _reject_lexical_alias(path: Path) -> None:
    """Reject spelling tricks before ``Path``/the kernel can normalise them."""

    raw = os.fspath(path)
    separators = {os.sep}
    if os.altsep:
        separators.add(os.altsep)
    components = [raw]
    for separator in separators:
        split: list[str] = []
        for component in components:
            split.extend(component.split(separator))
        components = split
    if any(component in {".", ".."} for component in components):
        raise UnsafePathError(f"path contains a lexical alias component: {path}")


def _absolute_lexical(path: Path) -> Path:
    _reject_lexical_alias(path)
    return path if path.is_absolute() else Path.cwd() / path


def _relative_parts(root: Path, path: Path) -> tuple[Path, tuple[str, ...]]:
    root = _absolute_lexical(root)
    path = _absolute_lexical(path)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"path escapes trusted root: {path}") from exc
    parts = relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise UnsafePathError(f"path must name an entry below trusted root: {path}")
    return root, parts


def bind_root_identity(root: Path, identity: tuple[int, int]) -> None:
    """Bind every future descriptor open of ``root`` to ``identity``."""

    lexical = _absolute_lexical(root)
    if (
        len(identity) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in identity)
        or any(value < 0 for value in identity)
    ):
        raise UnsafePathError("trusted root identity must contain device and inode")
    key = os.fspath(lexical)
    previous = _EXPECTED_ROOT_IDENTITIES.get(key)
    if previous is not None and previous != identity:
        raise ConcurrentModificationError(
            f"trusted root identity binding changed: {lexical}"
        )
    _EXPECTED_ROOT_IDENTITIES[key] = identity


def _verify_root_identity(root: Path, descriptor: int) -> None:
    expected = _EXPECTED_ROOT_IDENTITIES.get(os.fspath(root))
    if expected is None:
        return
    info = os.fstat(descriptor)
    if (info.st_dev, info.st_ino) != expected:
        raise ConcurrentModificationError(
            f"trusted root changed after identity binding: {root}"
        )


def _open_root(root: Path) -> int:
    """Open every absolute-path component with ``O_NOFOLLOW``.

    Checking only the final component with ``lstat`` is insufficient: an
    attacker can replace any ancestor with a symlink between validation and
    use.  The returned descriptor pins the directory identity for the caller.
    """

    root = _absolute_lexical(root)
    if not root.is_absolute():  # Defensive; _absolute_lexical always returns one.
        raise UnsafePathError(f"trusted root must be absolute: {root}")
    if os.name == "nt":  # pragma: no cover - descriptor-relative APIs are POSIX.
        try:
            info = os.lstat(root)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise UnsafePathError(f"trusted root is not a real directory: {root}")
            descriptor = os.open(root, _DIRECTORY_FLAGS)
            try:
                _verify_root_identity(root, descriptor)
                return descriptor
            except BaseException:
                os.close(descriptor)
                raise
        except OSError as exc:
            raise UnsafePathError(f"trusted root is unavailable: {root}: {exc}") from exc

    try:
        current = os.open(os.sep, _DIRECTORY_FLAGS)
    except OSError as exc:
        raise UnsafePathError(f"cannot open filesystem root: {exc}") from exc
    try:
        for component in root.parts[1:]:
            try:
                next_fd = os.open(component, _DIRECTORY_FLAGS, dir_fd=current)
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise UnsafePathError(
                        f"trusted root ancestor is symlinked or not a directory: {root}"
                    ) from exc
                raise UnsafePathError(f"trusted root is unavailable: {root}: {exc}") from exc
            os.close(current)
            current = next_fd
        _verify_root_identity(root, current)
        return current
    except BaseException:
        os.close(current)
        raise


def _open_directory_at(root_fd: int, parts: tuple[str, ...], *, create: bool) -> int:
    current = os.dup(root_fd)
    try:
        for part in parts:
            try:
                next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, mode=0o755, dir_fd=current)
                except FileExistsError:
                    # A concurrent creator is accepted only if the no-follow
                    # open below proves that it created a real directory.
                    pass
                try:
                    next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=current)
                except OSError as exc:
                    if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                        raise UnsafePathError(
                            f"path component is symlinked or not a directory: {part}"
                        ) from exc
                    raise
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise UnsafePathError(f"path component is symlinked or not a directory: {part}") from exc
                raise
            os.close(current)
            current = next_fd
        return current
    except BaseException:
        os.close(current)
        raise


@contextlib.contextmanager
def trusted_root(root: Path) -> Iterator[int]:
    """Yield one descriptor that pins a symlink-free trusted root."""

    descriptor = _open_root(root)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def _parent_fd_at(
    root_fd: int,
    parts: tuple[str, ...],
    *,
    create: bool = False,
) -> Iterator[tuple[int, str]]:
    try:
        parent_fd = _open_directory_at(root_fd, parts[:-1], create=create)
    except FileNotFoundError:
        raise
    try:
        yield parent_fd, parts[-1]
    finally:
        os.close(parent_fd)


@contextlib.contextmanager
def _parent_fd(root: Path, path: Path, *, create: bool = False) -> Iterator[tuple[int, str]]:
    root, parts = _relative_parts(root, path)
    with trusted_root(root) as root_fd:
        with _parent_fd_at(root_fd, parts, create=create) as value:
            yield value


def _read_open_file(descriptor: int) -> tuple[bytes, os.stat_result]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise UnsafePathError("expected a regular file")
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
    after = os.fstat(descriptor)
    stable_fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
        raise ConcurrentModificationError("file changed while it was being read")
    return b"".join(chunks), after


def _snapshot_at(parent_fd: int, name: str) -> FileSnapshot:
    try:
        descriptor = os.open(name, _FILE_READ_FLAGS, dir_fd=parent_fd)
    except FileNotFoundError:
        return MISSING
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise UnsafePathError(f"file is symlinked or unsafe: {name}") from exc
        raise
    try:
        content, info = _read_open_file(descriptor)
    finally:
        os.close(descriptor)
    return FileSnapshot(
        exists=True,
        device=info.st_dev,
        inode=info.st_ino,
        mode=stat.S_IMODE(info.st_mode),
        size=info.st_size,
        mtime_ns=info.st_mtime_ns,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def snapshot_file(path: Path, *, root: Path) -> FileSnapshot:
    """Snapshot ``path`` without following any component below ``root``.

    A missing parent or leaf is represented by :data:`MISSING` so callers can
    use the same API for safe first-time creation.
    """

    try:
        with _parent_fd(root, path) as (parent_fd, name):
            return _snapshot_at(parent_fd, name)
    except FileNotFoundError:
        return MISSING


def snapshot_file_pinned(path: Path, *, root: Path, root_fd: int) -> FileSnapshot:
    """Snapshot through a caller-owned root descriptor."""

    _, parts = _relative_parts(root, path)
    try:
        with _parent_fd_at(root_fd, parts) as (parent_fd, name):
            return _snapshot_at(parent_fd, name)
    except FileNotFoundError:
        return MISSING


def read_bytes_nofollow(path: Path, *, root: Path) -> bytes:
    """Read a regular file while refusing symlinks below ``root``."""

    try:
        with _parent_fd(root, path) as (parent_fd, name):
            descriptor = os.open(name, _FILE_READ_FLAGS, dir_fd=parent_fd)
            try:
                content, _ = _read_open_file(descriptor)
                return content
            finally:
                os.close(descriptor)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise UnsafePathError(f"file is symlinked or unsafe: {path}") from exc
        raise


def read_bytes_nofollow_pinned(path: Path, *, root: Path, root_fd: int) -> bytes:
    """Read through a caller-owned root descriptor."""

    _, parts = _relative_parts(root, path)
    try:
        with _parent_fd_at(root_fd, parts) as (parent_fd, name):
            descriptor = os.open(name, _FILE_READ_FLAGS, dir_fd=parent_fd)
            try:
                content, _ = _read_open_file(descriptor)
                return content
            finally:
                os.close(descriptor)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise UnsafePathError(f"file is symlinked or unsafe: {path}") from exc
        raise


@contextlib.contextmanager
def open_file_nofollow_pinned(path: Path, *, root: Path, root_fd: int) -> Iterator[int]:
    """Yield a pinned regular-file descriptor below ``root_fd``."""

    _, parts = _relative_parts(root, path)
    with _parent_fd_at(root_fd, parts) as (parent_fd, name):
        try:
            descriptor = os.open(name, _FILE_READ_FLAGS, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise UnsafePathError(f"file is symlinked or unsafe: {path}") from exc
            raise
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise UnsafePathError(f"expected a regular file: {path}")
            yield descriptor
        finally:
            os.close(descriptor)


def load_module_nofollow(path: Path, *, root: Path, module_name: str) -> types.ModuleType:
    """Compile and load one pinned Python source file without following links."""

    source = read_bytes_nofollow(path, root=root)
    try:
        code = compile(source, str(path), "exec")
    except (SyntaxError, ValueError) as exc:
        raise SafeIOError(f"cannot compile pinned module {path}: {exc}") from exc
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = module_name.rpartition(".")[0]
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


def load_module_nofollow_pinned(
    path: Path,
    *,
    root: Path,
    root_fd: int,
    module_name: str,
) -> types.ModuleType:
    """Compile a module read through a caller-pinned root descriptor."""

    source = read_bytes_nofollow_pinned(path, root=root, root_fd=root_fd)
    try:
        code = compile(source, str(path), "exec")
    except (SyntaxError, ValueError) as exc:
        raise SafeIOError(f"cannot compile pinned module {path}: {exc}") from exc
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = module_name.rpartition(".")[0]
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


@contextlib.contextmanager
def directory_nofollow(path: Path, *, root: Path, create: bool = False) -> Iterator[int]:
    """Yield a descriptor for a real directory below ``root``."""

    lexical_root = _absolute_lexical(root)
    lexical_path = _absolute_lexical(path)
    if lexical_path == lexical_root:
        descriptor = _open_root(root)
        try:
            yield descriptor
        finally:
            os.close(descriptor)
        return
    _, parts = _relative_parts(root, path)
    root_fd = _open_root(root)
    try:
        descriptor = _open_directory_at(root_fd, parts, create=create)
        try:
            yield descriptor
        finally:
            os.close(descriptor)
    finally:
        os.close(root_fd)


@contextlib.contextmanager
def directory_nofollow_pinned(
    path: Path,
    *,
    root: Path,
    root_fd: int,
    create: bool = False,
) -> Iterator[int]:
    """Yield a directory descriptor below a caller-pinned root."""

    lexical_root = _absolute_lexical(root)
    lexical_path = _absolute_lexical(path)
    if lexical_path == lexical_root:
        descriptor = os.dup(root_fd)
    else:
        _, parts = _relative_parts(lexical_root, lexical_path)
        descriptor = _open_directory_at(root_fd, parts, create=create)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def validate_tree_nofollow(path: Path, *, root: Path) -> None:
    """Reject symlinks and non-file/non-directory entries in a directory tree."""

    def inspect(descriptor: int, display: Path) -> None:
        for name in sorted(os.listdir(descriptor)):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            child = display / name
            if stat.S_ISLNK(info.st_mode):
                raise UnsafePathError(f"tree contains a symlink: {child}")
            if stat.S_ISDIR(info.st_mode):
                child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
                try:
                    inspect(child_fd, child)
                finally:
                    os.close(child_fd)
            elif not stat.S_ISREG(info.st_mode):
                raise UnsafePathError(f"tree contains an unsupported entry: {child}")

    with directory_nofollow(path, root=root) as descriptor:
        inspect(descriptor, path)


def tree_digest_nofollow(
    path: Path,
    *,
    root: Path,
    exclude: frozenset[str] = frozenset(),
) -> str:
    """Return a deterministic digest for a symlink-free directory tree."""

    digest = hashlib.sha256()

    def inspect(descriptor: int, prefix: tuple[str, ...]) -> None:
        for name in sorted(os.listdir(descriptor)):
            relative = "/".join((*prefix, name))
            if relative in exclude:
                continue
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise UnsafePathError(f"tree contains a symlink: {path / relative}")
            if stat.S_ISDIR(info.st_mode):
                digest.update(b"D\0" + relative.encode("utf-8") + b"\0")
                child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
                try:
                    inspect(child_fd, (*prefix, name))
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(info.st_mode):
                digest.update(b"F\0" + relative.encode("utf-8") + b"\0")
                file_fd = os.open(name, _FILE_READ_FLAGS, dir_fd=descriptor)
                try:
                    while True:
                        chunk = os.read(file_fd, 1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                finally:
                    os.close(file_fd)
                digest.update(b"\0")
            else:
                raise UnsafePathError(f"tree contains an unsupported entry: {path / relative}")

    with directory_nofollow(path, root=root) as descriptor:
        inspect(descriptor, ())
    return digest.hexdigest()


def tree_digest_nofollow_pinned(
    path: Path,
    *,
    root: Path,
    root_fd: int,
    exclude: frozenset[str] = frozenset(),
) -> str:
    """Digest a tree below a caller-pinned root descriptor."""

    digest = hashlib.sha256()

    def inspect(descriptor: int, prefix: tuple[str, ...]) -> None:
        for name in sorted(os.listdir(descriptor)):
            relative = "/".join((*prefix, name))
            if relative in exclude:
                continue
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise UnsafePathError(f"tree contains a symlink: {path / relative}")
            if stat.S_ISDIR(info.st_mode):
                digest.update(b"D\0" + relative.encode() + b"\0")
                child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
                try:
                    inspect(child_fd, (*prefix, name))
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(info.st_mode):
                digest.update(b"F\0" + relative.encode() + b"\0")
                file_fd = os.open(name, _FILE_READ_FLAGS, dir_fd=descriptor)
                try:
                    while chunk := os.read(file_fd, 1024 * 1024):
                        digest.update(chunk)
                finally:
                    os.close(file_fd)
                digest.update(b"\0")
            else:
                raise UnsafePathError(f"tree contains an unsupported entry: {path / relative}")

    with directory_nofollow_pinned(path, root=root, root_fd=root_fd) as descriptor:
        inspect(descriptor, ())
    return digest.hexdigest()


def tree_digest_fd_nofollow(
    descriptor: int,
    *,
    display: Path,
    exclude: frozenset[str] = frozenset(),
) -> str:
    """Digest a directory already pinned by the caller.

    Runtime loaders use this boundary after opening an immutable runtime
    directory.  Traversal therefore cannot be redirected by replacing the
    repository-relative directory name between validation and execution.
    ``descriptor`` remains owned by the caller.
    """

    root_info = os.fstat(descriptor)
    if not stat.S_ISDIR(root_info.st_mode):
        raise UnsafePathError(f"expected a pinned directory: {display}")
    digest = hashlib.sha256()

    def inspect(current: int, prefix: tuple[str, ...]) -> None:
        for name in sorted(os.listdir(current)):
            relative = "/".join((*prefix, name))
            if relative in exclude:
                continue
            info = os.stat(name, dir_fd=current, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise UnsafePathError(f"tree contains a symlink: {display / relative}")
            if stat.S_ISDIR(info.st_mode):
                digest.update(b"D\0" + relative.encode() + b"\0")
                child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=current)
                try:
                    inspect(child_fd, (*prefix, name))
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(info.st_mode):
                digest.update(b"F\0" + relative.encode() + b"\0")
                file_fd = os.open(name, _FILE_READ_FLAGS, dir_fd=current)
                try:
                    content, _ = _read_open_file(file_fd)
                    digest.update(content)
                finally:
                    os.close(file_fd)
                digest.update(b"\0")
            else:
                raise UnsafePathError(
                    f"tree contains an unsupported entry: {display / relative}"
                )

    duplicated = os.dup(descriptor)
    try:
        inspect(duplicated, ())
    finally:
        os.close(duplicated)
    return digest.hexdigest()


def directory_identity_fd_nofollow(
    descriptor: int,
    *,
    display: Path,
) -> tuple[int, int, str]:
    """Return a stable device, inode, and digest for a pinned directory."""

    before = os.fstat(descriptor)
    digest = tree_digest_fd_nofollow(descriptor, display=display)
    after = os.fstat(descriptor)
    stable_fields = ("st_dev", "st_ino", "st_mode", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
        raise ConcurrentModificationError(f"directory changed while inspected: {display}")
    return before.st_dev, before.st_ino, digest


def directory_identity_nofollow(
    path: Path,
    *,
    root: Path,
    pinned_root_fd: int | None = None,
) -> tuple[int, int, str]:
    """Return a stable identity for one repository-local directory."""

    manager = (
        directory_nofollow_pinned(path, root=root, root_fd=pinned_root_fd)
        if pinned_root_fd is not None
        else directory_nofollow(path, root=root)
    )
    with manager as descriptor:
        return directory_identity_fd_nofollow(descriptor, display=path)


def remove_tree_nofollow(
    path: Path,
    *,
    root: Path,
    pinned_root_fd: int | None = None,
) -> None:
    """Remove one directory tree without ever traversing a symlink."""

    _, parts = _relative_parts(root, path)
    parent_path = _absolute_lexical(root).joinpath(*parts[:-1])

    def clear(descriptor: int) -> None:
        for name in sorted(os.listdir(descriptor)):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
                try:
                    clear(child_fd)
                finally:
                    os.close(child_fd)
                os.rmdir(name, dir_fd=descriptor)
            else:
                os.unlink(name, dir_fd=descriptor)

    try:
        manager = (
            directory_nofollow_pinned(
                parent_path, root=root, root_fd=pinned_root_fd
            )
            if pinned_root_fd is not None
            else directory_nofollow(parent_path, root=root)
        )
        with manager as parent_fd:
            try:
                info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                return
            if stat.S_ISLNK(info.st_mode):
                os.unlink(parts[-1], dir_fd=parent_fd)
                return
            if not stat.S_ISDIR(info.st_mode):
                raise UnsafePathError(f"refusing to remove non-directory tree: {path}")
            descriptor = os.open(parts[-1], _DIRECTORY_FLAGS, dir_fd=parent_fd)
            try:
                clear(descriptor)
            finally:
                os.close(descriptor)
            os.rmdir(parts[-1], dir_fd=parent_fd)
            os.fsync(parent_fd)
    except FileNotFoundError:
        return


def remove_tree_nofollow_cas(
    path: Path,
    *,
    expected_identity: tuple[int, int, str],
    root: Path,
    pinned_root_fd: int | None = None,
) -> None:
    """Remove only the exact directory captured by an atomic rename boundary.

    The source name is first moved with no-replace semantics to an unpredictable
    quarantine name.  Identity is checked after that atomic capture, and tree
    contents are cleared only through the captured directory descriptor.  A
    competing entry swapped into the quarantine name is therefore preserved.
    """

    _, parts = _relative_parts(root, path)
    parent_path = _absolute_lexical(root).joinpath(*parts[:-1])

    def capture(parent_fd: int, source: str, destination: str) -> None:
        try:
            if _renameat2(
                parent_fd,
                source,
                parent_fd,
                destination,
                _RENAME_NOREPLACE,
            ):
                return
            if _renameatx_np(
                parent_fd,
                source,
                parent_fd,
                destination,
                _RENAME_EXCL_DARWIN,
            ):
                return
            if os.name == "nt":  # Windows rename refuses an existing target.
                os.rename(
                    source,
                    destination,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
                return
            raise SafeIOError(
                "atomic directory no-replace is unavailable on this platform"
            )
        except FileExistsError as exc:
            raise ConcurrentModificationError(
                f"directory CAS destination already exists: {path}"
            ) from exc

    def clear(descriptor: int) -> None:
        for name in sorted(os.listdir(descriptor)):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
                try:
                    clear(child_fd)
                finally:
                    os.close(child_fd)
                os.rmdir(name, dir_fd=descriptor)
            else:
                os.unlink(name, dir_fd=descriptor)
        os.fsync(descriptor)

    manager = (
        directory_nofollow_pinned(
            parent_path,
            root=root,
            root_fd=pinned_root_fd,
        )
        if pinned_root_fd is not None
        else directory_nofollow(parent_path, root=root)
    )
    with manager as parent_fd:
        try:
            info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise ConcurrentModificationError(
                f"directory disappeared before CAS removal: {path}"
            ) from exc
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise UnsafePathError(f"refusing to remove non-directory tree: {path}")
        quarantine = f".{parts[-1]}.safeio-delete-{uuid.uuid4().hex}"
        try:
            capture(parent_fd, parts[-1], quarantine)
        except FileNotFoundError as exc:
            raise ConcurrentModificationError(
                f"directory disappeared before CAS capture: {path}"
            ) from exc
        captured = parent_path / quarantine
        descriptor = os.open(quarantine, _DIRECTORY_FLAGS, dir_fd=parent_fd)
        try:
            actual_identity = directory_identity_fd_nofollow(
                descriptor,
                display=captured,
            )
            if actual_identity != expected_identity:
                try:
                    capture(parent_fd, quarantine, parts[-1])
                except SafeIOError as restore_error:
                    raise ConcurrentModificationError(
                        "directory changed before CAS removal and the competing "
                        f"entry was preserved at {captured}: {restore_error}"
                    ) from restore_error
                raise ConcurrentModificationError(
                    f"directory changed before CAS removal: {path}"
                )
            clear(descriptor)
            pinned = os.fstat(descriptor)
            try:
                current = os.stat(
                    quarantine,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError as exc:
                raise ConcurrentModificationError(
                    "captured directory name changed during CAS removal; no "
                    "competing entry was deleted"
                ) from exc
            if (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino):
                raise ConcurrentModificationError(
                    "captured directory name changed during CAS removal; the "
                    f"competing entry was preserved at {captured}"
                )
            try:
                os.rmdir(quarantine, dir_fd=parent_fd)
            except OSError as exc:
                if exc.errno in {errno.ENOTEMPTY, errno.EEXIST}:
                    raise ConcurrentModificationError(
                        "captured directory changed before final removal; the "
                        f"competing entry was preserved at {captured}"
                    ) from exc
                raise
            os.fsync(parent_fd)
        finally:
            os.close(descriptor)


def remove_named_entries_nofollow(
    path: Path,
    *,
    root: Path,
    names: frozenset[str],
    pinned_root_fd: int | None = None,
) -> int:
    """Remove matching entries recursively through pinned directory FDs.

    This is intended for package-manager link farms such as every nested
    ``node_modules/**/.bin``.  Matching symlinks are unlinked, never followed;
    any non-matching symlink fails closed so a subsequent tree validation
    cannot accidentally bless a link outside the runtime.
    """

    removed = 0

    def clear_tree(descriptor: int) -> None:
        for entry in sorted(os.listdir(descriptor)):
            info = os.stat(entry, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                child_fd = os.open(entry, _DIRECTORY_FLAGS, dir_fd=descriptor)
                try:
                    clear_tree(child_fd)
                finally:
                    os.close(child_fd)
                os.rmdir(entry, dir_fd=descriptor)
            else:
                os.unlink(entry, dir_fd=descriptor)

    def inspect(descriptor: int, display: Path) -> None:
        nonlocal removed
        for entry in sorted(os.listdir(descriptor)):
            info = os.stat(entry, dir_fd=descriptor, follow_symlinks=False)
            child = display / entry
            if entry in names:
                if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                    child_fd = os.open(entry, _DIRECTORY_FLAGS, dir_fd=descriptor)
                    try:
                        clear_tree(child_fd)
                    finally:
                        os.close(child_fd)
                    os.rmdir(entry, dir_fd=descriptor)
                else:
                    os.unlink(entry, dir_fd=descriptor)
                os.fsync(descriptor)
                removed += 1
                continue
            if stat.S_ISLNK(info.st_mode):
                raise UnsafePathError(f"tree contains a symlink outside removable entries: {child}")
            if stat.S_ISDIR(info.st_mode):
                child_fd = os.open(entry, _DIRECTORY_FLAGS, dir_fd=descriptor)
                try:
                    inspect(child_fd, child)
                finally:
                    os.close(child_fd)
            elif not stat.S_ISREG(info.st_mode):
                raise UnsafePathError(f"tree contains an unsupported entry: {child}")

    manager = (
        directory_nofollow_pinned(path, root=root, root_fd=pinned_root_fd)
        if pinned_root_fd is not None
        else directory_nofollow(path, root=root)
    )
    with manager as descriptor:
        inspect(descriptor, path)
    return removed


def atomic_publish_directory_noreplace(
    candidate: Path,
    destination: Path,
    *,
    root: Path,
    pinned_root_fd: int | None = None,
) -> None:
    """Atomically publish a prepared directory without replacing any entry."""

    _, candidate_parts = _relative_parts(root, candidate)
    _, destination_parts = _relative_parts(root, destination)
    if candidate_parts[:-1] != destination_parts[:-1]:
        raise SafeIOError("candidate and destination must have the same parent")
    if pinned_root_fd is None:
        validate_tree_nofollow(candidate, root=root)
    else:
        # A digest traversal validates every entry without following links.
        tree_digest_nofollow_pinned(candidate, root=root, root_fd=pinned_root_fd)
    parent_path = _absolute_lexical(root).joinpath(*candidate_parts[:-1])
    manager = (
        directory_nofollow_pinned(parent_path, root=root, root_fd=pinned_root_fd)
        if pinned_root_fd is not None
        else directory_nofollow(parent_path, root=root)
    )
    with manager as parent_fd:
        info = os.stat(candidate_parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode):
            raise UnsafePathError(f"candidate is not a real directory: {candidate}")
        try:
            if _renameat2(
                parent_fd,
                candidate_parts[-1],
                parent_fd,
                destination_parts[-1],
                _RENAME_NOREPLACE,
            ):
                os.fsync(parent_fd)
                return
            if _renameatx_np(
                parent_fd,
                candidate_parts[-1],
                parent_fd,
                destination_parts[-1],
                _RENAME_EXCL_DARWIN,
            ):
                os.fsync(parent_fd)
                return
            if os.name == "nt":  # Windows rename refuses an existing target.
                os.rename(
                    candidate_parts[-1],
                    destination_parts[-1],
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
                return
            raise SafeIOError("atomic directory no-replace is unavailable on this platform")
        except FileExistsError as exc:
            raise ConcurrentModificationError(f"publish destination already exists: {destination}") from exc


@contextlib.contextmanager
def locked_repository(root: Path, lock_name: str = ".dev-standard-write.lock") -> Iterator[None]:
    """Take an advisory repository-local lock through a no-follow open."""

    lexical_root = _absolute_lexical(root)
    _, parts = _relative_parts(lexical_root, lexical_root / lock_name)
    with trusted_root(lexical_root) as root_fd:
        with _locked_repository_at(root_fd, parts):
            yield


@contextlib.contextmanager
def locked_repository_pinned(
    root: Path,
    root_fd: int,
    lock_name: str = ".dev-standard-write.lock",
) -> Iterator[None]:
    """Lock through a root descriptor pinned by the enclosing transaction."""

    lexical_root = _absolute_lexical(root)
    _, parts = _relative_parts(lexical_root, lexical_root / lock_name)
    with _locked_repository_at(root_fd, parts):
        yield


@contextlib.contextmanager
def _locked_repository_at(root_fd: int, lock_parts: tuple[str, ...]) -> Iterator[None]:
    """Lock below an already pinned root for a complete transaction."""

    with _parent_fd_at(root_fd, lock_parts, create=True) as (parent_fd, name):
        try:
            descriptor = os.open(name, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise UnsafePathError(f"lock path is symlinked or unsafe: {'/'.join(lock_parts)}") from exc
            raise
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise UnsafePathError(
                    f"lock path is not a regular file: {'/'.join(lock_parts)}"
                )
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _renameat2(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> bool:
    if not sys.platform.startswith("linux"):
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        return False
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    result = rename(
        source_fd,
        os.fsencode(source),
        destination_fd,
        os.fsencode(destination),
        flags,
    )
    if result == 0:
        return True
    error = ctypes.get_errno()
    if error in {errno.ENOSYS, errno.EINVAL}:
        return False
    raise OSError(error, os.strerror(error), destination)


def _renameatx_np(
    source_fd: int,
    source: str,
    destination_fd: int,
    destination: str,
    flags: int,
) -> bool:
    """Use macOS's atomic rename primitive when available."""

    if sys.platform != "darwin":
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameatx_np", None)
    if rename is None:
        return False
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    result = rename(
        source_fd,
        os.fsencode(source),
        destination_fd,
        os.fsencode(destination),
        flags,
    )
    if result == 0:
        return True
    error = ctypes.get_errno()
    if error in {errno.ENOSYS, errno.EINVAL, getattr(errno, "ENOTSUP", errno.EINVAL)}:
        return False
    raise OSError(error, os.strerror(error), destination)


def _write_staged(parent_fd: int, destination_name: str, content: bytes, mode: int) -> str:
    temporary = f".{destination_name}.safeio-{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, _FILE_CREATE_FLAGS, mode, dir_fd=parent_fd)
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary, dir_fd=parent_fd)
        raise
    finally:
        os.close(descriptor)
    return temporary


def _publish_missing(parent_fd: int, temporary: str, destination: str) -> None:
    if _renameat2(parent_fd, temporary, parent_fd, destination, _RENAME_NOREPLACE):
        return
    if _renameatx_np(parent_fd, temporary, parent_fd, destination, _RENAME_EXCL_DARWIN):
        return
    # Hard-link publication is an atomic no-replace operation for regular
    # files and works on POSIX systems without renameat2.
    os.link(temporary, destination, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
    os.unlink(temporary, dir_fd=parent_fd)


def _exchange_existing(parent_fd: int, temporary: str, destination: str) -> None:
    if _renameat2(parent_fd, temporary, parent_fd, destination, _RENAME_EXCHANGE):
        return
    if _renameatx_np(parent_fd, temporary, parent_fd, destination, _RENAME_SWAP_DARWIN):
        return
    # Refuse an unsafe fallback instead of silently weakening CAS semantics.
    raise SafeIOError("atomic exchange is unavailable on this platform")


def _unlink_if_present(parent_fd: int, name: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.unlink(name, dir_fd=parent_fd)


def atomic_write_cas(
    path: Path,
    content: bytes,
    expected: FileSnapshot,
    *,
    root: Path,
    lock_name: str = ".dev-standard-write.lock",
    mode: int = 0o644,
    read_preconditions: Mapping[Path, FileSnapshot] | None = None,
) -> None:
    """Atomically write one file only if ``expected`` still matches."""

    atomic_batch_write_cas(
        {path: content},
        {path: expected},
        root=root,
        lock_name=lock_name,
        mode=mode,
        read_preconditions=read_preconditions,
    )


def atomic_batch_write_cas(
    updates: Mapping[Path, bytes],
    expected: Mapping[Path, FileSnapshot],
    *,
    root: Path,
    lock_name: str = ".dev-standard-write.lock",
    mode: int = 0o644,
    modes: Mapping[Path, int] | None = None,
    publication_order: list[Path] | None = None,
    pinned_root_fd: int | None = None,
    read_preconditions: Mapping[Path, FileSnapshot] | None = None,
) -> None:
    """Publish a batch after validating every initial snapshot.

    On Linux, existing files use ``renameat2(RENAME_EXCHANGE)``.  The exact
    previous file remains staged until the whole batch succeeds, which makes
    rollback possible and detects a non-cooperating writer at the publication
    boundary.  Missing files use atomic no-replace publication.
    """

    if set(updates) != set(expected):
        raise SafeIOError("updates and expected snapshots must name the same files")
    if modes is not None and set(modes) != set(updates):
        raise SafeIOError("per-file modes must name the same files as updates")
    if publication_order is not None and set(publication_order) != set(updates):
        raise SafeIOError("publication order must name every update exactly once")
    read_preconditions = read_preconditions or {}
    normalized: list[tuple[Path, bytes, FileSnapshot, int]] = []
    seen: set[tuple[str, ...]] = set()
    for raw_path, content in updates.items():
        path = _absolute_lexical(raw_path)
        _, parts = _relative_parts(root, path)
        if parts in seen:
            raise SafeIOError(f"duplicate output path: {path}")
        seen.add(parts)
        normalized.append((path, bytes(content), expected[raw_path], modes[raw_path] if modes else mode))
    normalized_reads: list[tuple[Path, FileSnapshot]] = []
    read_seen: set[tuple[str, ...]] = set()
    for raw_path, before in read_preconditions.items():
        path = _absolute_lexical(raw_path)
        _, parts = _relative_parts(root, path)
        if parts in read_seen:
            raise SafeIOError(f"duplicate read precondition path: {path}")
        if parts in seen:
            raise SafeIOError(f"read precondition overlaps an output path: {path}")
        read_seen.add(parts)
        normalized_reads.append((path, before))
    normalized_reads.sort(key=lambda item: str(item[0]))
    if publication_order is None:
        normalized.sort(key=lambda item: str(item[0]))
    else:
        order = {_absolute_lexical(path): index for index, path in enumerate(publication_order)}
        if len(order) != len(publication_order):
            raise SafeIOError("publication order contains duplicate paths")
        normalized.sort(key=lambda item: order[item[0]])

    lexical_root = _absolute_lexical(root)
    _, lock_parts = _relative_parts(lexical_root, lexical_root / lock_name)
    @contextlib.contextmanager
    def root_descriptor() -> Iterator[int]:
        if pinned_root_fd is None:
            with trusted_root(lexical_root) as descriptor:
                yield descriptor
        else:
            descriptor = os.dup(pinned_root_fd)
            try:
                yield descriptor
            finally:
                os.close(descriptor)

    with root_descriptor() as root_fd, _locked_repository_at(root_fd, lock_parts):
        def validate_reads(phase: str) -> None:
            for path, before in normalized_reads:
                _, parts = _relative_parts(lexical_root, path)
                try:
                    with _parent_fd_at(root_fd, parts) as (parent_fd, name):
                        current = _snapshot_at(parent_fd, name)
                except FileNotFoundError:
                    current = MISSING
                if current != before:
                    raise ConcurrentModificationError(
                        f"read precondition changed {phase}: {path}"
                    )

        validate_reads("before publication")
        for path, _, before, _ in normalized:
            _, parts = _relative_parts(lexical_root, path)
            try:
                with _parent_fd_at(root_fd, parts) as (parent_fd, name):
                    current = _snapshot_at(parent_fd, name)
            except FileNotFoundError:
                current = MISSING
            if current != before:
                raise ConcurrentModificationError(f"file changed before publication: {path}")

        committed: list[tuple[int, str, str, bool]] = []
        opened: list[int] = []
        try:
            for path, content, before, requested_mode in normalized:
                _, parts = _relative_parts(lexical_root, path)
                with _parent_fd_at(root_fd, parts, create=True) as (borrowed_fd, name):
                    parent_fd = os.dup(borrowed_fd)
                opened.append(parent_fd)
                current = _snapshot_at(parent_fd, name)
                if current != before:
                    raise ConcurrentModificationError(f"file changed while staging publication: {path}")
                if current.exists and current.sha256 == hashlib.sha256(content).hexdigest():
                    continue
                output_mode = current.mode if current.exists and current.mode is not None else requested_mode
                temporary = _write_staged(parent_fd, name, content, output_mode)
                try:
                    if current.exists:
                        _exchange_existing(parent_fd, temporary, name)
                        displaced = _snapshot_at(parent_fd, temporary)
                        if displaced != before:
                            # Restore the displaced writer's value. The second
                            # exchange preserves any simultaneous current value
                            # in ``temporary`` rather than unlinking it.
                            _exchange_existing(parent_fd, temporary, name)
                            raise ConcurrentModificationError(f"file changed at publication boundary: {path}")
                        committed.append((parent_fd, name, temporary, True))
                    else:
                        try:
                            _publish_missing(parent_fd, temporary, name)
                        except FileExistsError as exc:
                            raise ConcurrentModificationError(f"file appeared at publication boundary: {path}") from exc
                        committed.append((parent_fd, name, temporary, False))
                    os.fsync(parent_fd)
                except BaseException:
                    _unlink_if_present(parent_fd, temporary)
                    raise
            # A generator may have spent significant time deriving output
            # after taking the read snapshots.  Revalidate the complete read
            # set after publication while displaced output bytes are still
            # retained, so any drift rolls the whole batch back.
            validate_reads("during publication")
        except BaseException:
            for parent_fd, name, temporary, existed in reversed(committed):
                try:
                    if existed:
                        _exchange_existing(parent_fd, temporary, name)
                        # ``temporary`` now contains the rolled-back new value.
                        _unlink_if_present(parent_fd, temporary)
                    else:
                        _unlink_if_present(parent_fd, name)
                    os.fsync(parent_fd)
                except (OSError, SafeIOError):
                    # Preserve the displaced bytes for explicit recovery when
                    # a non-cooperating writer makes rollback ambiguous.
                    continue
            raise
        else:
            for parent_fd, _, temporary, existed in committed:
                if existed:
                    _unlink_if_present(parent_fd, temporary)
                os.fsync(parent_fd)
        finally:
            for descriptor in opened:
                os.close(descriptor)
