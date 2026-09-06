import ast
import logging
import re

import sqlglot
from app.observability import EVENTS
from sqlglot import exp


def ddl_fields(root):
    try:
        from tools.schema_model import ddl_state, primary_columns
    except ModuleNotFoundError:
        from schema_model import ddl_state, primary_columns
    tables, comments, _ = ddl_state(root)
    columns = {}
    for name, (_, statement) in tables.items():
        primary = primary_columns(statement.this)
        for c in statement.this.expressions:
            if isinstance(c, exp.ColumnDef):
                columns[name + "." + c.name] = (
                    c.kind.sql(dialect="postgres"),
                    c.name not in primary
                    and not any(
                        isinstance(k.kind, exp.NotNullColumnConstraint) for k in c.constraints
                    ),
                )
    return {key: (*value, comments.get(key, "")) for key, value in columns.items()}


def expression_origin(node, assignments, depth=0):
    if depth > 5:
        return ast.unparse(node)
    if isinstance(node, ast.Name) and node.id in assignments:
        return expression_origin(assignments[node.id], assignments, depth + 1)
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "data"
    ):
        return "リクエスト: " + node.attr
    if isinstance(node, ast.Name) and node.id == "owner":
        return "認証JWT: sub（所有者）"
    if isinstance(node, ast.Name) and node.id in {"note_id", "token"}:
        return "パス引数: " + node.id
    if isinstance(node, ast.Constant):
        return "固定値: " + repr(node.value)
    return ast.unparse(node)


def detail_design(
    *, root, function, definition, queries, incoming, responses, fields, schemas, table
):
    assignments = {
        target.id: n.value
        for n in ast.walk(function)
        if isinstance(n, ast.Assign)
        for target in n.targets
        if isinstance(target, ast.Name)
    }
    body = "## 1. 正常系入力\n\n" + table(["位置", "名前", "型", "必須"], incoming)
    for _media, c in definition.get("requestBody", {}).get("content", {}).items():
        body += table(["入力項目", "型", "必須", "説明", "制約"], fields(c["schema"], schemas))
    body += "## 2. 正常系前提と分岐\n\n以下の拒否条件が成立せず、記載の例外が発生しない場合に正常系へ進む。\n\n"
    body += table(
        ["条件・例外", "分岐時の応答"],
        (
            (condition, f"HTTP {code}: {response}")
            for code, _, condition, response in responses
            if not str(code).startswith("2")
        ),
    )
    changes = []
    metadata = ddl_fields(root)
    for q in queries:
        sql = sqlglot.parse_one((root / q["source"]).read_text(), dialect="postgres")
        parameter_calls = [
            n
            for n in ast.walk(function)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "".join(p.capitalize() for p in q["name"].split("_")) + "Params"
        ]
        params = {
            k.arg: expression_origin(k.value, assignments)
            for n in parameter_calls
            for k in n.keywords
        }
        where = sql.args.get("where")
        body += f"### {q['summary']}\n\nテーブル: `{', '.join(q['tables'])}` / 操作: `{q['operation']}`\n\n"
        body += "対象条件: `" + (where.sql(dialect="postgres") if where else "条件なし") + "`\n\n"
        body += table(["バインド引数", "値の取得元"], params.items())
        if isinstance(sql, exp.Insert):
            values = sql.expression.expressions[0].expressions
            pairs = zip(sql.this.expressions, values, strict=True)
        elif isinstance(sql, exp.Update):
            pairs = ((n.this, n.expression) for n in sql.expressions)
        else:
            pairs = []
        for column, value in pairs:
            origin = (
                params.get(value.this.name, ast.unparse(function).splitlines()[0])
                if isinstance(value, exp.Placeholder)
                else "SQL式: " + value.sql(dialect="postgres")
            )
            changes.append(
                (
                    q["table"],
                    q["operation"],
                    column.name,
                    metadata[q["table"] + "." + column.name][2],
                    origin,
                )
            )
        if isinstance(sql, exp.Delete):
            changes.append(
                (
                    q["table"],
                    "DELETE",
                    "行全体",
                    "対象行を削除する",
                    where.sql(dialect="postgres") if where else "条件なし",
                )
            )
    body += "## 3. 正常系リソース変更\n\n" + (
        table(["テーブル", "操作", "カラム", "日本語説明", "値の取得元"], changes)
        if changes
        else "正常系で作成・更新・削除するリソースはない。\n\n"
    )
    body += "## 4. 正常系レスポンス\n\n" + table(
        ["HTTP", "区分", "条件", "応答"], [r for r in responses if str(r[0]).startswith("2")]
    )
    returns = [n.value for n in ast.walk(function) if isinstance(n, ast.Return) and n.value]
    response_sources = {}
    for n in returns:
        if isinstance(n, ast.Call):
            response_sources.update(
                {k.arg: expression_origin(k.value, assignments) for k in n.keywords if k.arg}
            )
        elif isinstance(n, ast.Dict):
            response_sources.update(
                {
                    k.value: expression_origin(v, assignments)
                    for k, v in zip(n.keys, n.values, strict=True)
                    if isinstance(k, ast.Constant)
                }
            )
    mapping = ast.parse((root / "backend/src/app/note_mapping.py").read_text())
    aliases = {
        n.targets[0].slice.value: n.value.args[0].value
        for n in ast.walk(mapping)
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Subscript)
        and isinstance(n.targets[0].slice, ast.Constant)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Attribute)
        and n.value.func.attr == "pop"
    }
    for status, response in definition["responses"].items():
        if not status.startswith("2"):
            continue
        for content in response.get("content", {}).values():
            rows = []
            for name, kind, _required, description, _ in fields(content.get("schema", {}), schemas):
                key = (
                    re.sub(r"^\$\[\]\.?|^\$\.?", "", name).split(".")[0].split("[")[0].split(" ")[0]
                )
                column = aliases.get(key, key)
                origin = response_sources.get(key)
                if not origin and any(column in q["rows"] for q in queries):
                    origin = "DB: " + next(
                        q["row_sources"][column] for q in queries if column in q["rows"]
                    )
                if key in {"cue", "content", "summary"} and any(
                    "note_sections" in q["tables"] for q in queries
                ):
                    origin = "DB: note_sections.body（kind = " + key + "）"
                if key == "tasks" and any("note_tasks" in q["tables"] for q in queries):
                    origin = "DB: note_tasks の行を表示順に配列化"
                if (
                    not origin
                    and key
                    and any(
                        isinstance(n, ast.Call) and any(k.arg is None for k in n.keywords)
                        for n in returns
                    )
                ):
                    origin = "リクエスト: " + key
                rows.append(
                    (
                        name,
                        kind,
                        description,
                        origin
                        or (
                            "配列・オブジェクトの入れ物"
                            if kind in {"array", "object"}
                            else "戻り式: " + ", ".join(ast.unparse(n) for n in returns)
                        ),
                    )
                )
            body += table(["項目", "型", "説明", "値の取得元"], rows)
    return body


def query_design(root, queries, table, source):
    metadata = ddl_fields(root)
    body = ""
    for q in queries:
        body += f"## {q['filename']}\n\n### SQL種別\n\n`{q['operation']}`\n\n### SQLの概要\n\n{q['summary']}\n\n### 利用するテーブル\n\n`{', '.join(q['tables'])}`\n\n"
        for title, key in [("引数", "params"), ("戻り値", "rows")]:
            body += f"### {title}\n\n" + table(
                ["DDLテーブル", "DDL項目", "SQL項目", "日本語名", "DB型", "Python型", "NULL許容"],
                (
                    (
                        q["param_sources" if key == "params" else "row_sources"][name].split(".")[
                            0
                        ],
                        q["param_sources" if key == "params" else "row_sources"][name].split(".")[
                            1
                        ],
                        name,
                        metadata[q["param_sources" if key == "params" else "row_sources"][name]][2],
                        metadata[q["param_sources" if key == "params" else "row_sources"][name]][0],
                        kind,
                        "可"
                        if metadata[q["param_sources" if key == "params" else "row_sources"][name]][
                            1
                        ]
                        else "不可",
                    )
                    for name, kind in q[key].items()
                ),
            )
        body += (
            "### SQL\n\n```sql\n"
            + (root / q["source"]).read_text().rstrip()
            + "\n```\n\n正本: "
            + source(q["source"])
            + "\n\n"
        )
    return body or "SQL呼出なし。\n"


def message_design(op, responses, table, source):
    body = "ルートの共通ラッパーが、実際に返すHTTPコード・例外から構造化ログを出力する。JWT・パス中の共有トークン・本文・パスワードはログ項目に含めない。API Gatewayが手前で拒否した要求はFastAPIのログ対象外。\n\n"
    body += "正本: " + source("backend/src/app/observability.py") + "\n\n## メッセージ一覧\n\n"
    body += table(
        ["message_id", "レベル", "対象HTTP", "ログ概要"],
        (
            (
                op + "." + event.key,
                logging.getLevelName(event.level),
                f"{event.minimum}–{event.maximum}",
                event.message,
            )
            for event in EVENTS
        ),
    )
    body += "## ログ詳細\n\n"
    for event in EVENTS:
        codes = sorted(
            {str(r[0]) for r in responses if event.minimum <= int(r[0]) <= event.maximum}
        )
        body += f"### {op}.{event.key}\n\n" + table(
            ["出力項目", "値"],
            [
                ("message_id", op + "." + event.key),
                ("message", event.message),
                ("operation", op),
                ("status", ", ".join(codes)),
                ("exception_type", "捕捉した例外のクラス名。正常応答はnull"),
            ],
        )
    body += "## HTTPエラーとの対応\n\n" + table(
        ["HTTP", "区分", "発生条件", "レスポンス"],
        [r for r in responses if not str(r[0]).startswith("2")],
    )
    return body


def unit_factors(function, responses, table):
    body = "## 0. Router層の暗黙処理\n\n" + table(
        ["HTTP", "処理", "条件", "期待応答"],
        [r for r in responses if str(r[0]) in {"401", "422", "500"}],
    )
    body += "## 1. 要因ごとの要素\n\n"
    rows = []
    for n in ast.walk(function):
        if isinstance(n, ast.If):
            outcomes = []
            for label, nodes in [("成立", n.body), ("不成立", n.orelse)]:
                raised = [
                    c
                    for block in nodes
                    for c in ast.walk(block)
                    if isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Name)
                    and c.func.id == "HTTPException"
                ]
                outcomes.append(
                    (
                        ast.unparse(n.test),
                        label,
                        ", ".join(
                            "HTTP " + ast.unparse(c.args[0]) + ": " + ast.unparse(c.args[1])
                            for c in raised
                        )
                        or "後続処理または正常応答へ進む",
                    )
                )
            rows += outcomes
        elif isinstance(n, ast.ExceptHandler):
            rows.append(
                (
                    "例外: " + ast.unparse(n.type),
                    "発生／非発生",
                    "個別catchのHTTP応答と、非発生時の処理継続を確認する",
                )
            )
    body += table(["要因", "要素", "期待観点"], rows)
    body += "## 2. HTTP経路のテストケース一覧\n\n到達不能な条件の直積は作らず、実装にある応答経路を列挙する。この表はテスト観点であり実行済みの証跡ではない。\n\n"
    body += table(
        ["Case ID", "HTTP", "前提・操作", "期待結果"],
        ((f"TC{i:03}", r[0], r[2], r[3]) for i, r in enumerate(responses, 1)),
    )
    return body
