#!/usr/bin/env python3
"""Execute the individual as-built contracts FAST-016 through FAST-022 and AUD-008."""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import stat
import sys
import tokenize
import types
from functools import cache
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(os.path.abspath(__file__)).parent
DEFAULT_THRESHOLDS = SCRIPT_ROOT.parent / "assets" / "as-built-thresholds.json"
DEFAULT_STANDARD = SCRIPT_ROOT.parents[3] / "docs" / "standards" / "AS-BUILT-DESIGN.md"
SUPPRESSION = re.compile(r"ignore\[([A-Z][A-Z0-9-]+)\]\s*(.*)$")
UNIT_MARKERS = ("# 1. 初期化", "# 2. テストの実行", "# 3. アサーション")
GWT_MARKERS = ("# Given", "# When", "# Then")


class QualityError(RuntimeError):
    """Represent an invalid input or a blocking as-built contract failure."""


@cache
def load_designflow() -> Any:
    """Load the sibling generator without requiring package installation."""

    path = SCRIPT_ROOT / "designflow.py"
    module_name = "dev_standard_designflow"
    portable = sys.modules.get("_dev_standard_portable_imports")
    if portable is not None:
        root = SCRIPT_ROOT.parents[3]
        return portable.load_relative(
            path.relative_to(root).as_posix(),
            module_name,
        )
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(os.sep, directory_flags)
    try:
        for component in path.parent.parts[1:]:
            next_descriptor = os.open(
                component,
                directory_flags,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        source_descriptor = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=descriptor,
        )
        try:
            before = os.fstat(source_descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise QualityError(f"designflow is not a regular file: {path}")
            chunks: list[bytes] = []
            while chunk := os.read(source_descriptor, 1024 * 1024):
                chunks.append(chunk)
            after = os.fstat(source_descriptor)
            fields = (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
            if any(getattr(before, field) != getattr(after, field) for field in fields):
                raise QualityError(f"designflow changed while it was read: {path}")
        finally:
            os.close(source_descriptor)
    finally:
        os.close(descriptor)
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(compile(b"".join(chunks), str(path), "exec"), module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


def read_bytes_nofollow(path: Path) -> bytes:
    """Read one target-repository file without following lexical links."""

    portable = sys.modules.get("_dev_standard_portable_imports")
    if portable is not None:
        try:
            relative = path.absolute().relative_to(SCRIPT_ROOT.parents[3]).as_posix()
        except ValueError:
            relative = ""
        if relative and portable.contains(relative):
            return portable.read_relative(relative)
    designflow = load_designflow()
    try:
        repository_root = designflow.find_repository_root(path)
        safe_io = designflow._bootstrap_safe_io(repository_root)
        return safe_io.read_bytes_nofollow(path, root=repository_root)
    except (OSError, designflow.DesignError) as exc:
        raise QualityError(f"cannot safely read {path}: {exc}") from exc
    except safe_io.SafeIOError as exc:
        raise QualityError(f"cannot safely read {path}: {exc}") from exc


def read_text_nofollow(path: Path) -> str:
    """Decode one no-follow repository file as UTF-8."""

    return read_bytes_nofollow(path).decode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object and normalize parse failures."""

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise QualityError(f"duplicate JSON mapping key in {path}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(read_text_nofollow(path), object_pairs_hook=unique_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualityError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QualityError(f"JSON root must be an object: {path}")
    return value


def parse_python(path: Path) -> ast.Module:
    """Parse Python source with a stable diagnostic."""

    try:
        return ast.parse(read_text_nofollow(path), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise QualityError(f"cannot parse Python {path}: {exc}") from exc


def collectable_test_functions(
    tree: ast.Module,
    relative_path: str,
    collectable_nodes: set[str],
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Resolve only functions named by the portable pytest collection manifest."""

    functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if f"{relative_path}::{item.name}" in collectable_nodes:
                functions.append(item)
            continue
        if not isinstance(item, ast.ClassDef):
            continue
        for child in item.body:
            if (
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and f"{relative_path}::{item.name}::{child.name}" in collectable_nodes
            ):
                functions.append(child)
    return functions


def call_name(call: ast.Call) -> str:
    """Return a dotted call name for static contract matching."""

    parts: list[str] = []
    node: ast.AST = call.func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def literal(node: ast.AST | None, default: Any = None) -> Any:
    """Return a Python literal and reject executable expressions."""

    if node is None:
        return default
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def write_json(path: Path, value: Any, repository_root: Path) -> None:
    """Write machine output atomically inside a target-owned repository path."""

    repository_root = repository_root.absolute()
    lexical = repository_root / path if not path.is_absolute() else path
    if lexical == repository_root:
        raise QualityError(f"JSON output must name a file below repository: {path}")
    try:
        lexical.relative_to(repository_root)
    except ValueError:
        raise QualityError(f"JSON output escapes repository: {path}")
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    designflow = load_designflow()
    safe_io = designflow._bootstrap_safe_io(repository_root)
    try:
        before = safe_io.snapshot_file(lexical, root=repository_root)
        safe_io.atomic_write_cas(
            lexical,
            payload.encode("utf-8"),
            before,
            root=repository_root,
            lock_name=".designflow-quality-write.lock",
        )
    except (OSError, safe_io.SafeIOError) as exc:
        raise QualityError(f"cannot safely write JSON output {path}: {exc}") from exc


def api_consistency(source_root: Path, openapi_path: Path) -> list[str]:
    """Check handler registration, design metadata, and success/error samples."""

    designflow = load_designflow()
    repository_root = designflow.find_repository_root(source_root)
    routers = designflow.regular_files(
        source_root,
        repository_root,
        name="router.py",
    )
    operations = [item for path in routers for item in designflow.router_operations(path)]
    openapi = designflow.load_structured(openapi_path)
    try:
        designflow.validate_operation_set(operations)
        designflow.openapi_docs(openapi, operations)
    except designflow.DesignError as exc:
        return [str(exc)]
    declared: dict[tuple[str, str], dict[str, Any]] = {}
    for method, path, operation in designflow.openapi_operations(openapi):
        declared[(method, path)] = operation
    samples = designflow.load_api_samples(source_root)
    failures: list[str] = []
    observed: set[tuple[str, str]] = set()
    for handler in operations:
        key = (handler["method"], handler["path"])
        operation = declared.get(key)
        if operation is None:
            failures.append(f"handler not registered in OpenAPI: {key[0]} {key[1]}")
            continue
        observed.add(key)
        operation_id = str(operation.get("operationId") or handler["operation_id"])
        metadata = {**handler.get("metadata", {}), **{name: value for name, value in operation.items() if name.startswith("x-")}}
        for name in ("x-api-number", "x-permission", "x-business-summary"):
            if not metadata.get(name):
                failures.append(f"{operation_id}: metadata missing: {name}")
        if f"{operation_id}:success" not in samples:
            failures.append(f"{operation_id}: success sample missing")
        for error in handler["errors"]:
            if f"{operation_id}:{error['id']}" not in samples:
                failures.append(f"{operation_id}: error sample missing: {error['id']}")
    for method, path in sorted(set(declared) - observed):
        failures.append(f"OpenAPI operation has no handler: {method} {path}")
    return failures


def runtime_response_call(call: ast.Call, trusted_adapters: set[str]) -> bool:
    """Recognize an actual client invocation or a locally verified adapter."""

    name = call_name(call).lower()
    parts = name.split(".")
    if name in trusted_adapters:
        return True
    return (
        parts[-1] in {"delete", "get", "head", "options", "patch", "post", "put", "request"}
        and any(part.endswith("client") or part in {"client", "httpx", "requests"} for part in parts[:-1])
    )


def expression_has_provenance(
    node: ast.AST,
    names: set[str],
    trusted_adapters: set[str],
) -> bool:
    """Return whether an expression derives from a runtime response."""

    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, (ast.Await, ast.Starred)):
        return expression_has_provenance(node.value, names, trusted_adapters)
    if isinstance(node, ast.Attribute):
        return expression_has_provenance(node.value, names, trusted_adapters)
    if isinstance(node, ast.Subscript):
        return expression_has_provenance(node.value, names, trusted_adapters)
    if isinstance(node, ast.Call):
        if runtime_response_call(node, trusted_adapters):
            return True
        return isinstance(node.func, ast.Attribute) and expression_has_provenance(
            node.func.value,
            names,
            trusted_adapters,
        )
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return bool(node.elts) and all(
            expression_has_provenance(item, names, trusted_adapters)
            for item in node.elts
        )
    if isinstance(node, ast.Dict):
        return bool(node.values) and all(
            expression_has_provenance(item, names, trusted_adapters)
            for item in node.values
        )
    return False


def target_names(target: ast.AST) -> set[str]:
    """Return names whose prior provenance an assignment invalidates."""

    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Starred):
        return target_names(target.value)
    if isinstance(target, (ast.List, ast.Tuple)):
        return set().union(*(target_names(item) for item in target.elts))
    if isinstance(target, (ast.Attribute, ast.Subscript)):
        return {
            item.id
            for item in ast.walk(target.value)
            if isinstance(item, ast.Name)
        }
    return set()


def assigned_names(node: ast.Assign | ast.AnnAssign) -> set[str]:
    """Return simple assignment targets used for conservative provenance flow."""

    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return set().union(*(target_names(target) for target in targets))


def assigned_provenance(
    target: ast.AST,
    value: ast.AST,
    names: set[str],
    trusted_adapters: set[str],
) -> set[str]:
    """Map a supported assignment target to only its response-derived values."""

    if isinstance(target, ast.Name):
        return (
            {target.id}
            if expression_has_provenance(value, names, trusted_adapters)
            else set()
        )
    if isinstance(target, ast.Starred):
        return assigned_provenance(target.value, value, names, trusted_adapters)
    if isinstance(target, (ast.List, ast.Tuple)):
        if isinstance(value, (ast.List, ast.Tuple)) and len(target.elts) == len(value.elts):
            return set().union(
                *(
                    assigned_provenance(child_target, child_value, names, trusted_adapters)
                    for child_target, child_value in zip(target.elts, value.elts, strict=True)
                )
            )
        if expression_has_provenance(value, names, trusted_adapters):
            return set().union(*(target_names(item) for item in target.elts))
    return set()


def sample_keys(node: ast.AST) -> set[str]:
    """Return literal API sample keys referenced by an expression."""

    result: set[str] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Subscript):
            continue
        owner = item.value
        if isinstance(owner, ast.Name) and owner.id == "API_SAMPLES":
            key = literal(item.slice)
            if isinstance(key, str):
                result.add(key)
    return result


def direct_sample_keys(node: ast.AST) -> set[str]:
    """Return a sample key only when the compared value is that exact sample."""

    if not isinstance(node, ast.Subscript):
        return set()
    owner = node.value
    if not isinstance(owner, ast.Name) or owner.id != "API_SAMPLES":
        return set()
    key = literal(node.slice)
    return {key} if isinstance(key, str) else set()


def verified_runtime_adapters(tree: ast.Module, path: Path) -> tuple[set[str], list[str]]:
    """Find explicit adapters that return client-derived values on every path."""

    adapters: set[str] = set()
    failures: list[str] = []
    for function in (
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        declarations = [
            decorator
            for decorator in function.decorator_list
            if isinstance(decorator, ast.Call)
            and call_name(decorator).split(".")[-1] == "trusted_runtime_response_adapter"
        ]
        if not declarations:
            continue
        if len(declarations) != 1:
            failures.append(f"{path}:{function.name}: duplicate trusted adapter declaration")
            continue
        declaration = declarations[0]
        authority = literal(declaration.args[0]) if len(declaration.args) == 1 else None
        if not isinstance(authority, str) or not authority.strip() or declaration.keywords:
            failures.append(
                f"{path}:{function.name}: trusted adapter requires one literal authority ID"
            )
            continue
        remaining, returns, flow_failures = analyze_adapter_block(
            function.body,
            [set()],
            label=f"{path}:{function.name}",
        )
        if flow_failures:
            failures.extend(flow_failures)
            continue
        if returns == 0 or remaining:
            failures.append(
                f"{path}:{function.name}: trusted adapter must return a recognized "
                "runtime client value on every path"
            )
            continue
        adapters.add(function.name.lower())
    return adapters, failures


def analyze_adapter_block(
    statements: list[ast.stmt],
    states: list[set[str]],
    *,
    label: str,
) -> tuple[list[set[str]], int, list[str]]:
    """Verify that every adapter return is data-dependent on a real client call."""

    current = [set(state) for state in states]
    returns = 0
    failures: list[str] = []
    for statement in statements:
        if not current:
            break
        if isinstance(statement, ast.If):
            body_states, body_returns, body_failures = analyze_adapter_block(
                statement.body,
                current,
                label=label,
            )
            if statement.orelse:
                else_states, else_returns, else_failures = analyze_adapter_block(
                    statement.orelse,
                    current,
                    label=label,
                )
            else:
                else_states, else_returns, else_failures = (
                    [set(state) for state in current],
                    0,
                    [],
                )
            current = [*body_states, *else_states]
            returns += body_returns + else_returns
            failures.extend([*body_failures, *else_failures])
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            killed = assigned_names(statement)
            updated: list[set[str]] = []
            for provenance in current:
                next_state = provenance - killed
                if statement.value is not None:
                    next_state.update(
                        set().union(
                            *(
                                assigned_provenance(target, statement.value, provenance, set())
                                for target in targets
                            )
                        )
                    )
                updated.append(next_state)
            current = updated
            continue
        if isinstance(statement, ast.AugAssign):
            killed = target_names(statement.target)
            current = [state - killed for state in current]
            continue
        if isinstance(statement, ast.Return):
            returns += 1
            if statement.value is None or any(
                not expression_has_provenance(statement.value, state, set())
                for state in current
            ):
                failures.append(
                    f"{label}:{statement.lineno}: trusted adapter return lacks runtime "
                    "client provenance on every reaching branch"
                )
            current = []
            continue
        if isinstance(statement, ast.Raise):
            current = []
            continue
        if isinstance(
            statement,
            (
                ast.AsyncFor,
                ast.AsyncWith,
                ast.For,
                ast.Match,
                ast.Try,
                ast.While,
                ast.With,
            ),
        ):
            failures.append(
                f"{label}:{statement.lineno}: unsupported trusted adapter flow: "
                f"{type(statement).__name__}"
            )
    return current, returns, failures


def asserted_keys_in_assertion(
    assertion: ast.Assert,
    states: list[set[str]],
    trusted_adapters: set[str],
) -> set[str]:
    """Return keys whose equality has response provenance on every path."""

    per_state: list[set[str]] = []
    for provenance in states:
        state_keys: set[str] = set()
        for comparison in (
            [assertion.test] if isinstance(assertion.test, ast.Compare) else []
        ):
            operands = [comparison.left, *comparison.comparators]
            for index, operator in enumerate(comparison.ops):
                if not isinstance(operator, ast.Eq):
                    continue
                left, right = operands[index], operands[index + 1]
                if expression_has_provenance(left, provenance, trusted_adapters):
                    state_keys.update(direct_sample_keys(right))
                if expression_has_provenance(right, provenance, trusted_adapters):
                    state_keys.update(direct_sample_keys(left))
        per_state.append(state_keys)
    return set.intersection(*per_state) if per_state else set()


def asserted_keys_in_call(
    call: ast.Call,
    states: list[set[str]],
    trusted_adapters: set[str],
) -> set[str]:
    """Recognize unittest-style two-operand equality assertions."""

    if call_name(call).split(".")[-1] not in {"assertDictEqual", "assertEqual"}:
        return set()
    if len(call.args) < 2:
        return set()
    left, right = call.args[:2]
    per_state: list[set[str]] = []
    for provenance in states:
        state_keys: set[str] = set()
        if expression_has_provenance(left, provenance, trusted_adapters):
            state_keys.update(direct_sample_keys(right))
        if expression_has_provenance(right, provenance, trusted_adapters):
            state_keys.update(direct_sample_keys(left))
        per_state.append(state_keys)
    return set.intersection(*per_state) if per_state else set()


def analyze_provenance_block(
    statements: list[ast.stmt],
    states: list[set[str]],
    trusted_adapters: set[str],
    *,
    label: str,
) -> tuple[list[set[str]], set[str], list[str]]:
    """Run a forward, branch-aware, reassignment-killing provenance analysis."""

    keys: set[str] = set()
    failures: list[str] = []
    current = [set(state) for state in states]
    for statement in statements:
        if not current:
            break
        if isinstance(statement, ast.If):
            body_states, body_keys, body_failures = analyze_provenance_block(
                statement.body,
                current,
                trusted_adapters,
                label=label,
            )
            if statement.orelse:
                else_states, else_keys, else_failures = analyze_provenance_block(
                    statement.orelse,
                    current,
                    trusted_adapters,
                    label=label,
                )
            else:
                else_states, else_keys, else_failures = (
                    [set(state) for state in current],
                    set(),
                    [],
                )
            current = [*body_states, *else_states]
            keys.update(body_keys | else_keys)
            failures.extend([*body_failures, *else_failures])
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = assigned_names(statement)
            assignment_targets = (
                statement.targets
                if isinstance(statement, ast.Assign)
                else [statement.target]
            )
            updated: list[set[str]] = []
            for provenance in current:
                next_state = provenance - targets
                value = statement.value
                if value is not None:
                    next_state.update(
                        set().union(
                            *(
                                assigned_provenance(
                                    target,
                                    value,
                                    provenance,
                                    trusted_adapters,
                                )
                                for target in assignment_targets
                            )
                        )
                    )
                updated.append(next_state)
            current = updated
            continue
        if isinstance(statement, ast.AugAssign):
            target_names = {
                node.id for node in ast.walk(statement.target) if isinstance(node, ast.Name)
            }
            current = [state - target_names for state in current]
            continue
        if isinstance(statement, ast.Assert):
            validated = asserted_keys_in_assertion(statement, current, trusted_adapters)
            referenced = sample_keys(statement.test)
            keys.update(validated)
            for key in sorted(referenced - validated):
                failures.append(
                    f"{label}:{statement.lineno}: sample assertion lacks runtime provenance "
                    f"on every reaching branch: {key}"
                )
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            validated = asserted_keys_in_call(
                statement.value,
                current,
                trusted_adapters,
            )
            referenced = sample_keys(statement.value)
            if referenced:
                keys.update(validated)
                for key in sorted(referenced - validated):
                    failures.append(
                        f"{label}:{statement.lineno}: sample assertion lacks runtime "
                        f"provenance on every reaching branch: {key}"
                    )
            continue
        if isinstance(statement, (ast.Return, ast.Raise)):
            current = []
            continue
        if isinstance(
            statement,
            (
                ast.AsyncFor,
                ast.AsyncWith,
                ast.For,
                ast.Match,
                ast.Try,
                ast.While,
                ast.With,
            ),
        ):
            failures.append(
                f"{label}:{statement.lineno}: unsupported provenance flow: "
                f"{type(statement).__name__}"
            )
    return current, keys, failures


def asserted_sample_keys(test_root: Path) -> tuple[set[str], list[str]]:
    """Collect samples asserted against branch-safe runtime response values."""

    designflow = load_designflow()
    repository_root = designflow.find_repository_root(test_root)
    keys: set[str] = set()
    failures: list[str] = []
    manifest = designflow.pytest_collection_manifest(test_root, repository_root)
    collectable_nodes = set(manifest["nodes"])
    paths = designflow.regular_files(
        test_root,
        repository_root,
        suffix=".py",
        name_prefix="test",
    )
    for path in paths:
        tree = parse_python(path)
        adapters, adapter_failures = verified_runtime_adapters(tree, path)
        failures.extend(adapter_failures)
        relative = path.relative_to(repository_root).as_posix()
        functions = collectable_test_functions(
            tree,
            relative,
            collectable_nodes,
        )
        for function in functions:
            _, function_keys, function_failures = analyze_provenance_block(
                function.body,
                [set()],
                adapters,
                label=f"{path}:{function.name}",
            )
            keys.update(function_keys)
            failures.extend(function_failures)
    return keys, failures


def sample_consistency(source_root: Path, test_root: Path) -> list[str]:
    """Check that every design sample is asserted against an actual response value."""

    samples = load_designflow().load_api_samples(source_root)
    asserted, failures = asserted_sample_keys(test_root)
    return [*failures, *[
        f"sample is not asserted against a runtime response: {key}"
        for key in sorted(set(samples) - asserted)
    ]]


def function_calls(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Call]:
    """Return calls contained in one test function."""

    return [node for node in ast.walk(function) if isinstance(node, ast.Call)]


def declaration(call: ast.Call, name: str) -> str | None:
    """Read a literal ID from a named decorator or call."""

    if call_name(call).split(".")[-1] != name or not call.args:
        return None
    value = literal(call.args[0])
    return value if isinstance(value, str) else None


def crud_e2e_consistency(source_root: Path, sql_root: Path, e2e_root: Path) -> list[str]:
    """Check DB and external effects against effect-specific E2E assertions."""

    designflow = load_designflow()
    repository_root = designflow.find_repository_root(source_root)
    routers = designflow.regular_files(
        source_root,
        repository_root,
        name="router.py",
    )
    operations = [item for path in routers for item in designflow.router_operations(path)]
    queries, _ = designflow.parse_sql(sql_root)
    bindings = designflow.bind_operation_queries(operations, queries)
    success: dict[str, set[str]] = {}
    errors: dict[str, set[str]] = {}
    allowed_reasons: dict[tuple[str, str], list[str]] = {}
    manifest = designflow.pytest_collection_manifest(e2e_root, repository_root)
    collectable_nodes = set(manifest["nodes"])
    for path in designflow.regular_files(
        e2e_root,
        repository_root,
        suffix=".py",
        name_prefix="test",
    ):
        tree = parse_python(path)
        relative = path.relative_to(repository_root).as_posix()
        for function in collectable_test_functions(
            tree,
            relative,
            collectable_nodes,
        ):
            calls = function_calls(function)
            operation_ids = {value for call in [*function.decorator_list, *calls] if isinstance(call, ast.Call) and (value := declaration(call, "operation"))}
            case_ids = {value for call in [*function.decorator_list, *calls] if isinstance(call, ast.Call) and (value := declaration(call, "covers"))}
            names = {call_name(call).split(".")[-1] for call in calls}
            for operation_id in operation_ids:
                success.setdefault(operation_id, set()).update(names)
            for case_id in case_ids:
                errors.setdefault(case_id, set()).update(names)
                for call in calls:
                    marker = call_name(call).split(".")[-1]
                    if marker in {
                        "assert_allowed_db_state_change",
                        "assert_allowed_external_state_change",
                    }:
                        reason = literal(call.args[0]) if call.args else None
                        if isinstance(reason, str) and reason.strip():
                            effect = "db" if "_db_" in marker else "external"
                            allowed_reasons.setdefault((case_id, effect), []).append(reason)
    failures: list[str] = []
    for operation in operations:
        operation_id = str(operation["operation_id"])
        writes_db = any(
            query["letter"] in {"C", "U", "D"}
            for query in bindings[operation_id]
        )
        writes_external = bool(operation.get("external_effects"))
        if writes_db and "assert_db_state" not in success.get(operation_id, set()):
            failures.append(f"{operation_id}: DB write lacks assert_db_state")
        if writes_external and "assert_external_state" not in success.get(operation_id, set()):
            failures.append(f"{operation_id}: external write lacks assert_external_state")
        for error in operation["errors"]:
            calls = errors.get(error["id"], set())
            if not calls:
                failures.append(f"{operation_id}: error case lacks covers declaration: {error['id']}")
                continue
            for effect, enabled in (("db", writes_db), ("external", writes_external)):
                if not enabled:
                    continue
                unchanged = f"assert_{effect}_state_unchanged"
                allowed = f"assert_allowed_{effect}_state_change"
                if not calls.intersection({unchanged, allowed}):
                    failures.append(
                        f"{operation_id}: {effect} error effect lacks {unchanged} or {allowed}: "
                        f"{error['id']}"
                    )
                elif allowed in calls and not allowed_reasons.get((error["id"], effect)):
                    failures.append(
                        f"{operation_id}: allowed {effect} state change lacks a reason: {error['id']}"
                    )
    return failures


def coverage_result(path: Path, thresholds_path: Path) -> dict[str, Any]:
    """Evaluate statement and branch coverage against the declared advisory targets."""

    document = read_json(path)
    totals = document.get("totals")
    if not isinstance(totals, dict):
        raise QualityError("coverage JSON has no totals object")
    def count(name: str) -> int:
        value = totals.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise QualityError(f"coverage count must be an integer: {name}")
        return value

    statements = count("num_statements")
    covered_statements = count("covered_lines")
    branches = count("num_branches")
    covered_branches = count("covered_branches")
    if statements <= 0 or branches <= 0:
        raise QualityError("statement and branch coverage must both be measurable")
    if not 0 <= covered_statements <= statements:
        raise QualityError("covered statement count is outside 0..num_statements")
    if not 0 <= covered_branches <= branches:
        raise QualityError("covered branch count is outside 0..num_branches")
    statement_percent = covered_statements * 100 / statements
    branch_percent = covered_branches * 100 / branches
    targets = read_json(thresholds_path).get("coverage")
    if not isinstance(targets, dict):
        raise QualityError("coverage thresholds require a coverage object")
    for name in ("statement_percent", "branch_percent"):
        value = targets.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise QualityError(f"coverage threshold must be within 0..100: {name}")
    if targets.get("enforcement") != "advisory":
        raise QualityError("bundled coverage enforcement must remain advisory")
    return {
        "check_id": "FAST-019",
        "enforcement": targets["enforcement"],
        "statement_percent": round(statement_percent, 2),
        "branch_percent": round(branch_percent, 2),
        "statement_target": targets["statement_percent"],
        "branch_target": targets["branch_percent"],
        "status": "pass" if statement_percent >= targets["statement_percent"] and branch_percent >= targets["branch_percent"] else "advisory",
    }


def test_structure(root: Path, mode: str) -> list[str]:
    """Evaluate test docstrings, one-case functions, and AAA/GWT source markers."""

    failures: list[str] = []
    markers = UNIT_MARKERS if mode == "unit" else GWT_MARKERS
    designflow = load_designflow()
    repository_root = designflow.find_repository_root(root)
    manifest = designflow.pytest_collection_manifest(root, repository_root)
    collectable_nodes = set(manifest["nodes"])
    for path in designflow.regular_files(
        root,
        repository_root,
        suffix=".py",
        name_prefix="test",
    ):
        text = read_text_nofollow(path)
        lines = text.splitlines()
        tree = parse_python(path)
        relative = path.relative_to(repository_root).as_posix()
        for function in collectable_test_functions(
            tree,
            relative,
            collectable_nodes,
        ):
            label = f"{path}:{function.name}"
            if not ast.get_docstring(function):
                failures.append(f"{label}: docstring missing")
            body = "\n".join(lines[function.lineno - 1 : function.end_lineno or function.lineno])
            positions = [body.find(marker) for marker in markers]
            if any(position < 0 for position in positions) or positions != sorted(positions):
                failures.append(f"{label}: {'AAA' if mode == 'unit' else 'GWT'} markers missing or out of order")
            if any(isinstance(node, (ast.For, ast.While, ast.comprehension)) for node in ast.walk(function)):
                failures.append(f"{label}: one-case function contains iteration")
            if any(isinstance(decorator, ast.Call) and call_name(decorator).endswith("parametrize") for decorator in function.decorator_list):
                failures.append(f"{label}: parametrization hides multiple cases")
    return failures


def implementation_structure(root: Path) -> list[str]:
    """Evaluate analyzable endpoint, layer, SQL, and generator-tool conventions."""

    failures: list[str] = []
    designflow = load_designflow()
    repository_root = designflow.find_repository_root(root)
    for router in designflow.regular_files(
        root,
        repository_root,
        name="router.py",
    ):
        sibling = router.with_name("functions.py")
        if not sibling.is_file():
            failures.append(f"{router}: sibling functions.py missing")
        tree = parse_python(router)
        for function in (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            names = {call_name(call).lower() for call in ast.walk(function) if isinstance(call, ast.Call)}
            prohibited = sorted(name for name in names if name == "print" or name.startswith(("boto3.", "requests.", "httpx.")))
            if prohibited:
                failures.append(f"{router}:{function.name}: direct infrastructure call: {', '.join(prohibited)}")
    for functions in designflow.regular_files(
        root,
        repository_root,
        name="functions.py",
    ):
        tree = parse_python(functions)
        for function in (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            if not ast.get_docstring(function):
                failures.append(f"{functions}:{function.name}: responsibility docstring missing")
    for sql in designflow.regular_files(
        root,
        repository_root,
        suffix=".sql",
    ):
        text = read_text_nofollow(sql)
        try:
            statements = [
                item
                for item in load_designflow().sqlglot.parse(text, error_level="RAISE")
                if item is not None
            ]
        except Exception as exc:
            failures.append(f"{sql}: invalid SQL: {type(exc).__name__}: {exc}")
            continue
        if len(statements) != 1:
            failures.append(f"{sql}: expected one SQL statement")
        elif not isinstance(
            statements[0],
            (
                load_designflow().exp.Delete,
                load_designflow().exp.Insert,
                load_designflow().exp.Select,
                load_designflow().exp.Update,
            ),
        ):
            failures.append(
                f"{sql}: unsupported SQL statement: {type(statements[0]).__name__}"
            )
        if not text.lstrip().startswith("--"):
            failures.append(f"{sql}: natural-language summary comment missing")
    return failures


EXPECTED_THRESHOLDS = {
    "coverage": {"statement_percent": 95, "branch_percent": 90, "enforcement": "advisory"},
    "application": {
        "complexity_per_function": 10,
        "control_nesting": 3,
        "function_logical_lines": 50,
        "router_logical_lines": 200,
        "file_logical_lines": 400,
        "arguments": 3,
        "returns_per_function": 4,
        "boolean_operators": 2,
        "ternary_nesting": 0,
    },
    "tool": {
        "complexity_per_function": 12,
        "control_nesting": 4,
        "function_logical_lines": 30,
        "file_logical_lines": 500,
        "arguments": 8,
        "returns_per_function": 5,
        "boolean_operators": 2,
        "ternary_nesting": 0,
    },
}


def threshold_consistency(path: Path) -> list[str]:
    """Compare machine thresholds and linter delegation with the standard contract."""

    document = read_json(path)
    failures = [f"threshold group differs from standard: {key}" for key, expected in EXPECTED_THRESHOLDS.items() if document.get(key) != expected]
    delegation = document.get("linter_delegation", {})
    for rule in ("LIMIT-DO-001", "LIMIT-DO-002", "RULE-DO-002"):
        if not isinstance(delegation, dict) or not delegation.get(rule):
            failures.append(f"linter delegation missing: {rule}")
    return failures


def standard_rule_ids(path: Path) -> set[str]:
    """Extract authoritative Rule IDs from the standard tables."""

    return set(re.findall(r"\| `([A-Z][A-Z0-9-]+)` \|", read_text_nofollow(path)))


def suppression_lines(path: Path) -> list[tuple[int, str]]:
    """Return comments from Python and literal lines from other text files."""

    try:
        text = read_text_nofollow(path)
    except UnicodeDecodeError:
        return []
    if path.suffix != ".py":
        return list(enumerate(text.splitlines(), 1))
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        return [(token.start[0], token.string) for token in tokens if token.type == tokenize.COMMENT]
    except (IndentationError, tokenize.TokenError) as exc:
        raise QualityError(f"cannot tokenize Python {path}: {exc}") from exc


def suppression_inventory(root: Path, standard: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Inventory reasoned suppressions and reject silent, orphan, or duplicate entries."""

    valid = standard_rule_ids(standard)
    inventory: list[dict[str, Any]] = []
    failures: list[str] = []
    seen: set[tuple[str, str]] = set()
    ignored = {".git", ".venv", ".devflow", "__pycache__"}
    designflow = load_designflow()
    repository_root = designflow.find_repository_root(root)
    for path in (
        item
        for item in designflow.regular_files(root, repository_root)
        if not ignored.intersection(item.parts)
    ):
        for line_number, line in suppression_lines(path):
            match = SUPPRESSION.search(line)
            if not match:
                continue
            rule_id, reason = match.group(1), match.group(2).strip()
            key = (path.relative_to(root).as_posix(), rule_id)
            inventory.append({"path": key[0], "line": line_number, "rule_id": rule_id, "reason": reason})
            if not reason:
                failures.append(f"{key[0]}:{line_number}: suppression reason missing")
            if rule_id not in valid:
                failures.append(f"{key[0]}:{line_number}: orphan Rule ID: {rule_id}")
            if key in seen:
                failures.append(f"{key[0]}:{line_number}: duplicate suppression: {rule_id}")
            seen.add(key)
    return inventory, failures


def print_findings(check_id: str, failures: list[str], *, advisory: bool) -> int:
    """Print one check outcome and map advisory findings to a successful exit."""

    status = "PASS" if not failures else ("ADVISORY" if advisory else "FAIL")
    print(f"{check_id}: {status}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if advisory or not failures else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the quality contract command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    api = sub.add_parser("api")
    api.add_argument("--source-root", required=True, type=Path)
    api.add_argument("--openapi", required=True, type=Path)
    samples = sub.add_parser("samples")
    samples.add_argument("--source-root", required=True, type=Path)
    samples.add_argument("--test-root", required=True, type=Path)
    crud = sub.add_parser("crud-e2e")
    crud.add_argument("--source-root", required=True, type=Path)
    crud.add_argument("--sql-root", required=True, type=Path)
    crud.add_argument("--e2e-root", required=True, type=Path)
    coverage = sub.add_parser("coverage")
    coverage.add_argument("--input", required=True, type=Path)
    coverage.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    coverage.add_argument("--enforce", action="store_true")
    structure = sub.add_parser("test-structure")
    structure.add_argument("--root", required=True, type=Path)
    structure.add_argument("--mode", choices=["unit", "e2e"], required=True)
    structure.add_argument("--enforce", action="store_true")
    implementation = sub.add_parser("implementation")
    implementation.add_argument("--root", required=True, type=Path)
    implementation.add_argument("--enforce", action="store_true")
    thresholds = sub.add_parser("thresholds")
    thresholds.add_argument("--config", type=Path, default=DEFAULT_THRESHOLDS)
    suppressions = sub.add_parser("suppressions")
    suppressions.add_argument("--root", required=True, type=Path)
    suppressions.add_argument("--standard", type=Path, default=DEFAULT_STANDARD)
    suppressions.add_argument("--json-out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute one declared quality contract."""

    args = build_parser().parse_args(argv)
    try:
        if args.command == "api":
            return print_findings("FAST-016", api_consistency(args.source_root, args.openapi), advisory=False)
        if args.command == "samples":
            return print_findings("FAST-017", sample_consistency(args.source_root, args.test_root), advisory=False)
        if args.command == "crud-e2e":
            return print_findings("FAST-018", crud_e2e_consistency(args.source_root, args.sql_root, args.e2e_root), advisory=False)
        if args.command == "coverage":
            result = coverage_result(args.input, args.thresholds)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if args.enforce and result["status"] != "pass" else 0
        if args.command == "test-structure":
            return print_findings("FAST-020", test_structure(args.root, args.mode), advisory=not args.enforce)
        if args.command == "implementation":
            return print_findings("FAST-021", implementation_structure(args.root), advisory=not args.enforce)
        if args.command == "thresholds":
            return print_findings("FAST-022", threshold_consistency(args.config), advisory=False)
        if args.command == "suppressions":
            inventory, failures = suppression_inventory(args.root, args.standard)
            if args.json_out:
                write_json(args.json_out, {"schema_version": 1, "suppressions": inventory}, args.root)
            return print_findings("AUD-008", failures, advisory=False)
        raise QualityError(f"unsupported quality command: {args.command}")
    except (
        QualityError,
        load_designflow().DesignError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
