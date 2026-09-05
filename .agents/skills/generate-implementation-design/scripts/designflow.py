#!/usr/bin/env python3
"""Generate drift-detectable detailed design from FastAPI and CloudFormation artifacts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import types
import uuid
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - environment contract
    yaml = None
try:
    import sqlglot
    from sqlglot import exp
    from sqlglot.optimizer.scope import traverse_scope
except ImportError:  # pragma: no cover - environment contract
    sqlglot = exp = traverse_scope = None


class DesignError(RuntimeError):
    pass


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
MANAGED_BY = "dev-standard-designflow"
MANIFEST_SCHEMA_VERSION = 2
_EXPLICIT_REPOSITORY_ROOT: Path | None = None
UNSUPPORTED_FLOW_NODES = (
    ast.BoolOp,
    ast.comprehension,
    ast.For,
    ast.GeneratorExp,
    ast.IfExp,
    ast.Lambda,
    ast.ListComp,
    ast.Match,
    ast.NamedExpr,
    ast.SetComp,
    ast.DictComp,
    ast.Try,
    ast.While,
    ast.With,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Yield,
    ast.YieldFrom,
)


@cache
def _load_safe_io_module(repository_root: Path) -> Any:
    """Load the repository's bundled safe I/O module without following links.

    This small descriptor walk is the bootstrap boundary.  All subsequent
    tree validation and regular-file reads use ``tools/safe_io.py`` itself.
    """

    portable = sys.modules.get("_dev_standard_portable_imports")
    if portable is not None:
        return portable.load_relative(
            "tools/safe_io.py",
            "dev_standard_designflow_safe_io",
        )
    repository_root = repository_root.absolute()
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(os.sep, directory_flags)
    try:
        for component in repository_root.parts[1:]:
            next_descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        tools_descriptor = os.open("tools", directory_flags, dir_fd=descriptor)
        try:
            source_descriptor = os.open("safe_io.py", file_flags, dir_fd=tools_descriptor)
            try:
                info = os.fstat(source_descriptor)
                if not stat.S_ISREG(info.st_mode):
                    raise DesignError("tools/safe_io.py must be a regular file")
                chunks: list[bytes] = []
                while chunk := os.read(source_descriptor, 1024 * 1024):
                    chunks.append(chunk)
            finally:
                os.close(source_descriptor)
        finally:
            os.close(tools_descriptor)
    except OSError as exc:
        raise DesignError(f"cannot load no-follow I/O runtime: {exc}") from exc
    finally:
        os.close(descriptor)
    module_name = "dev_standard_designflow_safe_io"
    module = types.ModuleType(module_name)
    module.__file__ = str(repository_root / "tools" / "safe_io.py")
    sys.modules[module_name] = module
    try:
        exec(compile(b"".join(chunks), module.__file__, "exec"), module.__dict__)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise DesignError(f"cannot initialize no-follow I/O runtime: {exc}") from exc
    return module


def _bootstrap_safe_io(repository_root: Path) -> Any:
    """Return safe I/O and rebind every portable call to its receipt root."""

    safe_io = _load_safe_io_module(repository_root)
    portable = sys.modules.get("_dev_standard_portable_imports")
    if portable is None:
        return safe_io
    expected = tuple(portable.root_identity)
    try:
        safe_io.bind_root_identity(repository_root, expected)
        with safe_io.trusted_root(repository_root) as root_descriptor:
            root_info = os.fstat(root_descriptor)
        if (root_info.st_dev, root_info.st_ino) != expected:
            raise safe_io.ConcurrentModificationError("portable root identity mismatch")
    except safe_io.ConcurrentModificationError as exc:
        raise DesignError(
            "portable repository root changed after receipt validation"
        ) from exc
    except (OSError, safe_io.SafeIOError) as exc:
        raise DesignError(f"cannot bind portable repository root: {exc}") from exc
    return safe_io


def validate_input_tree(root: Path, repository_root: Path) -> Path:
    """Return an existing repository-local tree after no-follow validation."""

    repository_root = repository_root.absolute()
    lexical = root if root.is_absolute() else repository_root / root
    try:
        lexical.relative_to(repository_root)
    except ValueError as exc:
        raise DesignError(f"input tree escapes repository: {root}") from exc
    safe_io = _bootstrap_safe_io(repository_root)
    try:
        safe_io.validate_tree_nofollow(lexical, root=repository_root)
    except (OSError, safe_io.SafeIOError) as exc:
        raise DesignError(f"unsafe input tree {root}: {exc}") from exc
    return lexical


def regular_files(
    root: Path,
    repository_root: Path,
    *,
    suffix: str | None = None,
    name: str | None = None,
    name_prefix: str | None = None,
) -> list[Path]:
    """List a no-follow validated tree using a bounded filename predicate."""

    lexical = validate_input_tree(root, repository_root)
    result: list[Path] = []
    for path in lexical.rglob("*"):
        if not path.is_file():
            continue
        if suffix is not None and path.suffix.lower() != suffix.lower():
            continue
        if name is not None and path.name != name:
            continue
        if name_prefix is not None and not path.name.startswith(name_prefix):
            continue
        result.append(path)
    return sorted(result)


class RuntimeCallOrder(ast.NodeVisitor):
    """Collect calls in Python evaluation order rather than AST breadth order."""

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        self.visit(node.func)
        for argument in node.args:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)
        self.calls.append(node)


def dotted_name(node: ast.AST) -> str:
    """Return a stable dotted name for a name or attribute expression."""

    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def root_name(node: ast.AST) -> str:
    """Return the root binding of a dotted expression."""

    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def sha(path: Path) -> str:
    repository_root = find_repository_root(path)
    safe_io = _bootstrap_safe_io(repository_root)
    try:
        content = safe_io.read_bytes_nofollow(path, root=repository_root)
    except (OSError, safe_io.SafeIOError) as exc:
        raise DesignError(f"cannot read source without following links: {path}: {exc}") from exc
    return hashlib.sha256(content).hexdigest()


def read_text_nofollow(path: Path) -> str:
    """Read one repository file as UTF-8 without following any path component."""

    repository_root = find_repository_root(path)
    safe_io = _bootstrap_safe_io(repository_root)
    try:
        return safe_io.read_bytes_nofollow(path, root=repository_root).decode("utf-8")
    except (OSError, UnicodeDecodeError, safe_io.SafeIOError) as exc:
        raise DesignError(
            f"cannot read source without following links: {path}: {exc}"
        ) from exc


def find_repository_root(start: Path | None = None) -> Path:
    """Return the repository root without relying on the installed Skill path."""

    if _EXPLICIT_REPOSITORY_ROOT is not None:
        current = (start or Path.cwd()).absolute()
        try:
            current.relative_to(_EXPLICIT_REPOSITORY_ROOT)
        except ValueError as exc:
            raise DesignError(
                f"path escapes the explicit repository root: {current}"
            ) from exc
        return _EXPLICIT_REPOSITORY_ROOT
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise DesignError("repository root not found; run inside a Git repository or pass --repo-root")


def validate_output_path(out: Path, repository_root: Path) -> tuple[Path, Path]:
    """Return a lexical generated path without creating or resolving ancestors."""

    repository_root = repository_root.absolute()
    generated_root = repository_root / "docs" / "design" / "generated"
    lexical = repository_root / out if not out.is_absolute() else out
    try:
        relative = lexical.relative_to(generated_root)
    except ValueError as exc:
        raise DesignError(f"output must be a bundle below {generated_root}: {out}") from exc
    if not relative.parts:
        raise DesignError(f"output must be a bundle below {generated_root}: {out}")
    return lexical, generated_root


def validate_existing_output_path(
    out: Path, repository_root: Path
) -> tuple[Path, tuple[int, int, str]]:
    """Validate a managed output path without creating or changing anything."""

    repository_root = repository_root.absolute()
    generated_root = repository_root / "docs" / "design" / "generated"
    lexical = out if out.is_absolute() else repository_root / out
    try:
        lexical.relative_to(generated_root)
    except ValueError as exc:
        raise DesignError(f"output must be a bundle below {generated_root}: {out}") from exc
    if lexical == generated_root:
        raise DesignError(f"output must be a bundle below {generated_root}: {out}")
    safe_io = _bootstrap_safe_io(repository_root)
    try:
        safe_io.validate_tree_nofollow(lexical, root=repository_root)
    except (OSError, safe_io.SafeIOError) as exc:
        raise DesignError(f"unsafe or missing generated bundle {out}: {exc}") from exc
    identity = validate_managed_bundle(lexical, repository_root)
    return lexical, identity


def pinned_directory_identity(
    descriptor: int,
    *,
    display: Path,
    safe_io: Any,
) -> tuple[int, int, str]:
    """Return a stable identity for an already pinned no-follow directory."""

    before = os.fstat(descriptor)
    digest = safe_io.tree_digest_fd_nofollow(descriptor, display=display)
    after = os.fstat(descriptor)
    stable_fields = ("st_dev", "st_ino", "st_mode", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
        raise DesignError(f"generated bundle changed while it was inspected: {display}")
    return before.st_dev, before.st_ino, digest


def validate_managed_bundle(
    out: Path,
    repository_root: Path | None = None,
) -> tuple[int, int, str]:
    """Allow replacement only for a bundle previously owned by this generator."""

    repository_root = repository_root or find_repository_root(out)
    safe_io = _bootstrap_safe_io(repository_root)
    try:
        with safe_io.directory_nofollow(out, root=repository_root) as descriptor:
            identity_before = pinned_directory_identity(
                descriptor,
                display=out,
                safe_io=safe_io,
            )
            file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                manifest_descriptor = os.open(
                    "manifest.json",
                    file_flags,
                    dir_fd=descriptor,
                )
            except FileNotFoundError as exc:
                raise DesignError(f"refusing to replace unmanaged directory: {out}") from exc
            try:
                manifest_content, _ = safe_io._read_open_file(manifest_descriptor)
            finally:
                os.close(manifest_descriptor)
            try:
                manifest = json.loads(manifest_content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DesignError(
                    f"generated bundle manifest is invalid: {out / 'manifest.json'}"
                ) from exc
            if (
                manifest.get("managed_by") != MANAGED_BY
                or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
            ):
                raise DesignError(
                    f"refusing to replace bundle with an unknown manifest: {out}"
                )
            generated = manifest.get("generated")
            if (
                not isinstance(generated, list)
                or not all(isinstance(item, str) for item in generated)
                or len(generated) != len(set(generated))
                or any(
                    not item
                    or item == "manifest.json"
                    or Path(item).name != item
                    for item in generated
                )
            ):
                raise DesignError(f"generated bundle manifest file list is invalid: {out}")
            expected = {"manifest.json", *generated}
            actual: set[str] = set()
            for name in os.listdir(descriptor):
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    raise DesignError(
                        f"managed bundle contains a non-regular entry: {out / name}"
                    )
                actual.add(name)
            if actual != expected:
                raise DesignError(f"managed bundle file set differs from manifest: {out}")
            identity_after = pinned_directory_identity(
                descriptor,
                display=out,
                safe_io=safe_io,
            )
            if identity_after != identity_before:
                raise DesignError(f"generated bundle changed while it was inspected: {out}")
            return identity_after
    except DesignError:
        raise
    except (OSError, safe_io.SafeIOError) as exc:
        raise DesignError(
            f"generated bundle contains an unsafe entry: {out}: {exc}"
        ) from exc


def display_call(call: ast.Call) -> str:
    return dotted_name(call.func) or "call"


def literal(node: ast.AST | None, default: Any = None) -> Any:
    """Return a literal value while refusing executable expressions."""

    if node is None:
        return default
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def scoped_walk(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Walk one callable without treating uncalled nested definitions as flow."""

    result: list[ast.AST] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is function:
                for statement in node.body:
                    self.visit(statement)
                return
            result.append(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is function:
                for statement in node.body:
                    self.visit(statement)
                return
            result.append(node)

        def generic_visit(self, node: ast.AST) -> None:
            result.append(node)
            super().generic_visit(node)

    Visitor().visit(function)
    return result


def supported_assignment_target(node: ast.AST) -> bool:
    """Return whether assignment target evaluation has no hidden runtime calls."""

    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Starred):
        return supported_assignment_target(node.value)
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(supported_assignment_target(item) for item in node.elts)
    return False


def assignment_target_names(node: ast.AST) -> set[str]:
    """Return names bound by a supported assignment target."""

    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Starred):
        return assignment_target_names(node.value)
    if isinstance(node, (ast.List, ast.Tuple)):
        return set().union(*(assignment_target_names(item) for item in node.elts))
    return set()


def dynamic_call_bindings(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    """Return local names whose callable value cannot be resolved statically."""

    names = {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }
    for argument in (function.args.vararg, function.args.kwarg):
        if argument is not None:
            names.add(argument.arg)
    for node in scoped_walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(assignment_target_names(target))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            names.update(assignment_target_names(node.target))
    return names


def validate_supported_flow(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    source: Path,
) -> None:
    """Reject syntax that cannot be projected to the bundled structured CFG."""

    dynamic_bindings = dynamic_call_bindings(function)
    for node in scoped_walk(function):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            raise DesignError(
                f"{source}:{function.name}:{node.lineno}: nested definitions are unsupported"
            )
        if isinstance(node, UNSUPPORTED_FLOW_NODES):
            raise DesignError(
                f"{source}:{function.name}:{node.lineno}: unsupported flow node "
                f"{type(node).__name__}"
            )
        if isinstance(node, ast.Call) and (
            not dotted_name(node.func)
            or root_name(node.func) in dynamic_bindings
        ):
            raise DesignError(
                f"{source}:{function.name}:{node.lineno}: dynamic call target is unsupported"
            )
        if isinstance(node, ast.Assign) and any(
            not supported_assignment_target(target) for target in node.targets
        ):
            raise DesignError(
                f"{source}:{function.name}:{node.lineno}: unsupported assignment target"
            )
        if isinstance(node, (ast.AnnAssign, ast.AugAssign)) and not supported_assignment_target(
            node.target
        ):
            raise DesignError(
                f"{source}:{function.name}:{node.lineno}: unsupported assignment target"
            )


def calls_in_evaluation_order(node: ast.AST | None) -> list[ast.Call]:
    """Collect calls from one non-branching expression in evaluation order."""

    if node is None:
        return []
    collector = RuntimeCallOrder()
    collector.visit(node)
    return collector.calls


def statement_expressions(statement: ast.stmt) -> list[ast.AST]:
    """Return expression roots in runtime order for supported simple statements."""

    if isinstance(statement, ast.Assign):
        return [statement.value]
    if isinstance(statement, ast.AnnAssign):
        return [statement.value] if statement.value is not None else []
    if isinstance(statement, ast.AugAssign):
        return [statement.target, statement.value]
    if isinstance(statement, ast.Expr):
        return [statement.value]
    if isinstance(statement, ast.Return):
        return [statement.value] if statement.value is not None else []
    if isinstance(statement, ast.Raise):
        return [node for node in (statement.exc, statement.cause) if node is not None]
    if isinstance(statement, ast.Assert):
        return [node for node in (statement.test, statement.msg) if node is not None]
    if isinstance(statement, (ast.Pass, ast.Break, ast.Continue)):
        return []
    raise DesignError(
        f"line {getattr(statement, 'lineno', '?')}: unsupported statement "
        f"{type(statement).__name__}"
    )


def call_sql_literals(call: ast.Call) -> list[str]:
    """Return literal SQL paths passed to an actually evaluated call."""

    result: list[str] = []
    for argument in (*call.args, *(keyword.value for keyword in call.keywords)):
        result.extend(
            child.value
            for child in ast.walk(argument)
            if isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and child.value.lower().endswith(".sql")
        )
    return result


def expand_call_flow(
    call: ast.Call,
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    helper_source: Path,
    *,
    stack: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[str], list[str], set[str]]:
    """Expand one statically named helper call into structured flow."""

    name = display_call(call)
    own_literals = call_sql_literals(call)
    helper_name = name.removeprefix("functions.") if name.startswith("functions.") else name
    helper = helpers.get(helper_name) if "." not in helper_name else None
    if helper is None:
        return [{"kind": "call", "name": name}], [name], own_literals, set()
    if helper_name in stack:
        cycle = " -> ".join((*stack, helper_name))
        raise DesignError(f"recursive helper call cannot be expanded: {cycle}")
    validate_supported_flow(helper, source=helper_source)
    helper_raise = next(
        (node for node in scoped_walk(helper) if isinstance(node, ast.Raise)),
        None,
    )
    if helper_raise is not None:
        raise DesignError(
            f"{helper_source}:{helper.name}:{helper_raise.lineno}: "
            "interprocedural helper raise is unsupported"
        )
    nested_flow, nested_calls, nested_literals, reached = structured_flow(
        helper.body,
        helpers,
        helper_source,
        stack=(*stack, helper_name),
        terminal_scope="helper",
    )
    return (
        [*nested_flow, {"kind": "call", "name": name}],
        [*nested_calls, name],
        [*nested_literals, *own_literals],
        {helper_name, *reached},
    )


def structured_flow(
    statements: list[ast.stmt],
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    helper_source: Path,
    *,
    stack: tuple[str, ...] = (),
    terminal_scope: str = "route",
) -> tuple[list[dict[str, Any]], list[str], list[str], set[str]]:
    """Project the supported Python subset to a branch-preserving CFG."""

    flow, call_names, string_literals, reached_helpers, _ = _structured_flow_block(
        statements,
        helpers,
        helper_source,
        stack=stack,
        terminal_scope=terminal_scope,
    )
    return flow, call_names, string_literals, reached_helpers


def _structured_flow_block(
    statements: list[ast.stmt],
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    helper_source: Path,
    *,
    stack: tuple[str, ...],
    terminal_scope: str,
) -> tuple[list[dict[str, Any]], list[str], list[str], set[str], bool]:
    """Return one structured block and whether control can reach its end."""

    flow: list[dict[str, Any]] = []
    call_names: list[str] = []
    string_literals: list[str] = []
    reached_helpers: set[str] = set()
    for index, statement in enumerate(statements):
        if isinstance(statement, ast.If):
            condition_calls: list[dict[str, Any]] = []
            for call in calls_in_evaluation_order(statement.test):
                expanded, names, literals, reached = expand_call_flow(
                    call,
                    helpers,
                    helper_source,
                    stack=stack,
                )
                condition_calls.extend(expanded)
                call_names.extend(names)
                string_literals.extend(literals)
                reached_helpers.update(reached)
            then_flow, then_calls, then_literals, then_helpers, then_continues = _structured_flow_block(
                statement.body,
                helpers,
                helper_source,
                stack=stack,
                terminal_scope=terminal_scope,
            )
            else_flow, else_calls, else_literals, else_helpers, else_continues = _structured_flow_block(
                statement.orelse,
                helpers,
                helper_source,
                stack=stack,
                terminal_scope=terminal_scope,
            )
            condition = ast.unparse(statement.test)
            flow.extend(condition_calls)
            call_names.extend([*then_calls, *else_calls])
            string_literals.extend([*then_literals, *else_literals])
            reached_helpers.update(then_helpers | else_helpers)
            if then_continues != else_continues:
                remainder = statements[index + 1 :]
                (
                    remainder_flow,
                    remainder_calls,
                    remainder_literals,
                    remainder_helpers,
                    remainder_continues,
                ) = _structured_flow_block(
                    remainder,
                    helpers,
                    helper_source,
                    stack=stack,
                    terminal_scope=terminal_scope,
                )
                if then_continues:
                    then_flow.extend(remainder_flow)
                else:
                    else_flow.extend(remainder_flow)
                call_names.extend(remainder_calls)
                string_literals.extend(remainder_literals)
                reached_helpers.update(remainder_helpers)
                flow.append(
                    {
                        "kind": "branch",
                        "condition": condition,
                        "then": then_flow,
                        "else": else_flow,
                    }
                )
                return (
                    flow,
                    call_names,
                    string_literals,
                    reached_helpers,
                    remainder_continues,
                )
            flow.append(
                {
                    "kind": "branch",
                    "condition": condition,
                    "then": then_flow,
                    "else": else_flow,
                }
            )
            if not then_continues:
                if index + 1 < len(statements):
                    unreachable = statements[index + 1]
                    raise DesignError(
                        f"{helper_source}:{getattr(unreachable, 'lineno', '?')}: "
                        "unreachable flow after terminating branches"
                    )
                return flow, call_names, string_literals, reached_helpers, False
            continue
        for expression in statement_expressions(statement):
            for call in calls_in_evaluation_order(expression):
                expanded, names, literals, reached = expand_call_flow(
                    call,
                    helpers,
                    helper_source,
                    stack=stack,
                )
                flow.extend(expanded)
                call_names.extend(names)
                string_literals.extend(literals)
                reached_helpers.update(reached)
        if isinstance(statement, (ast.Return, ast.Raise)):
            flow.append(
                {
                    "kind": "terminal",
                    "type": "return" if isinstance(statement, ast.Return) else "raise",
                    "scope": terminal_scope,
                }
            )
            if index + 1 < len(statements):
                unreachable = statements[index + 1]
                raise DesignError(
                    f"{helper_source}:{getattr(unreachable, 'lineno', '?')}: "
                    f"unreachable flow after {type(statement).__name__}"
                )
            return flow, call_names, string_literals, reached_helpers, False
    return flow, call_names, string_literals, reached_helpers, True


def apirouter_prefixes(tree: ast.Module) -> dict[str, str]:
    """Extract literal APIRouter prefixes and reject dynamic routing authority."""

    prefixes: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or not isinstance(node.value, ast.Call):
            continue
        if not dotted_name(node.value.func).endswith("APIRouter"):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if len(names) != len(targets) or not names:
            raise DesignError("APIRouter must be assigned to a simple name")
        prefix_node = next((keyword.value for keyword in node.value.keywords if keyword.arg == "prefix"), None)
        prefix = literal(prefix_node, "")
        if not isinstance(prefix, str):
            raise DesignError(f"{names[0]}: APIRouter prefix must be a literal string")
        if prefix and (not prefix.startswith("/") or prefix.endswith("/")):
            raise DesignError(f"{names[0]}: APIRouter prefix must start with / and must not end with /")
        for name in names:
            if name in prefixes:
                raise DesignError(f"duplicate APIRouter authority: {name}")
            prefixes[name] = prefix
    return prefixes


def route_decorator(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    prefixes: dict[str, str] | None = None,
) -> tuple[str, str, dict[str, Any], bool] | None:
    prefixes = prefixes or {}
    discovered: list[tuple[str, str, dict[str, Any], bool]] = []
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        method = decorator.func.attr.lower()
        if method not in HTTP_METHODS:
            continue
        owner = dotted_name(decorator.func.value)
        router_name = owner.split(".")[-1]
        if not owner or router_name not in prefixes:
            raise DesignError(f"{function.name}: route router authority must be a local APIRouter")
        if len(decorator.args) != 1 or not isinstance(decorator.args[0], ast.Constant):
            raise DesignError(f"{function.name}: route path must be one literal argument")
        prefix = prefixes[router_name]
        route_path = decorator.args[0].value
        if not isinstance(route_path, str) or not route_path.startswith("/"):
            raise DesignError(f"{function.name}: route path must be a literal absolute path")
        metadata: dict[str, Any] = {}
        for keyword in decorator.keywords:
            if keyword.arg is None:
                raise DesignError(f"{function.name}: expanded route keyword arguments are unsupported")
            value = literal(keyword.value)
            if keyword.arg == "openapi_extra":
                if not isinstance(value, dict):
                    raise DesignError(
                        f"{function.name}: openapi_extra must be a literal mapping"
                    )
                metadata.update(value)
            elif keyword.arg == "operation_id" and not isinstance(value, str):
                raise DesignError(
                    f"{function.name}: operation_id must be a literal string"
                )
            elif value is not None:
                metadata[keyword.arg] = value
            else:
                raise DesignError(
                    f"{function.name}: route metadata must be literal: {keyword.arg}"
                )
        explicit_operation_id = bool(metadata.get("operation_id") or metadata.get("x-operation-id"))
        discovered.append(
            (method.upper(), prefix + route_path, metadata, explicit_operation_id)
        )
    if len(discovered) > 1:
        raise DesignError(f"{function.name}: multiple route decorators are unsupported")
    return discovered[0] if discovered else None


def helper_definitions(path: Path) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Parse a functions module into a unique top-level helper map."""

    try:
        tree = ast.parse(read_text_nofollow(path), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise DesignError(f"cannot parse helper module {path}: {exc}") from exc
    result: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in result:
            raise DesignError(f"{path}: duplicate helper definition: {node.name}")
        result[node.name] = node
    return result


def expanded_runtime(
    calls: list[ast.Call],
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    *,
    stack: tuple[str, ...] = (),
) -> tuple[list[str], list[str]]:
    """Expand local helper calls recursively while preserving evaluation order."""

    call_names: list[str] = []
    string_literals: list[str] = []
    for call in calls:
        name = display_call(call)
        helper_name = name.removeprefix("functions.") if name.startswith("functions.") else name
        helper = helpers.get(helper_name) if "." not in helper_name else None
        if helper is not None:
            if helper_name in stack:
                cycle = " -> ".join((*stack, helper_name))
                raise DesignError(f"recursive helper call cannot be expanded: {cycle}")
            collector = RuntimeCallOrder()
            for statement in helper.body:
                collector.visit(statement)
            nested_calls, nested_literals = expanded_runtime(
                collector.calls,
                helpers,
                stack=(*stack, helper_name),
            )
            call_names.extend(nested_calls)
            string_literals.extend(nested_literals)
            string_literals.extend(
                child.value
                for child in ast.walk(helper)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            )
        call_names.append(name)
    return call_names, string_literals


def is_external_call(name: str) -> bool:
    """Identify explicit external-client calls without importing target code."""

    parts = name.lower().split(".")
    return any(
        part in {"http", "httpx", "requests", "external", "service", "boto3"}
        or part.endswith(("client", "gateway", "publisher"))
        for part in parts[:-1]
    )


def is_mutating_external_call(name: str) -> bool:
    """Classify explicit external calls whose verb can change remote state."""

    if not is_external_call(name):
        return False
    verb = name.lower().split(".")[-1]
    return verb in {
        "create",
        "delete",
        "patch",
        "post",
        "publish",
        "put",
        "remove",
        "save",
        "send",
        "upsert",
        "update",
        "write",
    } or verb.startswith(
        (
            "create_",
            "delete_",
            "patch_",
            "post_",
            "publish_",
            "put_",
            "remove_",
            "save_",
            "send_",
            "update_",
            "upsert_",
            "write_",
        )
    )


def error_cases(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, Any]]:
    """Extract normalized error responses and derive stable IDs from explicit codes."""

    result: list[dict[str, Any]] = []
    for node in scoped_walk(function):
        if not isinstance(node, ast.Call) or not display_call(node).endswith("error_response"):
            continue
        keywords = {keyword.arg: literal(keyword.value) for keyword in node.keywords if keyword.arg}
        code = keywords.get("case_id") or keywords.get("code") or (literal(node.args[0]) if node.args else None)
        if not isinstance(code, str) or not code.strip():
            raise DesignError(f"{function.name}: error_response requires a literal code or case_id")
        normalized = re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-")
        if not normalized:
            raise DesignError(
                f"{function.name}: error_response code cannot form a stable global ID"
            )
        case_id = f"ERR-{normalized.upper()}"
        result.append(
            {
                "id": case_id,
                "code": code,
                "message_id": keywords.get("message_id") or "-",
                "status_code": keywords.get("status_code") or "-",
            }
        )
    ids = [item["id"] for item in result]
    if len(ids) != len(set(ids)):
        raise DesignError(f"{function.name}: duplicate normalized error case")
    return sorted(result, key=lambda item: item["id"])


def router_operations(path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(read_text_nofollow(path), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise DesignError(f"cannot parse router {path}: {exc}") from exc
    prefixes = apirouter_prefixes(tree)
    helpers_path = path.with_name("functions.py")
    helpers = helper_definitions(helpers_path) if helpers_path.is_file() else {}
    operations: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        route = route_decorator(node, prefixes)
        if route is None:
            continue
        validate_supported_flow(node, source=path)
        returns = [child for child in ast.walk(node) if isinstance(child, ast.Return)]
        if not node.body or not isinstance(node.body[-1], ast.Return):
            raise DesignError(f"{path}:{node.name}: route must end in a direct return")
        returned = node.body[-1].value
        if isinstance(returned, ast.Await):
            returned = returned.value
        if not isinstance(returned, ast.Call):
            raise DesignError(f"{path}:{node.name}: final return must directly call the response producer")
        if any(isinstance(ret.value, ast.Name) for ret in returns):
            raise DesignError(f"{path}:{node.name}: returning a response variable is forbidden")
        # Walk only the function body. Walking the function node also visits route
        # decorators, which are registration metadata rather than runtime calls.
        metadata = route[2]
        flow, call_names, string_literals, reached_helpers = structured_flow(
            node.body,
            helpers,
            helpers_path,
        )
        sql_files = sorted({value for value in string_literals if value.lower().endswith(".sql")})
        external_clients = sorted({name for name in call_names if is_external_call(name)})
        external_effects = sorted({name for name in call_names if is_mutating_external_call(name)})
        operation_id = metadata.get("operation_id") or metadata.get("x-operation-id") or node.name
        errors = error_cases(node)
        for helper_name in sorted(reached_helpers):
            errors.extend(error_cases(helpers[helper_name]))
        error_ids = [error["id"] for error in errors]
        if len(error_ids) != len(set(error_ids)):
            raise DesignError(f"{path}:{node.name}: duplicate reachable error case")
        operations.append(
            {
                "method": route[0],
                "path": route[1],
                "function": node.name,
                "operation_id": str(operation_id),
                "source": str(path),
                "docstring": (ast.get_docstring(node) or "-").splitlines()[0],
                "calls": call_names,
                "flow": flow,
                "sql_files": sql_files,
                "external_clients": external_clients,
                "external_effects": external_effects,
                "metadata": metadata,
                "operation_id_explicit": route[3],
                "errors": sorted(errors, key=lambda item: item["id"]),
            }
        )
    return operations


def validate_operation_set(operations: list[dict[str, Any]]) -> None:
    """Reject ambiguous handler routes and operation identities."""

    routes: dict[tuple[str, str], str] = {}
    operation_ids: dict[str, tuple[str, str]] = {}
    error_ids: dict[str, str] = {}
    for operation in operations:
        route = (str(operation["method"]), str(operation["path"]))
        operation_id = str(operation["operation_id"])
        if route in routes:
            raise DesignError(
                f"duplicate handler route: {route[0]} {route[1]} "
                f"({routes[route]}, {operation_id})"
            )
        if operation_id in operation_ids:
            previous = operation_ids[operation_id]
            raise DesignError(
                f"duplicate handler operation ID: {operation_id} "
                f"({previous[0]} {previous[1]}, {route[0]} {route[1]})"
            )
        routes[route] = operation_id
        operation_ids[operation_id] = route
        for error in operation.get("errors", []):
            error_id = str(error["id"])
            if error_id in error_ids:
                raise DesignError(
                    f"duplicate global error case ID: {error_id} "
                    f"({error_ids[error_id]}, {operation_id})"
                )
            error_ids[error_id] = operation_id


def render_flow_steps(
    flow: list[dict[str, Any]],
    participants: dict[str, str],
    *,
    indent: str,
) -> list[str]:
    """Render a branch-preserving flow into Mermaid sequence statements."""

    lines: list[str] = []
    for step in flow:
        if step["kind"] == "call":
            participant = participants[str(step["name"])]
            lines.append(f"{indent}Router->>{participant}: call")
            lines.append(f"{indent}{participant}-->>Router: result")
            continue
        if step["kind"] == "terminal":
            lines.append(
                f"{indent}Note over Router: {step['scope']} {step['type']}"
            )
            continue
        lines.append(f"{indent}alt {step['condition']}")
        lines.extend(render_flow_steps(step["then"], participants, indent=indent + "    "))
        lines.append(f"{indent}else otherwise")
        if step["else"]:
            lines.extend(render_flow_steps(step["else"], participants, indent=indent + "    "))
        else:
            lines.append(f"{indent}    Note over Router: no operation")
        lines.append(f"{indent}end")
    return lines


def render_sequences(operations: list[dict[str, Any]]) -> str:
    lines = ["# FastAPI operation sequences"]
    for operation in operations:
        lines += ["", f"## {operation['method']} {operation['path']} — `{operation['function']}`", "", "```mermaid", "sequenceDiagram", "    participant Client", "    participant Router"]
        call_names = list(dict.fromkeys(operation["calls"]))
        participants = {name: f"F{index}" for index, name in enumerate(call_names, 1)}
        for name in call_names:
            lines.append(f"    participant {participants[name]} as {name}")
        lines.append(f"    Client->>Router: {operation['method']} {operation['path']}")
        lines.extend(render_flow_steps(operation["flow"], participants, indent="    "))
        lines += ["    Router-->>Client: response", "```"]
    return "\n".join(lines) + "\n"


def load_structured(path: Path) -> Any:
    repository_root = find_repository_root(path)
    safe_io = _bootstrap_safe_io(repository_root)
    try:
        text = safe_io.read_bytes_nofollow(path, root=repository_root).decode("utf-8")
    except (OSError, UnicodeDecodeError, safe_io.SafeIOError) as exc:
        raise DesignError(f"cannot read structured input without following links: {path}: {exc}") from exc
    if path.suffix.lower() == ".json":
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise DesignError(f"duplicate JSON mapping key in {path}: {key}")
                result[key] = value
            return result

        return json.loads(text, object_pairs_hook=unique_object)
    if yaml is None:
        raise DesignError("PyYAML is required for YAML input")

    class Loader(yaml.SafeLoader):
        pass

    def unique_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
        loader.flatten_mapping(node)
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                duplicate = key in result
            except TypeError as exc:
                raise DesignError(f"unhashable YAML mapping key in {path}") from exc
            if duplicate:
                raise DesignError(f"duplicate YAML mapping key in {path}: {key}")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

    def unknown(loader: Any, tag_suffix: str, node: Any) -> Any:
        if isinstance(node, yaml.ScalarNode):
            return {"tag": tag_suffix, "value": loader.construct_scalar(node)}
        if isinstance(node, yaml.SequenceNode):
            return {"tag": tag_suffix, "value": loader.construct_sequence(node)}
        return {"tag": tag_suffix, "value": loader.construct_mapping(node)}

    Loader.add_multi_constructor("!", unknown)
    return yaml.load(text, Loader=Loader)


def ref_name(value: Any) -> str:
    if isinstance(value, dict) and "$ref" in value:
        return str(value["$ref"]).rsplit("/", 1)[-1]
    if isinstance(value, dict):
        return str(value.get("type") or value.get("content") or "inline")
    return "-"


def load_api_samples(source_root: Path) -> dict[str, Any]:
    """Load literal API_SAMPLES mappings without importing application code."""

    samples: dict[str, Any] = {}
    repository_root = find_repository_root(source_root)
    for path in regular_files(source_root, repository_root, name="samples.py"):
        try:
            tree = ast.parse(read_text_nofollow(path), filename=str(path))
        except (OSError, SyntaxError) as exc:
            raise DesignError(f"cannot parse samples {path}: {exc}") from exc
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value_node = node.value
            if any(isinstance(target, ast.Name) and target.id == "API_SAMPLES" for target in targets):
                value = literal(value_node)
                if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
                    raise DesignError(f"{path}: API_SAMPLES must be a literal string-keyed mapping")
                duplicates = set(samples).intersection(value)
                if duplicates:
                    raise DesignError(f"duplicate API sample keys: {sorted(duplicates)}")
                samples.update(value)
    return dict(sorted(samples.items()))


def operation_extensions(operation: dict[str, Any], handler: dict[str, Any] | None) -> dict[str, Any]:
    extensions = {key: value for key, value in operation.items() if key.startswith("x-")}
    if handler:
        handler_extensions = {
            key: value
            for key, value in handler.get("metadata", {}).items()
            if key.startswith("x-")
        }
        for key in sorted(set(handler_extensions).intersection(extensions)):
            if handler_extensions[key] != extensions[key]:
                raise DesignError(
                    f"metadata conflict for {handler['method']} {handler['path']}: {key}"
                )
        extensions = {**handler_extensions, **extensions}
    return extensions


def openapi_operations(document: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Return unique, inline OpenAPI operations in a stable order."""

    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        raise DesignError("OpenAPI document requires a paths mapping")
    operations: list[tuple[str, str, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for path, item in sorted(document["paths"].items()):
        if not isinstance(path, str) or not path.startswith("/") or not isinstance(item, dict):
            raise DesignError(f"unsupported OpenAPI path item: {path}")
        if "$ref" in item:
            raise DesignError(f"referenced OpenAPI path items are unsupported: {path}")
        for method, operation in sorted(item.items()):
            if method.lower() not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                raise DesignError(f"OpenAPI operation must be inline: {method.upper()} {path}")
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id.strip():
                raise DesignError(f"OpenAPI operationId is required: {method.upper()} {path}")
            if operation_id in seen_ids:
                raise DesignError(f"duplicate OpenAPI operationId: {operation_id}")
            seen_ids.add(operation_id)
            operations.append((method.upper(), path, operation))
    if not operations:
        raise DesignError("OpenAPI document has no supported operations")
    return operations


def openapi_parameters(
    path: str,
    path_item: dict[str, Any],
    operation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Resolve the supported inline path/query/header parameter projection."""

    combined: dict[tuple[str, str], dict[str, Any]] = {}
    for owner, raw_parameters in (
        (f"path {path}", path_item.get("parameters", [])),
        (f"operation {operation.get('operationId', '-')} ", operation.get("parameters", [])),
    ):
        if not isinstance(raw_parameters, list):
            raise DesignError(f"OpenAPI parameters must be an array: {owner}")
        local: set[tuple[str, str]] = set()
        for parameter in raw_parameters:
            if not isinstance(parameter, dict) or "$ref" in parameter:
                raise DesignError(f"OpenAPI parameter must be inline: {owner}")
            name = parameter.get("name")
            location = parameter.get("in")
            if not isinstance(name, str) or not name.strip() or location not in {"path", "query", "header"}:
                raise DesignError(f"unsupported OpenAPI parameter: {owner}")
            key = (str(location), name.lower() if location == "header" else name)
            if key in local:
                raise DesignError(f"duplicate OpenAPI parameter: {location} {name}: {owner}")
            local.add(key)
            required = parameter.get("required", False)
            if not isinstance(required, bool) or (location == "path" and not required):
                raise DesignError(f"path parameters must declare required=true: {name}")
            schema = parameter.get("schema", {})
            if not isinstance(schema, dict):
                raise DesignError(f"OpenAPI parameter schema must be a mapping: {location} {name}")
            combined[key] = {
                "name": name,
                "in": location,
                "required": required,
                "schema": ref_name(schema),
                "description": parameter.get("description", "-"),
            }
    declared_path_names = {
        item["name"] for item in combined.values() if item["in"] == "path"
    }
    templated_path_names = set(re.findall(r"\{([^{}]+)\}", path))
    if declared_path_names != templated_path_names:
        raise DesignError(
            f"OpenAPI path parameter mismatch for {path}: "
            f"declared={sorted(declared_path_names)} template={sorted(templated_path_names)}"
        )
    return [combined[key] for key in sorted(combined)]


def openapi_docs(document: dict[str, Any], handlers: list[dict[str, Any]] | None = None) -> tuple[str, str]:
    operations = openapi_operations(document)
    handlers = handlers or []
    handler_route_map = {(item["method"], item["path"]): item for item in (handlers or [])}
    openapi_route_map = {(method, path): operation for method, path, operation in operations}
    if handlers:
        missing_openapi = sorted(set(handler_route_map) - set(openapi_route_map))
        missing_handlers = sorted(set(openapi_route_map) - set(handler_route_map))
        if missing_openapi:
            raise DesignError(f"handler operations missing from OpenAPI: {missing_openapi}")
        if missing_handlers:
            raise DesignError(f"OpenAPI operations missing from handlers: {missing_handlers}")
        for route, handler in sorted(handler_route_map.items()):
            operation = openapi_route_map[route]
            operation_id = str(operation["operationId"])
            if handler.get("operation_id_explicit") and handler["operation_id"] != operation_id:
                raise DesignError(
                    f"operation ID conflict for {route[0]} {route[1]}: "
                    f"handler={handler['operation_id']} OpenAPI={operation_id}"
                )
            operation_extensions(operation, handler)
            handler["operation_id"] = operation_id
    catalog = [
        "# API catalog",
        "",
        "| Method | Path | Operation ID | API number | Permission | Business summary | Requirement IDs |",
        "|---|---|---|---|---|---|---|",
    ]
    interfaces = ["# API interfaces"]
    for method, path, operation in operations:
        path_item = document["paths"][path]
        request_body = operation.get("requestBody", {})
        if not isinstance(request_body, dict):
            raise DesignError(f"OpenAPI requestBody must be inline: {method} {path}")
        request = request_body.get("content", {})
        if not isinstance(request, dict):
            raise DesignError(f"OpenAPI request content must be a mapping: {method} {path}")
        request_types = []
        for media, body in sorted(request.items()):
            if not isinstance(body, dict):
                raise DesignError(f"OpenAPI request media entry must be a mapping: {method} {path}")
            request_types.append(f"{media}:{ref_name(body.get('schema', {}))}")
        responses = []
        raw_responses = operation.get("responses", {})
        if not isinstance(raw_responses, dict) or not raw_responses:
            raise DesignError(f"OpenAPI responses must be a non-empty mapping: {method} {path}")
        for status, response in sorted(raw_responses.items()):
            if not isinstance(response, dict) or "$ref" in response:
                raise DesignError(f"OpenAPI response must be inline: {method} {path} {status}")
            content = response.get("content", {})
            if not isinstance(content, dict):
                raise DesignError(f"OpenAPI response content must be a mapping: {method} {path} {status}")
            schemas = []
            for media, body in sorted(content.items()):
                if not isinstance(body, dict):
                    raise DesignError(f"OpenAPI response media entry must be a mapping: {method} {path} {status}")
                schemas.append(f"{media}:{ref_name(body.get('schema', {}))}")
            responses.append(f"{status}={'/'.join(schemas) or response.get('description', '-')}" )
        parameters = openapi_parameters(path, path_item, operation)
        interfaces += [
            "",
            f"## {method} {path}",
            "",
            f"- Request body: {', '.join(request_types) or '-'}",
            f"- Responses: {', '.join(responses) or '-'}",
            "",
            "| Parameter | In | Required | Schema | Description |",
            "|---|---|:---:|---|---|",
        ]
        for parameter in parameters:
            interfaces.append(
                f"| `{parameter['name']}` | {parameter['in']} | "
                f"{'yes' if parameter['required'] else 'no'} | `{parameter['schema']}` | "
                f"{parameter['description']} |"
            )
        if not parameters:
            interfaces.append("| - | - | - | - | - |")
    schemas = document.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        raise DesignError("OpenAPI components.schemas must be a mapping")
    for method, path, operation in operations:
        operation_id = str(operation["operationId"])
        handler = handler_route_map.get((method, path))
        extensions = operation_extensions(operation, handler)
        requirements = operation.get("x-requirement-ids", [])
        if requirements and (
            not isinstance(requirements, list)
            or not all(isinstance(value, str) and value.strip() for value in requirements)
            or len(requirements) != len(set(requirements))
        ):
            raise DesignError(f"{operation_id}: x-requirement-ids must be a unique string array")
        catalog.append(
            f"| {method} | `{path}` | `{operation_id}` | {extensions.get('x-api-number', '-')} | "
            f"{extensions.get('x-permission', '-')} | {extensions.get('x-business-summary', operation.get('summary', '-'))} | "
            f"{', '.join(requirements) or '-'} |"
        )
    interfaces += ["", "## Schemas", "", "| Name | Required fields | Properties |", "|---|---|---|"]
    for name, schema in sorted(schemas.items()):
        if not isinstance(schema, dict):
            raise DesignError(f"OpenAPI schema must be inline: {name}")
        properties = [f"{key}:{value.get('type', ref_name(value))}" for key, value in sorted(schema.get("properties", {}).items())]
        interfaces.append(f"| `{name}` | {', '.join(schema.get('required', [])) or '-'} | {', '.join(properties) or '-'} |")
    return "\n".join(catalog) + "\n", "\n".join(interfaces) + "\n"


def render_api_details(operations: list[dict[str, Any]], samples: dict[str, Any]) -> str:
    lines = ["# API detailed design"]
    for operation in sorted(operations, key=lambda item: (item["path"], item["method"])):
        operation_id = operation["operation_id"]
        lines += ["", f"## {operation['method']} {operation['path']} — `{operation_id}`", ""]
        lines.append(f"- Responsibility: {operation['docstring']}")
        lines.append(f"- Samples: {', '.join(key for key in samples if key.startswith(operation_id + ':')) or '-'}")
        lines += ["", "### Processing steps", ""]
        for index, call in enumerate(operation["calls"], 1):
            lines.append(f"{index}. `{call}`")
        if not operation["calls"]:
            lines.append("1. Direct response")
        lines += ["", "### Error branches and messages", ""]
        if operation["errors"]:
            lines += ["| Case ID | Code | Status | Message ID |", "|---|---|---:|---|"]
            for error in operation["errors"]:
                lines.append(f"| `{error['id']}` | {error['code']} | {error['status_code']} | {error['message_id']} |")
        else:
            lines.append("- No normalized error branch is declared.")
        lines += ["", "### Unit-test perspectives", "", f"- Success response for `{operation_id}`"]
        for error in operation["errors"]:
            lines.append(f"- Error response `{error['id']}` and message `{error['message_id']}`")
    return "\n".join(lines) + "\n"


def error_case_definition(operations: list[dict[str, Any]]) -> str:
    cases = []
    for operation in sorted(operations, key=lambda item: item["operation_id"]):
        for error in operation["errors"]:
            cases.append({"operation_id": operation["operation_id"], **error})
    return json.dumps(
        {"schema_version": 1, "notice": "AUTO-GENERATED. DO NOT EDIT DIRECTLY.", "cases": cases},
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def parse_sql(
    root: Path,
    repository_root: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    if sqlglot is None or exp is None or traverse_scope is None:
        raise DesignError("SQLGlot is required for SQL AST analysis")
    queries: list[dict[str, Any]] = []
    matrix: dict[str, set[str]] = defaultdict(set)
    repository_root = repository_root or find_repository_root(root)
    sql_files = regular_files(root, repository_root, suffix=".sql")
    if not sql_files:
        raise DesignError(f"SQL root contains no .sql files: {root}")
    for path in sql_files:
        try:
            statements = sqlglot.parse(read_text_nofollow(path), error_level="RAISE")
        except Exception as exc:
            raise DesignError(f"cannot parse SQL {path}: {exc}") from exc
        if not statements or any(statement is None for statement in statements):
            raise DesignError(f"SQL file contains an empty statement: {path}")
        for index, statement in enumerate(statements, 1):
            if not isinstance(statement, (exp.Select, exp.Insert, exp.Update, exp.Delete)):
                raise DesignError(
                    f"unsupported SQL statement in {path}:{index}: {type(statement).__name__}"
                )
            target = None
            if isinstance(statement, (exp.Insert, exp.Update, exp.Delete)):
                target_table = statement.this if isinstance(statement.this, exp.Table) else statement.this.find(exp.Table)
                target = target_table.name if isinstance(target_table, exp.Table) else None
                if not target:
                    raise DesignError(f"SQL write has no statically named target: {path}:{index}")
            cte_aliases = {
                cte.alias_or_name
                for cte in statement.find_all(exp.CTE)
                if cte.alias_or_name
            }
            tables = {
                source.name
                for scope in traverse_scope(statement)
                for source in scope.sources.values()
                if isinstance(source, exp.Table)
            }
            tables.update(
                table.name
                for table in statement.find_all(exp.Table)
                if table.name not in cte_aliases
            )
            if target:
                tables.add(target)
            if not tables or any(not table for table in tables):
                raise DesignError(f"SQL statement has no statically named table: {path}:{index}")
            operation = "SELECT"
            letter = "R"
            if isinstance(statement, exp.Insert):
                operation, letter = "INSERT", "C"
            elif isinstance(statement, exp.Update):
                operation, letter = "UPDATE", "U"
            elif isinstance(statement, exp.Delete):
                operation, letter = "DELETE", "D"
            write_columns: set[str] = set()
            if isinstance(statement, exp.Insert) and isinstance(statement.this, exp.Schema):
                write_columns.update(identifier.name for identifier in statement.this.expressions if isinstance(identifier, exp.Identifier))
            elif isinstance(statement, exp.Update):
                for assignment in statement.expressions:
                    if isinstance(assignment, exp.EQ) and isinstance(assignment.this, exp.Column):
                        write_columns.add(assignment.this.name)
            for table in tables:
                matrix[table].add(letter if table == target else "R")
            relative = path.relative_to(root).with_suffix("").as_posix().replace("/", "-")
            queries.append(
                {
                    "id": f"{relative}-{index}",
                    "file": path.relative_to(root).as_posix(),
                    "operation": operation,
                    "letter": letter,
                    "target": target or "-",
                    "tables": sorted(tables),
                    "write_columns": sorted(write_columns),
                }
            )
    return queries, matrix


def bind_operation_queries(
    operations: list[dict[str, Any]],
    queries: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Bind every SQL source file to exactly one explicit operation reference."""

    files = sorted({str(query["file"]) for query in queries})
    basename_index: dict[str, list[str]] = defaultdict(list)
    for file in files:
        basename_index[Path(file).name].append(file)
    ownership: dict[str, str] = {}
    result: dict[str, list[dict[str, Any]]] = {}
    for operation in operations:
        operation_id = str(operation["operation_id"])
        references = operation.get("sql_files", [])
        if not isinstance(references, list) or len(references) != len(set(references)):
            raise DesignError(f"{operation_id}: SQL references must be a unique array")
        resolved: set[str] = set()
        for reference in references:
            if not isinstance(reference, str):
                raise DesignError(f"{operation_id}: SQL reference must be a string")
            raw_parts = reference.split("/")
            if (
                not reference
                or "\\" in reference
                or any(part in {"", ".", ".."} for part in raw_parts)
            ):
                raise DesignError(
                    f"{operation_id}: SQL reference must be a normalized relative path: {reference}"
                )
            relative = Path(reference)
            if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
                raise DesignError(
                    f"{operation_id}: SQL reference must be a normalized relative path: {reference}"
                )
            normalized = relative.as_posix()
            if normalized in files:
                target = normalized
            elif len(relative.parts) == 1:
                candidates = basename_index.get(relative.name, [])
                if len(candidates) > 1:
                    raise DesignError(
                        f"{operation_id}: SQL basename is ambiguous: {reference}: {candidates}"
                    )
                if not candidates:
                    raise DesignError(f"{operation_id}: SQL reference does not exist: {reference}")
                target = candidates[0]
            else:
                raise DesignError(f"{operation_id}: SQL reference does not exist: {reference}")
            previous = ownership.get(target)
            if previous is not None and previous != operation_id:
                raise DesignError(
                    f"SQL source maps to multiple operations: {target}: {previous}, {operation_id}"
                )
            ownership[target] = operation_id
            resolved.add(target)
        result[operation_id] = [query for query in queries if query["file"] in resolved]
    unbound = sorted(set(files) - set(ownership))
    if unbound:
        raise DesignError(f"SQL sources lack an explicit operation mapping: {unbound}")
    return result


def sql_docs(root: Path, operations: list[dict[str, Any]] | None = None) -> tuple[str, str]:
    queries, matrix = parse_sql(root)
    query_lines = ["# Query objects", "", "| Query | File | Operation | Target | Tables |", "|---|---|---|---|---|"]
    for query in queries:
        query_lines.append(f"| `{query['id']}` | `{query['file']}` | {query['operation']} | {query['target']} | {', '.join(query['tables']) or '-'} |")
    crud = ["# CRUD matrix", "", "| Table | C | R | U | D |", "|---|:---:|:---:|:---:|:---:|"]
    for table, letters in sorted(matrix.items()):
        crud.append("| " + table + " | " + " | ".join(letter if letter in letters else "-" for letter in "CRUD") + " |")
    operations = operations or []
    if operations:
        bindings = bind_operation_queries(operations, queries)
        operation_ids = [str(operation["operation_id"]) for operation in operations]
        api_matrix: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for operation in operations:
            for query in bindings[str(operation["operation_id"])]:
                for table in query["tables"]:
                    api_matrix[table][str(operation["operation_id"])].add(query["letter"] if table == query["target"] else "R")
        crud += ["", "## Table by API", "", "| Table | " + " | ".join(operation_ids) + " |", "|---|" + "|".join("---" for _ in operation_ids) + "|"]
        for table in sorted(api_matrix):
            crud.append("| " + table + " | " + " | ".join("".join(sorted(api_matrix[table].get(operation_id, set()), key="CRUD".index)) or "-" for operation_id in operation_ids) + " |")
        clients = sorted({client for operation in operations for client in operation["external_clients"]})
        crud += ["", "## External destination by API", "", "| External destination | " + " | ".join(operation_ids) + " |", "|---|" + "|".join("---" for _ in operation_ids) + "|"]
        for client in clients:
            crud.append("| `" + client + "` | " + " | ".join("X" if client in operation["external_clients"] else "-" for operation in operations) + " |")
        if not clients:
            crud.append("| - | " + " | ".join("-" for _ in operation_ids) + " |")
    return "\n".join(crud) + "\n", "\n".join(query_lines) + "\n"


def ddl_docs(ddl_root: Path, sql_root: Path, operations: list[dict[str, Any]]) -> str:
    """Generate tables, columns, constraints, ER links, and writing APIs from DDL/SQL ASTs."""

    if sqlglot is None or exp is None:
        raise DesignError("SQLGlot is required for DDL AST analysis")
    tables: dict[str, dict[str, Any]] = {}
    relations: set[tuple[str, str, str, str]] = set()
    repository_root = find_repository_root(ddl_root)
    ddl_files = regular_files(ddl_root, repository_root, suffix=".sql")
    if not ddl_files:
        raise DesignError(f"DDL root contains no .sql files: {ddl_root}")
    for path in ddl_files:
        try:
            statements = sqlglot.parse(read_text_nofollow(path), error_level="RAISE")
        except Exception as exc:
            raise DesignError(f"cannot parse DDL {path}: {exc}") from exc
        if not statements or any(statement is None for statement in statements):
            raise DesignError(f"DDL file contains an empty statement: {path}")
        for index, statement in enumerate(statements, 1):
            if not isinstance(statement, exp.Create) or str(statement.args.get("kind", "")).upper() != "TABLE" or not isinstance(statement.this, exp.Schema):
                raise DesignError(
                    f"unsupported DDL statement in {path}:{index}: {type(statement).__name__}"
                )
            schema = statement.this
            table_name = schema.this.name
            if not table_name:
                raise DesignError(f"CREATE TABLE has no static table name: {path}:{index}")
            if table_name in tables:
                raise DesignError(f"duplicate CREATE TABLE authority: {table_name}")
            columns: list[dict[str, str]] = []
            constraints: list[str] = []
            for item in schema.expressions:
                if isinstance(item, exp.ColumnDef):
                    kinds = [type(constraint.args.get("kind")).__name__.removesuffix("ColumnConstraint") for constraint in item.args.get("constraints", [])]
                    columns.append({"name": item.this.name, "type": item.args.get("kind").sql(), "constraints": ", ".join(kinds) or "-"})
                    for constraint in item.args.get("constraints", []):
                        reference = constraint.args.get("kind")
                        if not isinstance(reference, exp.Reference):
                            continue
                        referenced_schema = reference.this
                        referenced = (
                            referenced_schema.this
                            if isinstance(referenced_schema, exp.Schema)
                            and isinstance(referenced_schema.this, exp.Table)
                            else None
                        )
                        destination_columns = (
                            ",".join(
                                identifier.name
                                for identifier in referenced_schema.expressions
                                if isinstance(identifier, exp.Identifier)
                            )
                            if isinstance(referenced_schema, exp.Schema)
                            else "-"
                        )
                        if not isinstance(referenced, exp.Table):
                            raise DesignError(
                                f"column foreign key has no static destination: {path}:{item.this.name}"
                            )
                        relations.add(
                            (
                                table_name,
                                item.this.name,
                                referenced.name,
                                destination_columns or "-",
                            )
                        )
                else:
                    constraints.append(item.sql())
                    for foreign_key in item.find_all(exp.ForeignKey):
                        reference = foreign_key.args.get("reference")
                        referenced_schema = reference.this if isinstance(reference, exp.Reference) else None
                        referenced = (
                            referenced_schema.this
                            if isinstance(referenced_schema, exp.Schema)
                            and isinstance(referenced_schema.this, exp.Table)
                            else None
                        )
                        local_columns = ",".join(identifier.name for identifier in foreign_key.expressions if isinstance(identifier, exp.Identifier))
                        destination_columns = (
                            ",".join(
                                identifier.name
                                for identifier in referenced_schema.expressions
                                if isinstance(identifier, exp.Identifier)
                            )
                            if isinstance(referenced_schema, exp.Schema)
                            else "-"
                        )
                        if not isinstance(referenced, exp.Table):
                            raise DesignError(f"foreign key has no static destination: {path}")
                        relations.add(
                            (
                                table_name,
                                local_columns or "-",
                                referenced.name,
                                destination_columns or "-",
                            )
                        )
            tables[table_name] = {"columns": columns, "constraints": constraints, "source": path.relative_to(ddl_root).as_posix()}

    queries, _ = parse_sql(sql_root)
    bindings = bind_operation_queries(operations, queries)
    writes: dict[tuple[str, str], set[str]] = defaultdict(set)
    for operation in operations:
        for query in bindings[str(operation["operation_id"])]:
            if query["letter"] not in {"C", "U"} or query["target"] == "-":
                continue
            columns = query["write_columns"] or ["*"]
            for column in columns:
                writes[(query["target"], column)].add(str(operation["operation_id"]))

    lines = ["# Database design", "", "## Tables and columns", "", "| Table | Column | Type | Constraints | DDL source |", "|---|---|---|---|---|"]
    for table_name, table in sorted(tables.items()):
        for column in table["columns"]:
            lines.append(f"| `{table_name}` | `{column['name']}` | `{column['type']}` | {column['constraints']} | `{table['source']}` |")
        if not table["columns"]:
            lines.append(f"| `{table_name}` | - | - | - | `{table['source']}` |")
    lines += ["", "## Table constraints", "", "| Table | Constraint |", "|---|---|"]
    for table_name, table in sorted(tables.items()):
        if table["constraints"]:
            for constraint in table["constraints"]:
                lines.append(f"| `{table_name}` | `{constraint}` |")
        else:
            lines.append(f"| `{table_name}` | - |")
    lines += ["", "## ER relationships", "", "| From table | Columns | To table | To columns |", "|---|---|---|---|"]
    for source, columns, destination, destination_columns in sorted(relations):
        lines.append(
            f"| `{source}` | `{columns}` | `{destination}` | `{destination_columns}` |"
        )
    if not relations:
        lines.append("| - | - | - | - |")
    lines += ["", "## Column-writing APIs", "", "| Table | Column | APIs |", "|---|---|---|"]
    for (table, column), api_ids in sorted(writes.items()):
        lines.append(f"| `{table}` | `{column}` | {', '.join(sorted(api_ids))} |")
    if not writes:
        lines.append("| - | - | - |")
    return "\n".join(lines) + "\n"


GWT_PATTERN = re.compile(r"^\s*#\s*(Given|When|Then)(?:\([^)]*\))?\s*[:：-]?\s*(.*)$", re.IGNORECASE)


def e2e_scenarios(root: Path) -> str:
    """Generate ordered Given/When/Then scenarios from test-code sections."""

    scenarios: list[dict[str, Any]] = []
    repository_root = find_repository_root(root)
    for path in regular_files(
        root,
        repository_root,
        suffix=".py",
        name_prefix="test",
    ):
        text = read_text_nofollow(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            raise DesignError(f"cannot parse E2E test {path}: {exc}") from exc
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            steps: list[tuple[str, str]] = []
            for line in lines[node.lineno - 1 : node.end_lineno or node.lineno]:
                match = GWT_PATTERN.match(line)
                if match:
                    steps.append((match.group(1).title(), match.group(2).strip() or "declared section"))
            if steps:
                if [kind for kind, _ in steps] != ["Given", "When", "Then"]:
                    raise DesignError(f"{path}:{node.name}: E2E sections must be exactly Given, When, Then")
                scenarios.append({"name": node.name, "source": path.relative_to(root).as_posix(), "docstring": (ast.get_docstring(node) or "-").splitlines()[0], "steps": steps})
    result = ["# E2E scenarios"]
    for scenario in scenarios:
        result += ["", f"## `{scenario['name']}`", "", f"- Source: `{scenario['source']}`", f"- Purpose: {scenario['docstring']}", ""]
        for kind, description in scenario["steps"]:
            result.append(f"1. **{kind}**: {description}")
    if not scenarios:
        result += ["", "No declared E2E scenario was found."]
    return "\n".join(result) + "\n"


def evidence_view(path: Path) -> str:
    """Format external test-result references without copying response bodies."""

    document = load_structured(path)
    runs = document.get("runs") if isinstance(document, dict) else None
    if not isinstance(runs, list):
        raise DesignError("test evidence JSON requires a runs array")
    allowed = {"id", "status", "api_response", "db_result", "mock_result"}
    lines = ["# Test evidence view", "", "| Run | Status | API response | DB result | Mock result |", "|---|---|---|---|---|"]
    for run in runs:
        if not isinstance(run, dict) or set(run) - allowed or not all(isinstance(run.get(key, "-"), str) for key in allowed):
            raise DesignError("test evidence entries may contain only string references, not result bodies")
        for key in ["api_response", "db_result", "mock_result"]:
            reference = run.get(key, "-")
            if reference != "-" and not reference.startswith(("https://", "http://", "artifact://", "run://")):
                raise DesignError(f"test evidence {key} must be an external URL or artifact/run reference")
        lines.append(f"| {run.get('id', '-')} | {run.get('status', '-')} | {run.get('api_response', '-')} | {run.get('db_result', '-')} | {run.get('mock_result', '-')} |")
    return "\n".join(lines) + "\n"


def tool_design(root: Path) -> str:
    """Generate CLI arguments, control flow, and function responsibility from Python AST/docstrings."""

    lines = ["# Generator tool design"]
    repository_root = find_repository_root(root)
    for path in regular_files(root, repository_root, suffix=".py"):
        try:
            tree = ast.parse(read_text_nofollow(path), filename=str(path))
        except SyntaxError as exc:
            raise DesignError(f"cannot parse tool {path}: {exc}") from exc
        arguments: list[str] = []
        functions: list[tuple[str, str, list[str]]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and display_call(node).endswith("add_argument") and node.args:
                argument = literal(node.args[0])
                if isinstance(argument, str):
                    arguments.append(argument)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node)
                if docstring:
                    collector = RuntimeCallOrder()
                    for statement in node.body:
                        collector.visit(statement)
                    functions.append((node.name, docstring.splitlines()[0], [display_call(call) for call in collector.calls]))
        if not arguments and not functions:
            continue
        lines += ["", f"## `{path.relative_to(root).as_posix()}`", "", f"- CLI arguments: {', '.join(sorted(set(arguments))) or '-'}", "", "| Function | Responsibility | Calls |", "|---|---|---|"]
        for name, responsibility, calls in functions:
            lines.append(f"| `{name}` | {responsibility} | {', '.join(calls) or '-'} |")
    return "\n".join(lines) + "\n"


def active_requirement_catalog(path: Path) -> dict[str, dict[str, Any]]:
    """Load the generated canonical requirement view and retain active entries."""

    document = load_structured(path)
    requirements = document.get("requirements") if isinstance(document, dict) else None
    if not isinstance(requirements, list):
        raise DesignError("canonical requirements JSON requires a requirements array")
    catalog: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise DesignError("canonical requirement entries must be objects")
        requirement_id = requirement.get("id")
        status = requirement.get("status")
        if not isinstance(requirement_id, str) or not requirement_id:
            raise DesignError("canonical requirement requires a non-empty id")
        if requirement_id in seen:
            raise DesignError(f"duplicate canonical requirement ID: {requirement_id}")
        seen.add(requirement_id)
        if status == "active":
            catalog[requirement_id] = requirement
    return catalog


def pytest_collection_manifest(test_root: Path, repository_root: Path) -> dict[str, Any]:
    """Build the supported, static subset of pytest's collection manifest."""

    repository_root = repository_root.absolute()
    files = regular_files(
        test_root,
        repository_root,
        suffix=".py",
        name_prefix="test",
    )
    safe_io = _bootstrap_safe_io(repository_root)
    nodes: list[str] = []
    sources: list[dict[str, str]] = []
    for path in files:
        relative = path.relative_to(repository_root).as_posix()
        try:
            content = safe_io.read_bytes_nofollow(path, root=repository_root)
            tree = ast.parse(content, filename=str(path))
        except (OSError, SyntaxError, safe_io.SafeIOError) as exc:
            raise DesignError(f"cannot collect pytest source {relative}: {exc}") from exc
        module_disabled = any(
            isinstance(item, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == "__test__"
                for target in (item.targets if isinstance(item, ast.Assign) else [item.target])
            )
            and literal(item.value) is False
            for item in tree.body
        )
        if not module_disabled:
            for item in tree.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                    if any(
                        isinstance(decorator, ast.Call)
                        and dotted_name(decorator.func).endswith("parametrize")
                        for decorator in item.decorator_list
                    ):
                        continue
                    nodes.append(f"{relative}::{item.name}")
                if not isinstance(item, ast.ClassDef):
                    continue
                unittest_case = any(dotted_name(base).endswith("TestCase") for base in item.bases)
                if not item.name.startswith("Test") and not unittest_case:
                    continue
                if any(
                    isinstance(decorator, ast.Call)
                    and dotted_name(decorator.func).endswith("parametrize")
                    for decorator in item.decorator_list
                ):
                    continue
                if any(
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == "__init__"
                    for child in item.body
                ):
                    continue
                for child in item.body:
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) or not child.name.startswith("test"):
                        continue
                    if any(
                        isinstance(decorator, ast.Call)
                        and dotted_name(decorator.func).endswith("parametrize")
                        for decorator in child.decorator_list
                    ):
                        continue
                    nodes.append(f"{relative}::{item.name}::{child.name}")
        sources.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return {
        "schema_version": 1,
        "notice": "AUTO-GENERATED. DO NOT EDIT DIRECTLY.",
        "collector": "portable-pytest-static-v1",
        "sources": sources,
        "nodes": sorted(nodes),
    }


def validate_test_node(
    node_id: str,
    test_root: Path,
    repository_root: Path,
    collectable_nodes: set[str] | None = None,
) -> None:
    """Require a repository-relative node in the generated pytest manifest."""

    parts = node_id.split("::")
    if len(parts) not in {2, 3} or not all(parts):
        raise DesignError(f"test node must be path::test or path::Class::test: {node_id}")
    relative = Path(parts[0])
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
        or relative.suffix != ".py"
    ):
        raise DesignError(f"test node path must be a normalized repository-relative Python file: {node_id}")
    nodes = collectable_nodes
    if nodes is None:
        nodes = set(pytest_collection_manifest(test_root, repository_root)["nodes"])
    if node_id not in nodes:
        raise DesignError(f"test node is not in the portable pytest collection manifest: {node_id}")


def traceability_view(
    requirements_path: Path,
    trace_path: Path,
    artifact_kind: str,
    artifact_requirements: dict[str, list[str]],
    test_root: Path,
    repository_root: Path,
) -> str:
    """Validate requirement-to-artifact-to-test links and render their exact projection."""

    catalog = active_requirement_catalog(requirements_path)
    test_manifest = pytest_collection_manifest(test_root, repository_root)
    collectable_nodes = set(test_manifest["nodes"])
    document = load_structured(trace_path)
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "applicable_requirement_ids", "links"}
        or document.get("schema_version") != 2
    ):
        raise DesignError(
            "trace JSON must contain schema_version 2, applicable_requirement_ids, and links only"
        )
    applicable = document.get("applicable_requirement_ids")
    if (
        not isinstance(applicable, list)
        or not applicable
        or not all(isinstance(value, str) and value for value in applicable)
        or len(applicable) != len(set(applicable))
    ):
        raise DesignError("trace applicable_requirement_ids must be a non-empty unique string array")
    unknown_applicable = sorted(set(applicable) - set(catalog))
    if unknown_applicable:
        raise DesignError(
            f"trace applicable requirements are unknown or inactive: {unknown_applicable}"
        )
    links = document.get("links") if isinstance(document, dict) else None
    if not isinstance(links, list):
        raise DesignError("trace JSON requires a links array")
    expected = {
        artifact_id: set(requirement_ids)
        for artifact_id, requirement_ids in artifact_requirements.items()
    }
    for artifact_id, requirement_ids in expected.items():
        if not requirement_ids:
            raise DesignError(f"{artifact_kind} lacks canonical requirement IDs: {artifact_id}")
        if any(not isinstance(value, str) or not value for value in requirement_ids):
            raise DesignError(f"{artifact_kind} has invalid requirement IDs: {artifact_id}")
        if len(requirement_ids) != len(set(requirement_ids)):
            raise DesignError(f"{artifact_kind} has duplicate requirement IDs: {artifact_id}")
    metadata_applicable = set().union(*expected.values()) if expected else set()
    if metadata_applicable != set(applicable):
        raise DesignError(
            "artifact metadata and explicit applicable requirements differ: "
            f"metadata={sorted(metadata_applicable)} applicable={sorted(applicable)}"
        )
    observed: dict[str, set[str]] = defaultdict(set)
    rendered: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != {"requirement_id", "artifact", "tests"}:
            raise DesignError("each trace link requires only requirement_id, artifact, and tests")
        requirement_id = link["requirement_id"]
        artifact = link["artifact"]
        tests = link["tests"]
        if requirement_id not in catalog:
            raise DesignError(f"trace references an unknown or inactive requirement: {requirement_id}")
        if not isinstance(artifact, dict) or set(artifact) != {"kind", "id"}:
            raise DesignError(f"trace artifact must contain only kind and id: {requirement_id}")
        if artifact.get("kind") != artifact_kind or artifact.get("id") not in expected:
            raise DesignError(
                f"trace references an unknown {artifact_kind}: {artifact.get('id')}"
            )
        artifact_id = str(artifact["id"])
        key = (str(requirement_id), artifact_id)
        if key in seen:
            raise DesignError(f"duplicate requirement/artifact trace: {key[0]} -> {key[1]}")
        seen.add(key)
        if (
            not isinstance(tests, list)
            or not tests
            or not all(isinstance(node_id, str) for node_id in tests)
            or len(tests) != len(set(tests))
        ):
            raise DesignError(f"trace tests must be a non-empty unique array: {key[0]} -> {key[1]}")
        for node_id in tests:
            validate_test_node(
                node_id,
                test_root,
                repository_root,
                collectable_nodes,
            )
        observed[artifact_id].add(str(requirement_id))
        rendered.append(
            {
                "requirement_id": str(requirement_id),
                "title": str(catalog[str(requirement_id)].get("title", "-")),
                "artifact_id": artifact_id,
                "tests": sorted(tests),
            }
        )
    if observed != expected:
        missing = {
            artifact: sorted(requirements - observed.get(artifact, set()))
            for artifact, requirements in expected.items()
            if requirements - observed.get(artifact, set())
        }
        unexpected = {
            artifact: sorted(requirements - expected.get(artifact, set()))
            for artifact, requirements in observed.items()
            if requirements - expected.get(artifact, set())
        }
        raise DesignError(
            f"artifact metadata and explicit trace differ: missing={missing} unexpected={unexpected}"
        )
    lines = [
        "# Requirement traceability",
        "",
        f"| Requirement | Title | {artifact_kind.title()} | Test nodes |",
        "|---|---|---|---|",
    ]
    for link in sorted(rendered, key=lambda item: (item["requirement_id"], item["artifact_id"])):
        lines.append(
            f"| `{link['requirement_id']}` | {link['title']} | `{link['artifact_id']}` | "
            f"{', '.join(f'`{node}`' for node in link['tests'])} |"
        )
    return "\n".join(lines) + "\n"


def cfn_requirement_ids(resource: dict[str, Any], logical_id: str) -> list[str]:
    """Read requirement IDs from explicit synthesized-resource metadata."""

    metadata = resource.get("Metadata", {})
    if not isinstance(metadata, dict):
        raise DesignError(f"CloudFormation resource Metadata must be a mapping: {logical_id}")
    value = metadata.get("RequirementIds")
    if value is None and isinstance(metadata.get("DevStandard"), dict):
        value = metadata["DevStandard"].get("RequirementIds")
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise DesignError(f"CloudFormation resource requires Metadata.RequirementIds: {logical_id}")
    if len(value) != len(set(value)):
        raise DesignError(f"CloudFormation resource has duplicate requirement IDs: {logical_id}")
    return value


def cfn_docs(template: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(template, dict) or not isinstance(template.get("Resources"), dict):
        raise DesignError("CloudFormation template requires a Resources mapping")
    if not template["Resources"]:
        raise DesignError("CloudFormation template requires at least one resource")
    resources = [
        "# CloudFormation resources",
        "",
        "| Logical ID | Type | Condition | DependsOn | Properties |",
        "|---|---|---|---|---|",
    ]
    for logical_id, resource in sorted(template["Resources"].items()):
        if not isinstance(logical_id, str) or not isinstance(resource, dict):
            raise DesignError(f"unsupported CloudFormation resource: {logical_id}")
        if not isinstance(resource.get("Type"), str):
            raise DesignError(f"CloudFormation resource type missing: {logical_id}")
        properties = resource.get("Properties", {})
        if not isinstance(properties, dict):
            raise DesignError(f"CloudFormation resource Properties must be a mapping: {logical_id}")
        depends = resource.get("DependsOn", "-")
        if isinstance(depends, list):
            depends = ", ".join(depends)
        elif not isinstance(depends, str):
            raise DesignError(f"CloudFormation DependsOn must be a string or array: {logical_id}")
        serialized_properties = json.dumps(
            properties,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).replace("|", "\\|")
        resources.append(
            f"| `{logical_id}` | `{resource.get('Type', '-')}` | "
            f"{resource.get('Condition', '-')} | {depends} | `{serialized_properties}` |"
        )
    parameters = ["# CloudFormation parameters", "", "| Name | Type | Default | Allowed values | Description |", "|---|---|---|---|---|"]
    raw_parameters = template.get("Parameters", {})
    if not isinstance(raw_parameters, dict):
        raise DesignError("CloudFormation Parameters must be a mapping")
    for name, parameter in sorted(raw_parameters.items()):
        if not isinstance(name, str) or not isinstance(parameter, dict):
            raise DesignError(f"unsupported CloudFormation parameter: {name}")
        allowed = parameter.get("AllowedValues", "-")
        if isinstance(allowed, list):
            allowed = ", ".join(map(str, allowed))
        parameters.append(f"| `{name}` | `{parameter.get('Type', '-')}` | {parameter.get('Default', '-')} | {allowed} | {parameter.get('Description', '-')} |")
    return "\n".join(resources) + "\n", "\n".join(parameters) + "\n"


def command_templates(kind: str) -> tuple[str, str]:
    entry = (
        "python tools/portable_python.py run "
        "<host-skill-path>/scripts/designflow.py --"
    )
    if kind == "fastapi":
        arguments = (
            "fastapi --source-root <source-root> --openapi <openapi.json> "
            "--sql-root <sql-root> [--ddl-root <ddl-root>] [--e2e-root <e2e-root>] "
            "[--tool-root <tool-root>] [--evidence <external-evidence.json>] "
            "--requirements <requirements.json> --trace <trace.json> --test-root <test-root> "
            "--out <output>"
        )
    elif kind == "cdk":
        arguments = (
            "cdk --template <template.yaml> --requirements <requirements.json> "
            "--trace <trace.json> --test-root <test-root> --out <output>"
        )
    else:  # pragma: no cover - internal contract
        raise DesignError(f"unsupported generator kind: {kind}")
    generate = f"{entry} {arguments}"
    return generate, generate + " --check"


def generated_banner(kind: str) -> str:
    generate, check = command_templates(kind)
    return (
        "<!-- AUTO-GENERATED. DO NOT EDIT DIRECTLY.\n"
        f"Generate: `{generate}`\n"
        f"Check: `{check}`\n"
        "-->\n\n"
    )


def rename_directory_noreplace(
    safe_io: Any,
    source_fd: int,
    source: str,
    destination_fd: int,
    destination: str,
    *,
    display: Path,
) -> None:
    """Publish one directory with the bundled platform CAS primitives."""

    try:
        if safe_io._renameat2(
            source_fd,
            source,
            destination_fd,
            destination,
            safe_io._RENAME_NOREPLACE,
        ):
            return
        if safe_io._renameatx_np(
            source_fd,
            source,
            destination_fd,
            destination,
            safe_io._RENAME_EXCL_DARWIN,
        ):
            return
        if os.name == "nt":  # Windows rename refuses an existing target.
            os.rename(
                source,
                destination,
                src_dir_fd=source_fd,
                dst_dir_fd=destination_fd,
            )
            return
        raise DesignError("atomic directory no-replace is unavailable on this platform")
    except FileExistsError as exc:
        raise DesignError(
            f"generated output changed during publication: {display}"
        ) from exc


def write_regular_exclusive(directory_fd: int, name: str, content: str) -> None:
    """Write one generated UTF-8 file through a pinned candidate directory."""

    if not name or name in {".", ".."} or Path(name).name != name:
        raise DesignError(f"generated file must have a plain filename: {name}")
    descriptor = os.open(
        name,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        remaining = memoryview(content.encode("utf-8"))
        while remaining:
            written = os.write(descriptor, remaining)
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_bundle(
    out: Path,
    files: dict[str, str],
    sources: list[tuple[str, Path]],
    kind: str,
    *,
    repository_root: Path,
    candidate: bool = False,
) -> None:
    safe_io = _bootstrap_safe_io(repository_root)
    managed_identity: tuple[int, int, str] | None = None
    if not candidate:
        out, _ = validate_output_path(out, repository_root)
        if out.exists():
            managed_identity = validate_managed_bundle(out, repository_root)

    generate, check = command_templates(kind)
    source_paths = sorted({path.absolute() for _, path in sources})
    source_entries: list[dict[str, str]] = []
    for path in source_paths:
        try:
            relative = path.relative_to(repository_root).as_posix()
        except ValueError as exc:
            raise DesignError(f"manifest source escapes repository: {path}") from exc
        source_entries.append({"path": relative, "sha256": sha(path)})
    manifest = {
        "managed_by": MANAGED_BY,
        "notice": "AUTO-GENERATED. DO NOT EDIT DIRECTLY.",
        "generate_command": generate,
        "check_command": check,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "sources": source_entries,
        "generated": sorted(files),
    }
    payloads: dict[str, str] = {}
    banner = generated_banner(kind)
    for name, content in files.items():
        if name == "manifest.json":
            raise DesignError("generated files must not replace manifest.json")
        if name.endswith(".gen.md"):
            payload = banner + content
        elif name.endswith(".gen.json"):
            try:
                document = json.loads(content)
            except json.JSONDecodeError as exc:
                raise DesignError(f"generated JSON is invalid: {name}") from exc
            if document.get("notice") != "AUTO-GENERATED. DO NOT EDIT DIRECTLY.":
                raise DesignError(f"generated JSON requires a direct-edit notice: {name}")
            payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        else:
            raise DesignError(f"generated file must end with .gen.md or .gen.json: {name}")
        payloads[name] = payload
    payloads["manifest.json"] = json.dumps(
        manifest, ensure_ascii=False, indent=2
    ) + "\n"

    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    if candidate:
        try:
            parent_manager = safe_io.trusted_root(out.parent)
            parent_fd = parent_manager.__enter__()
        except (OSError, safe_io.SafeIOError) as exc:
            raise DesignError(f"candidate parent is unsafe or missing: {out.parent}: {exc}") from exc
        temporary_name = f".{out.name}.candidate-{uuid.uuid4().hex}"
        temporary = out.parent / temporary_name
        try:
            try:
                os.stat(out.name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise DesignError(f"candidate output already exists: {out}")
            os.mkdir(temporary_name, mode=0o700, dir_fd=parent_fd)
            temporary_fd = os.open(temporary_name, directory_flags, dir_fd=parent_fd)
            published = False
            staged_identity: tuple[int, int, str] | None = None
            try:
                for name, payload in sorted(payloads.items()):
                    write_regular_exclusive(temporary_fd, name, payload)
                os.fsync(temporary_fd)
                staged_identity = pinned_directory_identity(
                    temporary_fd,
                    display=temporary,
                    safe_io=safe_io,
                )
                rename_directory_noreplace(
                    safe_io,
                    parent_fd,
                    temporary_name,
                    parent_fd,
                    out.name,
                    display=out,
                )
                published = True
                os.fsync(parent_fd)
            except BaseException as operation_error:
                if not published:
                    try:
                        cleanup_identity = staged_identity or pinned_directory_identity(
                            temporary_fd,
                            display=temporary,
                            safe_io=safe_io,
                        )
                        safe_io.remove_tree_nofollow_cas(
                            temporary,
                            expected_identity=cleanup_identity,
                            root=out.parent,
                            pinned_root_fd=parent_fd,
                        )
                    except (OSError, safe_io.SafeIOError, DesignError) as cleanup_error:
                        raise DesignError(
                            "candidate generation failed and the staged directory was "
                            f"preserved at {temporary}: {cleanup_error}"
                        ) from operation_error
                raise
            finally:
                os.close(temporary_fd)
        finally:
            parent_manager.__exit__(None, None, None)
        return

    backup: Path | None = None
    try:
        with safe_io.trusted_root(repository_root) as root_fd:
            with safe_io.directory_nofollow_pinned(
                out.parent,
                root=repository_root,
                root_fd=root_fd,
                create=True,
            ) as output_parent_fd:
                temporary_name = f".{out.name}.candidate-{uuid.uuid4().hex}"
                temporary = out.parent / temporary_name
                os.mkdir(temporary_name, mode=0o700, dir_fd=output_parent_fd)
                temporary_fd = os.open(
                    temporary_name, directory_flags, dir_fd=output_parent_fd
                )
                published = False
                staged_identity: tuple[int, int, str] | None = None
                try:
                    for name, payload in sorted(payloads.items()):
                        write_regular_exclusive(temporary_fd, name, payload)
                    os.fsync(temporary_fd)
                    staged_identity = pinned_directory_identity(
                        temporary_fd,
                        display=temporary,
                        safe_io=safe_io,
                    )
                    try:
                        current = os.stat(
                            out.name,
                            dir_fd=output_parent_fd,
                            follow_symlinks=False,
                        )
                    except FileNotFoundError:
                        current = None
                    if managed_identity is None and current is not None:
                        raise DesignError(
                            f"generated output changed after validation: {out}"
                        )
                    if managed_identity is not None and current is None:
                        raise DesignError(
                            f"generated output changed after validation: {out}"
                        )
                    if current is not None:
                        if not stat.S_ISDIR(current.st_mode) or stat.S_ISLNK(
                            current.st_mode
                        ):
                            raise DesignError(
                                f"generated output must be a non-symlink directory: {out}"
                            )
                        backup = out.parent / f".{out.name}.backup-{uuid.uuid4().hex}"
                        rename_directory_noreplace(
                            safe_io,
                            output_parent_fd,
                            out.name,
                            output_parent_fd,
                            backup.name,
                            display=backup,
                        )
                    try:
                        if backup is not None:
                            backup_fd = os.open(
                                backup.name,
                                directory_flags,
                                dir_fd=output_parent_fd,
                            )
                            try:
                                moved_identity = pinned_directory_identity(
                                    backup_fd,
                                    display=backup,
                                    safe_io=safe_io,
                                )
                            finally:
                                os.close(backup_fd)
                            if moved_identity != managed_identity:
                                raise DesignError(
                                    f"generated output changed after validation: {out}"
                                )
                        rename_directory_noreplace(
                            safe_io,
                            output_parent_fd,
                            temporary_name,
                            output_parent_fd,
                            out.name,
                            display=out,
                        )
                        published = True
                        os.fsync(output_parent_fd)
                    except BaseException as publication_error:
                        if backup is not None:
                            try:
                                rename_directory_noreplace(
                                    safe_io,
                                    output_parent_fd,
                                    backup.name,
                                    output_parent_fd,
                                    out.name,
                                    display=out,
                                )
                            except BaseException as rollback_error:
                                raise DesignError(
                                    "generated bundle publication failed and the previous "
                                    f"bundle was preserved at {backup}: {rollback_error}"
                                ) from publication_error
                            backup = None
                            os.fsync(output_parent_fd)
                        raise
                    if backup is not None:
                        try:
                            safe_io.remove_tree_nofollow_cas(
                                backup,
                                expected_identity=managed_identity,
                                root=repository_root,
                                pinned_root_fd=root_fd,
                            )
                        except safe_io.SafeIOError as exc:
                            raise DesignError(
                                f"previous generated bundle cleanup was refused: {exc}"
                            ) from exc
                        backup = None
                except BaseException as operation_error:
                    if not published:
                        try:
                            cleanup_identity = staged_identity or pinned_directory_identity(
                                temporary_fd,
                                display=temporary,
                                safe_io=safe_io,
                            )
                            safe_io.remove_tree_nofollow_cas(
                                temporary,
                                expected_identity=cleanup_identity,
                                root=repository_root,
                                pinned_root_fd=root_fd,
                            )
                        except (OSError, safe_io.SafeIOError, DesignError) as cleanup_error:
                            raise DesignError(
                                "generated bundle staging failed and the candidate was "
                                f"preserved at {temporary}: {cleanup_error}"
                            ) from operation_error
                    raise
                finally:
                    os.close(temporary_fd)
    except (OSError, safe_io.SafeIOError) as exc:
        raise DesignError(f"generated output path is unsafe: {out}: {exc}") from exc


def compare_bundle(
    expected: Path,
    actual: Path,
    *,
    repository_root: Path,
    actual_identity: tuple[int, int, str],
) -> None:
    """Compare pinned candidate/actual directories and rebind the actual name."""

    def display(relative: Path) -> str:
        return (actual / relative).relative_to(repository_root).as_posix()

    safe_io = _bootstrap_safe_io(repository_root)

    def read_flat_files(descriptor: int, root: Path) -> dict[str, bytes]:
        result: dict[str, bytes] = {}
        for name in sorted(os.listdir(descriptor)):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise DesignError(
                    f"generated comparison contains a non-regular entry: {root / name}"
                )
            file_descriptor = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=descriptor,
            )
            try:
                content, _ = safe_io._read_open_file(file_descriptor)
            finally:
                os.close(file_descriptor)
            result[name] = content
        return result

    try:
        with safe_io.trusted_root(expected) as expected_fd, safe_io.trusted_root(
            repository_root
        ) as repository_fd, safe_io.directory_nofollow_pinned(
            actual,
            root=repository_root,
            root_fd=repository_fd,
        ) as actual_fd:
            expected_before = pinned_directory_identity(
                expected_fd,
                display=expected,
                safe_io=safe_io,
            )
            actual_before = pinned_directory_identity(
                actual_fd,
                display=actual,
                safe_io=safe_io,
            )
            if actual_before != actual_identity:
                raise DesignError(
                    f"generated output changed after validation: {actual}"
                )
            expected_files = read_flat_files(expected_fd, expected)
            actual_files = read_flat_files(actual_fd, actual)
            if expected_files.keys() != actual_files.keys():
                missing = sorted(
                    display(Path(name)) for name in expected_files.keys() - actual_files.keys()
                )
                unexpected = sorted(
                    display(Path(name)) for name in actual_files.keys() - expected_files.keys()
                )
                raise DesignError(
                    f"generated file set drift: missing={missing} unexpected={unexpected}"
                )
            changed = [
                display(Path(name))
                for name in sorted(expected_files)
                if expected_files[name] != actual_files[name]
            ]
            if changed:
                raise DesignError("generated design drift: " + ", ".join(changed))
            if pinned_directory_identity(
                expected_fd,
                display=expected,
                safe_io=safe_io,
            ) != expected_before:
                raise DesignError(
                    f"generated comparison candidate changed while inspected: {expected}"
                )
            if pinned_directory_identity(
                actual_fd,
                display=actual,
                safe_io=safe_io,
            ) != actual_identity:
                raise DesignError(
                    f"generated output changed while compared: {actual}"
                )
            with safe_io.directory_nofollow_pinned(
                actual,
                root=repository_root,
                root_fd=repository_fd,
            ) as rebound_fd:
                rebound_identity = pinned_directory_identity(
                    rebound_fd,
                    display=actual,
                    safe_io=safe_io,
                )
            if rebound_identity != actual_identity:
                raise DesignError(
                    f"generated output name changed while compared: {actual}"
                )
    except DesignError:
        raise
    except (OSError, safe_io.SafeIOError) as exc:
        raise DesignError(f"generated comparison path is unsafe: {actual}: {exc}") from exc


def generate_fastapi(
    args: argparse.Namespace,
    out: Path,
    *,
    repository_root: Path,
    candidate: bool = False,
) -> None:
    routers = regular_files(args.source_root, repository_root, name="router.py")
    if not routers:
        raise DesignError("no router.py found")
    operations = [operation for path in routers for operation in router_operations(path)]
    if not operations:
        raise DesignError("no statically supported FastAPI route operation found")
    validate_operation_set(operations)
    openapi = load_structured(args.openapi)
    samples = load_api_samples(args.source_root)
    api, interfaces = openapi_docs(openapi, operations)
    artifact_requirements = {
        str(operation["operationId"]): list(operation.get("x-requirement-ids", []))
        for _, _, operation in openapi_operations(openapi)
    }
    traceability = traceability_view(
        args.requirements,
        args.trace,
        "operation",
        artifact_requirements,
        args.test_root,
        repository_root,
    )
    test_manifest = pytest_collection_manifest(args.test_root, repository_root)
    crud, queries = sql_docs(args.sql_root, operations)
    sql_files = regular_files(args.sql_root, repository_root, suffix=".sql")
    source_files = regular_files(args.source_root, repository_root, suffix=".py")
    sources = (
        [(f"source/{path.relative_to(args.source_root).as_posix()}", path) for path in source_files]
        + [(f"openapi/{args.openapi.name}", args.openapi)]
        + [(f"sql/{path.relative_to(args.sql_root).as_posix()}", path) for path in sql_files]
        + [("requirements/requirements.json", args.requirements), ("trace/trace.json", args.trace)]
        + [
            (f"tests/{path.relative_to(args.test_root).as_posix()}", path)
            for path in regular_files(
                args.test_root,
                repository_root,
                suffix=".py",
                name_prefix="test",
            )
        ]
    )
    files = {
        "SEQUENCES.gen.md": render_sequences(operations),
        "API_CATALOG.gen.md": api,
        "API_DETAILS.gen.md": render_api_details(operations, samples),
        "INTERFACES.gen.md": interfaces,
        "CRUD.gen.md": crud,
        "QUERY_OBJECTS.gen.md": queries,
        "ERROR_CASES.gen.json": error_case_definition(operations),
        "TEST_MANIFEST.gen.json": json.dumps(test_manifest, ensure_ascii=False, indent=2) + "\n",
        "TRACEABILITY.gen.md": traceability,
    }
    if args.ddl_root:
        ddl_files = regular_files(args.ddl_root, repository_root, suffix=".sql")
        files["DB_DESIGN.gen.md"] = ddl_docs(args.ddl_root, args.sql_root, operations)
        sources += [(f"ddl/{path.relative_to(args.ddl_root).as_posix()}", path) for path in ddl_files]
    if args.e2e_root:
        e2e_files = regular_files(
            args.e2e_root,
            repository_root,
            suffix=".py",
            name_prefix="test",
        )
        files["E2E_SCENARIOS.gen.md"] = e2e_scenarios(args.e2e_root)
        sources += [(f"e2e/{path.relative_to(args.e2e_root).as_posix()}", path) for path in e2e_files]
    if args.tool_root:
        tool_files = regular_files(args.tool_root, repository_root, suffix=".py")
        files["TOOLS.gen.md"] = tool_design(args.tool_root)
        sources += [(f"tools/{path.relative_to(args.tool_root).as_posix()}", path) for path in tool_files]
    if args.evidence:
        files["TEST_EVIDENCE.gen.md"] = evidence_view(args.evidence)
        sources.append((f"external-evidence/{args.evidence.name}", args.evidence))
    write_bundle(
        out,
        files,
        sources,
        "fastapi",
        repository_root=repository_root,
        candidate=candidate,
    )


def generate_cdk(
    args: argparse.Namespace,
    out: Path,
    *,
    repository_root: Path,
    candidate: bool = False,
) -> None:
    template = load_structured(args.template)
    resources, parameters = cfn_docs(template)
    artifact_requirements = {
        str(logical_id): cfn_requirement_ids(resource, str(logical_id))
        for logical_id, resource in sorted(template["Resources"].items())
    }
    traceability = traceability_view(
        args.requirements,
        args.trace,
        "resource",
        artifact_requirements,
        args.test_root,
        repository_root,
    )
    test_manifest = pytest_collection_manifest(args.test_root, repository_root)
    test_files = regular_files(
        args.test_root,
        repository_root,
        suffix=".py",
        name_prefix="test",
    )
    sources = [
        (f"template/{args.template.name}", args.template),
        ("requirements/requirements.json", args.requirements),
        ("trace/trace.json", args.trace),
        *[(f"tests/{path.relative_to(args.test_root).as_posix()}", path) for path in test_files],
    ]
    write_bundle(
        out,
        {
            "RESOURCES.gen.md": resources,
            "PARAMETERS.gen.md": parameters,
            "TEST_MANIFEST.gen.json": json.dumps(test_manifest, ensure_ascii=False, indent=2) + "\n",
            "TRACEABILITY.gen.md": traceability,
        },
        sources,
        "cdk",
        repository_root=repository_root,
        candidate=candidate,
    )


def normalize_repository_arguments(
    args: argparse.Namespace, repository_root: Path
) -> None:
    """Anchor every CLI path once to the explicit repository root."""

    for name in [
        "source_root",
        "openapi",
        "sql_root",
        "ddl_root",
        "e2e_root",
        "tool_root",
        "evidence",
        "requirements",
        "trace",
        "test_root",
        "template",
        "out",
    ]:
        value = getattr(args, name, None)
        if value is None:
            continue
        if any(part in {"", ".", ".."} for part in value.parts):
            raise DesignError(f"{name.replace('_', '-')} must be a lexical path: {value}")
        anchored = value if value.is_absolute() else repository_root / value
        try:
            anchored.relative_to(repository_root)
        except ValueError as exc:
            raise DesignError(
                f"{name.replace('_', '-')} escapes repository root: {value}"
            ) from exc
        setattr(args, name, anchored)


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="kind", required=True)
    fastapi = sub.add_parser("fastapi")
    fastapi.add_argument("--source-root", required=True, type=Path)
    fastapi.add_argument("--openapi", required=True, type=Path)
    fastapi.add_argument("--sql-root", required=True, type=Path)
    fastapi.add_argument("--ddl-root", type=Path)
    fastapi.add_argument("--e2e-root", type=Path)
    fastapi.add_argument("--tool-root", type=Path)
    fastapi.add_argument("--evidence", type=Path)
    fastapi.add_argument("--requirements", required=True, type=Path)
    fastapi.add_argument("--trace", required=True, type=Path)
    fastapi.add_argument("--test-root", required=True, type=Path)
    fastapi.add_argument("--out", required=True, type=Path)
    fastapi.add_argument("--repo-root", type=Path)
    fastapi.add_argument("--check", action="store_true")
    cdk = sub.add_parser("cdk")
    cdk.add_argument("--template", required=True, type=Path)
    cdk.add_argument("--requirements", required=True, type=Path)
    cdk.add_argument("--trace", required=True, type=Path)
    cdk.add_argument("--test-root", required=True, type=Path)
    cdk.add_argument("--out", required=True, type=Path)
    cdk.add_argument("--repo-root", type=Path)
    cdk.add_argument("--check", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    global _EXPLICIT_REPOSITORY_ROOT

    args = build_parser().parse_args(argv)
    original_cwd = Path.cwd()
    previous_root = _EXPLICIT_REPOSITORY_ROOT
    try:
        repository_root = (args.repo_root.resolve(strict=True) if args.repo_root else find_repository_root())
        normalize_repository_arguments(args, repository_root)
        _EXPLICIT_REPOSITORY_ROOT = repository_root
        os.chdir(repository_root)
        if args.check:
            actual, actual_identity = validate_existing_output_path(
                args.out, repository_root
            )
            with tempfile.TemporaryDirectory(prefix="designflow-check-") as directory:
                candidate = Path(directory) / actual.name
                (generate_fastapi if args.kind == "fastapi" else generate_cdk)(
                    args,
                    candidate,
                    repository_root=repository_root,
                    candidate=True,
                )
                compare_bundle(
                    candidate,
                    actual,
                    repository_root=repository_root,
                    actual_identity=actual_identity,
                )
            print(f"generated design current: {actual}")
        else:
            (generate_fastapi if args.kind == "fastapi" else generate_cdk)(
                args,
                args.out,
                repository_root=repository_root,
            )
            print(f"generated design: {args.out}")
        return 0
    except (DesignError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    finally:
        os.chdir(original_cwd)
        _EXPLICIT_REPOSITORY_ROOT = previous_root


if __name__ == "__main__":
    raise SystemExit(main())
