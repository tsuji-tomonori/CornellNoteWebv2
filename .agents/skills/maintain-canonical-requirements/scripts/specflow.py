#!/usr/bin/env python3
"""Quintから生成された要件JSONを検証し、人向け文書へ描画する。"""

from __future__ import annotations

import argparse
import copy
import html
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_PORTABLE_IMPORTS = sys.modules.get("_dev_standard_portable_imports")
if _PORTABLE_IMPORTS is not None:
    _safe_io = _PORTABLE_IMPORTS.load_relative(
        "tools/safe_io.py",
        "dev_standard_specflow_safe_io",
    )
    FileSnapshot = _safe_io.FileSnapshot
    SafeIOError = _safe_io.SafeIOError
    atomic_write_cas = _safe_io.atomic_write_cas
    read_bytes_nofollow = _safe_io.read_bytes_nofollow
    snapshot_file = _safe_io.snapshot_file
else:
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    from tools.safe_io import (  # noqa: E402
        FileSnapshot,
        SafeIOError,
        atomic_write_cas,
        read_bytes_nofollow,
        snapshot_file,
    )


class SpecError(RuntimeError):
    pass


STATUSES = {"active", "retired"}
TYPES = {"functional", "quality", "constraint", "interface", "data", "operational"}
SCOPES = {"product", "project"}
CATEGORIES = {"functional", "nonfunctional"}
ACTIONS = {
    "constrain",
    "derive",
    "detect",
    "discover",
    "enable",
    "enforce",
    "estimate",
    "expand",
    "formalize",
    "generate",
    "maintain",
    "measure",
    "parse",
    "preserve",
    "provide",
    "route",
    "select",
    "separate",
    "stage",
    "stop",
    "structure",
    "validate",
    "verify",
}
TRACE_KEYS = {"design", "implementation", "tests", "standards"}
REQUIREMENT_FIELDS = {
    "id",
    "revision",
    "status",
    "type",
    "title",
    "subject",
    "action",
    "object",
    "rationale",
    "source_refs",
    "acceptance_criteria",
    "verification",
    "traces",
    "last_changed_by",
    "retirement_reason",
    "superseded_by",
    "scope",
    "category",
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(read_bytes_nofollow(path, root=REPOSITORY_ROOT).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SafeIOError) as exc:
        raise SpecError(f"cannot read JSON {path}: {exc}") from exc


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise SpecError(f"{label} must be a non-empty string")
    return value


def validate_classification(item: dict[str, Any], rid: str) -> None:
    if not isinstance(item["scope"], str) or not isinstance(item["category"], str):
        raise SpecError(f"{rid}: scope and category must be strings")
    if (item["scope"] == "") != (item["category"] == ""):
        raise SpecError(f"{rid}: scope and category must be specified together")
    if item["scope"] == "":
        return
    if item["scope"] not in SCOPES:
        raise SpecError(f"{rid}: invalid scope")
    if item["category"] not in CATEGORIES:
        raise SpecError(f"{rid}: invalid category")


def _validate_trace_paths(rid: str, traces: dict[str, Any], trace_root: Path | None) -> None:
    for key, values in traces.items():
        canonical: list[str] = []
        for value in values:
            if key == "standards":
                canonical.append(value)
                continue
            raw_parts = value.split("/")
            relative = PurePosixPath(value)
            if (
                "\\" in value
                or relative.is_absolute()
                or not relative.parts
                or any(part in {"", ".", ".."} for part in raw_parts)
                or relative.as_posix() != value
            ):
                raise SpecError(
                    f"{rid}: {key} trace must use canonical repository-relative spelling: {value}"
                )
            canonical.append(relative.as_posix())
            if trace_root is None:
                continue
            candidate = trace_root.joinpath(*relative.parts)
            try:
                read_bytes_nofollow(candidate, root=trace_root)
            except (OSError, SafeIOError) as exc:
                raise SpecError(
                    f"{rid}: {key} trace is not a regular repository file: {value}"
                ) from exc
        if len(canonical) != len(set(canonical)):
            raise SpecError(f"{rid}: duplicate {key} trace")


def validate_requirement(item: Any, seen_ac: set[str], trace_root: Path | None) -> None:
    if not isinstance(item, dict):
        raise SpecError("each requirement must be an object")
    missing = REQUIREMENT_FIELDS - set(item)
    extra = set(item) - REQUIREMENT_FIELDS
    if missing or extra:
        raise SpecError(f"requirement fields invalid: missing={sorted(missing)} extra={sorted(extra)}")
    rid = nonempty(item["id"], "id")
    if type(item["revision"]) is not int or item["revision"] < 1:
        raise SpecError(f"{rid}: revision must be a positive integer")
    if (
        not isinstance(item["status"], str)
        or not isinstance(item["type"], str)
        or item["status"] not in STATUSES
        or item["type"] not in TYPES
    ):
        raise SpecError(f"{rid}: invalid status or type")
    validate_classification(item, rid)
    for key in ["title", "subject", "object", "rationale", "last_changed_by"]:
        nonempty(item[key], f"{rid}.{key}")
    action = nonempty(item["action"], f"{rid}.action")
    if action not in ACTIONS:
        raise SpecError(f"{rid}.action must be one allowed normalized verb token")
    if not isinstance(item["source_refs"], list) or not item["source_refs"]:
        raise SpecError(f"{rid}: source_refs required")
    if any(not isinstance(value, str) or value == "" for value in item["source_refs"]):
        raise SpecError(f"{rid}: source_refs must contain non-empty strings")
    if len(item["source_refs"]) != len(set(item["source_refs"])):
        raise SpecError(f"{rid}: duplicate source_refs")
    criteria = item["acceptance_criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise SpecError(f"{rid}: acceptance_criteria required")
    for criterion in criteria:
        if not isinstance(criterion, dict) or set(criterion) != {"id", "given", "when", "then"}:
            raise SpecError(f"{rid}: each criterion needs id/given/when/then only")
        cid = nonempty(criterion["id"], f"{rid}.criterion.id")
        if cid in seen_ac:
            raise SpecError(f"duplicate acceptance criterion: {cid}")
        seen_ac.add(cid)
        for key in ["given", "when", "then"]:
            nonempty(criterion[key], f"{cid}.{key}")
    verification = item["verification"]
    if not isinstance(verification, dict) or set(verification) != {"method", "evidence"}:
        raise SpecError(f"{rid}: verification needs method/evidence")
    nonempty(verification["method"], f"{rid}.verification.method")
    nonempty(verification["evidence"], f"{rid}.verification.evidence")
    traces = item["traces"]
    if not isinstance(traces, dict) or set(traces) != TRACE_KEYS:
        raise SpecError(f"{rid}: traces must contain {sorted(TRACE_KEYS)}")
    if any(
        not isinstance(values, list)
        or any(not isinstance(value, str) or value == "" for value in values)
        for values in traces.values()
    ):
        raise SpecError(f"{rid}: trace values must be string lists")
    _validate_trace_paths(rid, traces, trace_root)

    for field in ["retirement_reason", "superseded_by"]:
        if not isinstance(item[field], str):
            raise SpecError(f"{rid}: {field} must be a string")
    retirement_reason = item["retirement_reason"]
    superseded_by = item["superseded_by"]
    if item["status"] == "active" and (retirement_reason != "" or superseded_by != ""):
        raise SpecError(f"{rid}: active requirement cannot contain retirement fields")
    if item["status"] == "retired" and retirement_reason == "":
        raise SpecError(f"{rid}: retired requirement needs retirement_reason")


def validate_supersession_graph(requirements: list[dict[str, Any]]) -> None:
    """Require every supersession chain to be ordered, acyclic, and active-ended."""

    by_id = {item["id"]: item for item in requirements}
    indices = {item["id"]: index for index, item in enumerate(requirements)}
    for source in requirements:
        successor_id = source["superseded_by"]
        if successor_id == "":
            continue
        successor = by_id.get(successor_id)
        if successor is None or successor_id == source["id"]:
            raise SpecError(
                f"{source['id']}: superseded_by must identify another requirement"
            )
        if indices[successor_id] <= indices[source["id"]]:
            raise SpecError(
                f"{source['id']}: supersession edges must advance catalog order"
            )
        if successor["status"] == "retired" and successor["superseded_by"] == "":
            raise SpecError(
                f"{source['id']}: supersession chain terminates at retired {successor_id}"
            )

        visited = {source["id"]}
        current = successor
        while current["superseded_by"] != "":
            if current["id"] in visited:
                raise SpecError(f"{source['id']}: supersession chain contains a cycle")
            visited.add(current["id"])
            next_item = by_id.get(current["superseded_by"])
            if next_item is None:
                raise SpecError(
                    f"{current['id']}: superseded_by identifies a missing requirement"
                )
            current = next_item
        if current["status"] != "active":
            raise SpecError(
                f"{source['id']}: supersession chain must terminate at an active requirement"
            )


def validate_catalog(catalog: Any, *, trace_root: Path | None = REPOSITORY_ROOT) -> dict[str, Any]:
    expected = {"schema_version", "catalog_revision", "product", "updated_at", "requirements"}
    if not isinstance(catalog, dict) or set(catalog) != expected:
        raise SpecError("catalog must contain schema_version/catalog_revision/product/updated_at/requirements only")
    if (
        type(catalog["schema_version"]) is not int
        or catalog["schema_version"] != 1
        or type(catalog["catalog_revision"]) is not int
        or catalog["catalog_revision"] < 1
    ):
        raise SpecError("invalid schema or catalog revision")
    nonempty(catalog["product"], "product")
    nonempty(catalog["updated_at"], "updated_at")
    if not isinstance(catalog["requirements"], list) or not catalog["requirements"]:
        raise SpecError("requirements must be a non-empty list")
    seen: set[str] = set()
    seen_ac: set[str] = set()
    for item in catalog["requirements"]:
        validate_requirement(item, seen_ac, trace_root)
        if item["id"] in seen:
            raise SpecError(f"duplicate requirement: {item['id']}")
        seen.add(item["id"])
    validate_supersession_graph(catalog["requirements"])
    return catalog


def trace_input_paths(catalog: dict[str, Any], *, trace_root: Path) -> set[Path]:
    """Return every repository file whose existence validates a non-standards trace."""

    return {
        trace_root.joinpath(*PurePosixPath(value).parts)
        for item in catalog["requirements"]
        for key in ("design", "implementation", "tests")
        for value in item["traces"][key]
    }


def _markdown_text(value: str) -> str:
    """Preserve text visibly without allowing Markdown structure injection."""

    escaped = html.escape(value, quote=False)
    return (
        escaped.replace("\\", "&#92;")
        .replace("`", "&#96;")
        .replace("|", "&#124;")
        .replace("\r\n", "<br>")
        .replace("\r", "<br>")
        .replace("\n", "<br>")
    )


def _json_code(value: Any) -> str:
    """Render exact JSON boundaries and ordering as injection-safe inline code."""

    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return f"<code>{html.escape(encoded, quote=False).replace('|', '&#124;')}</code>"


def render(catalog: dict[str, Any]) -> str:
    action_labels = {
        "separate": "分離する",
        "discover": "探り当てる",
        "maintain": "維持する",
        "apply": "適用する",
        "generate": "生成する",
        "structure": "構成する",
        "derive": "導出する",
        "parse": "解析する",
        "detect": "検出する",
        "verify": "検証する",
        "enable": "実現する",
        "provide": "提供する",
        "estimate": "推定する",
        "enforce": "強制する",
        "route": "経路選択する",
        "constrain": "制約する",
        "expand": "拡張する",
        "stop": "停止する",
        "measure": "計測する",
        "select": "選択する",
        "stage": "段階適用する",
        "formalize": "形式化する",
        "validate": "妥当性確認する",
        "preserve": "維持する",
    }
    status_labels = {"active": "有効", "retired": "廃止"}
    type_labels = {
        "functional": "機能",
        "quality": "品質",
        "constraint": "制約",
        "interface": "インターフェース",
        "data": "データ",
        "operational": "運用",
    }
    lines = [
        "<!-- tools/quintflow.pyによる自動生成。spec/requirements/requirements.qntを編集すること。 -->",
        f"# {_markdown_text(catalog['product'])} 要件一覧",
        "",
        f"- スキーマ版: {catalog['schema_version']}",
        f"- カタログ版: {catalog['catalog_revision']}",
        f"- Product(JSON): {_json_code(catalog['product'])}",
        f"- 更新日(JSON): {_json_code(catalog['updated_at'])}",
        "- 正本: `spec/requirements/requirements.qnt`",
        "- 機械可読view: `spec/requirements/requirements.json`",
        "",
        "| ID | 版 | 状態 | 種別 | 原子的な義務 | 検証方法 |",
        "|---|---:|---|---|---|---|",
    ]
    for item in catalog["requirements"]:
        action = action_labels.get(item["action"], item["action"])
        obligation = (
            f"{_markdown_text(item['subject'])}は、{_markdown_text(item['object'])}を"
            f"**{_markdown_text(action)}**（{_json_code(item['action'])}）"
        )
        lines.append(
            f"| {_json_code(item['id'])} | {item['revision']} | {status_labels[item['status']]} | "
            f"{type_labels[item['type']]} | {obligation} | "
            f"{_markdown_text(item['verification']['method'])} |"
        )
    for item in catalog["requirements"]:
        action = action_labels.get(item["action"], item["action"])
        lines += [
            "",
            f"## {_markdown_text(item['id'])}: {_markdown_text(item['title'])}",
            "",
            f"要件ID(JSON): {_json_code(item['id'])}",
            f"タイトル(JSON): {_json_code(item['title'])}",
            f"主体(JSON): {_json_code(item['subject'])}",
            f"対象(JSON): {_json_code(item['object'])}",
            f"{_markdown_text(item['subject'])}は、{_markdown_text(item['object'])}を"
            f"**{_markdown_text(action)}**。",
            f"行為enum: {_json_code(item['action'])}",
            "",
            f"根拠: {_markdown_text(item['rationale'])}",
            f"根拠(JSON): {_json_code(item['rationale'])}",
            "",
            f"項目版: {item['revision']} / 状態: `{item['status']}` / 種別: `{item['type']}`",
            f"変更識別子: {_json_code(item['last_changed_by'])}",
            f"分類: scope={_json_code(item['scope'])} / category={_json_code(item['category'])}",
        ]
        lines += ["", "受入条件:"]
        for criterion in item["acceptance_criteria"]:
            lines.append(
                f"- {_json_code(criterion['id'])} 前提: {_markdown_text(criterion['given'])}。"
                f"条件: {_markdown_text(criterion['when'])}。"
                f"期待結果: {_markdown_text(criterion['then'])}。"
            )
            lines.append(f"  - criterion(JSON Object): {_json_code(criterion)}")
        lines += [
            "",
            f"要求源(JSON List): {_json_code(item['source_refs'])}",
            f"検証方法: {_markdown_text(item['verification']['method'])}",
            f"検証証跡: {_markdown_text(item['verification']['evidence'])}",
            f"検証(JSON Object): {_json_code(item['verification'])}",
            "トレース(JSON List、順序保持):",
        ]
        trace_labels = {"design": "設計", "implementation": "実装", "tests": "テスト", "standards": "参照資料"}
        lines.extend(
            f"- {trace_labels[key]}: {_json_code(item['traces'][key])}"
            for key in ["design", "implementation", "tests", "standards"]
        )
        lines.append(f"廃止理由: {_json_code(item['retirement_reason'])}")
        lines.append(f"後継要件: {_json_code(item['superseded_by'])}")
    return "\n".join(lines) + "\n"


def atomic_text(
    path: Path,
    content: str,
    expected: FileSnapshot,
    *,
    read_preconditions: dict[Path, FileSnapshot],
) -> None:
    atomic_write_cas(
        path,
        content.encode("utf-8"),
        expected,
        root=REPOSITORY_ROOT,
        lock_name=".devflow/run/specflow-generate.lock",
        read_preconditions=read_preconditions,
    )


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def apply_change(catalog: dict[str, Any], change: Any) -> dict[str, Any]:
    catalog = validate_catalog(copy.deepcopy(catalog))
    expected = {"base_catalog_revision", "changed_at", "work_item", "operations"}
    if not isinstance(change, dict) or set(change) != expected:
        raise SpecError("change needs base_catalog_revision/changed_at/work_item/operations")
    if (
        type(change["base_catalog_revision"]) is not int
        or change["base_catalog_revision"] != catalog["catalog_revision"]
    ):
        raise SpecError("stale catalog revision; no changes written")
    nonempty(change["changed_at"], "changed_at")
    change_id = nonempty(change["work_item"], "work_item")
    if not isinstance(change["operations"], list) or not change["operations"]:
        raise SpecError("operations must be a non-empty list")
    candidate = copy.deepcopy(catalog)
    by_id = {item["id"]: item for item in candidate["requirements"]}
    touched: set[str] = set()
    for operation in change["operations"]:
        op = operation.get("op") if isinstance(operation, dict) else None
        if op == "add":
            if set(operation) != {"op", "requirement"}:
                raise SpecError("add operation needs op/requirement only")
            item = copy.deepcopy(operation.get("requirement"))
            if not isinstance(item, dict):
                raise SpecError("add requires a new requirement")
            rid = nonempty(item.get("id"), "add.id")
            if rid in by_id:
                raise SpecError("add requires a new requirement")
            if type(item.get("revision")) is not int or item.get("revision") != 1:
                raise SpecError(f"{rid}: added requirement must start at revision 1")
            if item.get("status") != "active":
                raise SpecError(f"{rid}: added requirement must start active at revision 1")
            if set(item) != REQUIREMENT_FIELDS:
                raise SpecError(f"{rid}: add requires all 18 requirement fields exactly")
            item["last_changed_by"] = change_id
            by_id[rid] = item
            candidate["requirements"].append(item)
            touched.add(rid)
        elif op == "update":
            if set(operation) != {"op", "id", "expected_revision", "changes"}:
                raise SpecError("update operation needs op/id/expected_revision/changes only")
            rid = nonempty(operation.get("id"), "update.id")
            item = by_id.get(rid)
            if (
                item is None
                or type(operation.get("expected_revision")) is not int
                or operation.get("expected_revision") != item["revision"]
            ):
                raise SpecError(f"{rid}: stale or missing requirement")
            if item["status"] != "active":
                raise SpecError(f"{rid}: retired requirement cannot be updated")
            if rid in touched:
                raise SpecError(f"{rid}: requirement may change only once per catalog transition")
            changes = operation.get("changes")
            immutable = {
                "id",
                "revision",
                "status",
                "last_changed_by",
                "retirement_reason",
                "superseded_by",
                "traces",
            }
            allowed = REQUIREMENT_FIELDS - immutable
            if not isinstance(changes, dict) or not changes or set(changes) - allowed:
                raise SpecError(f"{rid}: invalid update fields")
            if all(item.get(key) == value for key, value in changes.items()):
                raise SpecError(f"{rid}: update must change at least one field")
            item.update(copy.deepcopy(changes))
            item["revision"] += 1
            item["last_changed_by"] = change_id
            touched.add(rid)
        elif op == "trace":
            if set(operation) != {"op", "id", "expected_revision", "traces"}:
                raise SpecError("trace operation needs op/id/expected_revision/traces only")
            rid = nonempty(operation.get("id"), "trace.id")
            item = by_id.get(rid)
            if (
                item is None
                or type(operation.get("expected_revision")) is not int
                or operation.get("expected_revision") != item["revision"]
            ):
                raise SpecError(f"{rid}: stale or missing requirement")
            if item["status"] != "active":
                raise SpecError(f"{rid}: retired requirement trace cannot be updated")
            if rid in touched:
                raise SpecError(f"{rid}: requirement may change only once per catalog transition")
            traces = operation.get("traces")
            if not isinstance(traces, dict) or set(traces) != TRACE_KEYS:
                raise SpecError(f"{rid}: trace operation requires all trace categories")
            if traces == item["traces"]:
                raise SpecError(f"{rid}: trace update must change at least one link")
            item["traces"] = copy.deepcopy(traces)
            item["revision"] += 1
            item["last_changed_by"] = change_id
            touched.add(rid)
        elif op == "retire":
            fields = set(operation)
            if fields not in [
                {"op", "id", "expected_revision", "reason"},
                {"op", "id", "expected_revision", "reason", "superseded_by"},
            ]:
                raise SpecError(
                    "retire operation needs op/id/expected_revision/reason and optional superseded_by"
                )
            rid = nonempty(operation.get("id"), "retire.id")
            item = by_id.get(rid)
            if (
                item is None
                or type(operation.get("expected_revision")) is not int
                or operation.get("expected_revision") != item["revision"]
            ):
                raise SpecError(f"{rid}: stale or missing requirement")
            if rid in touched or item["status"] != "active":
                raise SpecError(f"{rid}: only one active requirement may be retired per transition")
            successor = operation.get("superseded_by", "")
            if not isinstance(successor, str):
                raise SpecError(f"{rid}: superseded_by must be a string")
            item.update(
                {
                    "status": "retired",
                    "retirement_reason": nonempty(operation.get("reason"), f"{rid}.reason"),
                    "superseded_by": successor,
                    "revision": item["revision"] + 1,
                    "last_changed_by": change_id,
                }
            )
            touched.add(rid)
        else:
            raise SpecError(f"unsupported operation: {op}")
    candidate["catalog_revision"] += 1
    candidate["updated_at"] = change["changed_at"]
    return validate_catalog(candidate)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    for name in ["validate", "generate", "check"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--spec", type=Path, default=Path("spec/requirements/requirements.json"))
        if name != "validate":
            cmd.add_argument("--out", type=Path, default=Path("docs/requirements/REQUIREMENTS.md"))
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        spec_path = args.spec if args.spec.is_absolute() else REPOSITORY_ROOT / args.spec
        output_path = (
            args.out if args.out.is_absolute() else REPOSITORY_ROOT / args.out
        ) if args.command in {"generate", "check"} else None
        spec_snapshot = snapshot_file(spec_path, root=REPOSITORY_ROOT)
        output_snapshot = (
            snapshot_file(output_path, root=REPOSITORY_ROOT)
            if output_path is not None
            else None
        )
        catalog = validate_catalog(read_json(spec_path), trace_root=None)
        trace_snapshots = {
            path: snapshot_file(path, root=REPOSITORY_ROOT)
            for path in trace_input_paths(catalog, trace_root=REPOSITORY_ROOT)
        }
        catalog = validate_catalog(catalog)
        if args.command == "validate":
            print(f"requirements valid: {len(catalog['requirements'])} items / revision {catalog['catalog_revision']}")
        elif args.command == "generate":
            assert output_snapshot is not None
            assert output_path is not None
            read_preconditions = {
                **{
                    path: snapshot
                    for path, snapshot in trace_snapshots.items()
                    if path != output_path
                },
                spec_path: spec_snapshot,
            }
            atomic_text(
                output_path,
                render(catalog),
                output_snapshot,
                read_preconditions=read_preconditions,
            )
            print(f"generated {args.out}")
        elif args.command == "check":
            assert output_snapshot is not None
            assert output_path is not None
            try:
                actual = read_bytes_nofollow(output_path, root=REPOSITORY_ROOT).decode("utf-8")
            except (OSError, UnicodeDecodeError, SafeIOError) as exc:
                raise SpecError(f"cannot safely read generated requirements {args.out}: {exc}") from exc
            expected_text = render(catalog)
            if (
                snapshot_file(spec_path, root=REPOSITORY_ROOT) != spec_snapshot
                or snapshot_file(output_path, root=REPOSITORY_ROOT) != output_snapshot
                or any(
                    snapshot_file(path, root=REPOSITORY_ROOT) != before
                    for path, before in trace_snapshots.items()
                )
            ):
                raise SpecError(
                    "requirements input, trace input, or generated output changed during check"
                )
            if actual != expected_text:
                raise SpecError(f"generated requirements drift: {args.out}")
            print(f"requirements docs current: {args.out}")
        return 0
    except (SafeIOError, SpecError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
