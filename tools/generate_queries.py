import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend/src/app/apis"
MANIFEST = ROOT / "docs/design/generated/queries.gen.json"


def schema(root: Path) -> dict[str, dict[str, str]]:
    tables = {}
    for path in sorted((root / "backend/migrations").glob("*.sql")):
        for statement in sqlglot.parse(path.read_text(), dialect="postgres"):
            if not isinstance(statement, exp.Create) or statement.kind != "TABLE":
                continue
            table = statement.this
            if not isinstance(table, exp.Schema):
                raise ValueError(f"{path}: unsupported table definition")
            fields = {}
            for column in table.expressions:
                if not isinstance(column, exp.ColumnDef):
                    raise ValueError(f"{path}: unsupported table constraint")
                kind = column.kind.sql(dialect="postgres").split("(")[0]
                types = {
                    "UUID": "UUID",
                    "VARCHAR": "str",
                    "TEXT": "str",
                    "INT": "int",
                    "TIMESTAMPTZ": "datetime",
                }
                if kind not in types:
                    raise ValueError(f"{path}: unsupported column type {kind}")
                nonnull = any(
                    isinstance(c.kind, exp.NotNullColumnConstraint | exp.PrimaryKeyColumnConstraint)
                    for c in column.constraints
                )
                fields[column.name] = types[kind] + ("" if nonnull else " | None")
            tables[table.this.name] = fields
    return tables


def analyze(path: Path, tables: dict[str, dict[str, str]]) -> dict:
    text = path.read_text()
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first.startswith("-- ") or not first[3:].strip():
        raise ValueError(f"{path}: first line must summarize the SQL")
    if not re.fullmatch(r"\d{3}_[a-z][a-z0-9_]*\.sql", path.name):
        raise ValueError(f"{path}: expected NNN_query_name.sql")
    statements = [s for s in sqlglot.parse(text, dialect="postgres") if s is not None]
    if len(statements) != 1 or not isinstance(
        statements[0], exp.Select | exp.Insert | exp.Update | exp.Delete
    ):
        raise ValueError(f"{path}: exactly one SELECT/INSERT/UPDATE/DELETE is supported")
    statement = statements[0]
    table_nodes = list(statement.find_all(exp.Table))
    if len(table_nodes) != 1 or table_nodes[0].name not in tables:
        raise ValueError(
            f"{path}: expected one known table; joins/subqueries need generator support"
        )
    fields = tables[table_nodes[0].name]
    for column in statement.find_all(exp.Column):
        if column.name not in fields:
            raise ValueError(f"{path}: unknown column {column.name}")
    if statement.find(exp.Star):
        raise ValueError(f"{path}: enumerate columns instead of SELECT *")
    for column in statement.find_all(exp.Column):
        if column.table and column.table not in {table_nodes[0].name, table_nodes[0].alias}:
            raise ValueError(f"{path}: unknown table qualifier {column.table}")
    placeholders = list(statement.find_all(exp.Placeholder))
    params = {}
    for p in placeholders:
        name = p.this.name if isinstance(p.this, exp.Identifier) else ""
        if name not in fields or not isinstance(p.this, exp.Identifier):
            raise ValueError(f"{path}: named pyformat placeholders must match DDL columns")
        parent = p.parent
        if isinstance(parent, exp.Binary):
            peer = parent.this if parent.expression is p else parent.expression
            if not isinstance(peer, exp.Column) or peer.name != name:
                raise ValueError(f"{path}: placeholder must match its compared/assigned column")
        elif isinstance(parent, exp.Tuple) and isinstance(statement, exp.Insert):
            if statement.this.expressions[parent.expressions.index(p)].name != name:
                raise ValueError(f"{path}: INSERT parameter/column mismatch")
        else:
            raise ValueError(f"{path}: unsupported parameter context {type(parent).__name__}")
        params[name] = fields[name]
    projection = statement if isinstance(statement, exp.Select) else statement.args.get("returning")
    rows = {}
    if projection:
        for c in projection.expressions:
            if not isinstance(c, exp.Column):
                raise ValueError(f"{path}: computed result requires explicit generator support")
            if c.name in rows:
                raise ValueError(f"{path}: duplicate result column {c.name}")
            rows[c.name] = fields[c.name]
    name = path.stem[4:]
    return {
        "name": name,
        "summary": first[3:],
        "filename": path.name,
        "params": dict(sorted(params.items())),
        "rows": rows,
        "table": table_nodes[0].name,
        "operation": statement.key.upper(),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def model(name: str, fields: dict[str, str]) -> str:
    return f'class {name}(BaseModel):\n    model_config = ConfigDict(extra="forbid")\n' + "".join(
        f"    {key}: {value}\n" for key, value in fields.items()
    )


def render_module(queries: list[dict]) -> str:
    hints = " ".join(t for q in queries for t in [*q["params"].values(), *q["rows"].values()])
    imports = "from pathlib import Path\nfrom pydantic import BaseModel, ConfigDict\nfrom app.port import QuerySession\n"
    if "datetime" in hints:
        imports += "from datetime import datetime\n"
    if "UUID" in hints:
        imports += "from uuid import UUID\n"
    text = (
        "# Generated from sibling sql/*.sql and migration DDL. Do not edit.\n"
        + imports
        + '\nSQL_DIR = Path(__file__).parents[1] / "sql"\n\n'
    )
    for query in queries:
        name = query["name"]
        prefix = "".join(x.capitalize() for x in name.split("_"))
        text += model(prefix + "Params", query["params"]) + "\n\n"
        if query["rows"]:
            text += model(prefix + "Row", query["rows"]) + "\n\n"
        result = f"list[{prefix}Row]" if query["rows"] else "None"
        text += f'def {name}(session: QuerySession, params: {prefix}Params) -> {result}:\n    """{query["summary"]}"""\n'
        call = f'session.{{method}}(SQL_DIR / "{query["filename"]}", params.model_dump())'
        if query["rows"]:
            text += f"    return [{prefix}Row.model_validate(row) for row in {call.format(method='fetch_all')}]\n\n\n"
        else:
            text += f"    {call.format(method='execute')}\n\n\n"
    lint = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "I",
            "--fix",
            "--stdin-filename",
            "queries.py",
            "-",
        ],
        input=text,
        text=True,
        capture_output=True,
        check=True,
    )
    return subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--stdin-filename", "queries.py", "-"],
        input=lint.stdout,
        text=True,
        capture_output=True,
        check=True,
    ).stdout


def render(root: Path = ROOT) -> dict[Path, str]:
    tables = schema(root)
    grouped = defaultdict(list)
    catalog = []
    for path in sorted((root / "backend/src/app/apis").glob("*/*/sql/*.sql")):
        query = analyze(path, tables)
        grouped[path.parent.parent].append(query)
        catalog.append(
            {
                **query,
                "source": str(path.relative_to(root)),
                "api": path.parent.parent.name,
                "generated": str((path.parent.parent / "generated/queries.py").relative_to(root)),
            }
        )
    if not grouped:
        raise ValueError("No operation SQL found")
    outputs = {}
    for operation, queries in grouped.items():
        if len({q["name"] for q in queries}) != len(queries):
            raise ValueError(f"{operation}: duplicate query name")
        outputs[operation / "generated/queries.py"] = render_module(queries)
    outputs[root / MANIFEST.relative_to(ROOT)] = (
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    )
    return outputs


def write_outputs(outputs: dict[Path, str], *, check: bool, root: Path = ROOT) -> None:
    stale = []
    for path, data in outputs.items():
        if (
            not path.is_relative_to(root)
            or path.is_symlink()
            or any(p.is_symlink() for p in path.parents if p.is_relative_to(root))
        ):
            raise ValueError(f"Unsafe generated output: {path}")
        if path.exists() and not path.is_file():
            raise ValueError(f"Non-file generated output: {path}")
        if not path.exists() or path.read_text() != data:
            stale.append(path)
    orphaned = (
        set((root / "backend/src/app/apis").glob("*/*/generated/queries.py")) - outputs.keys()
    )
    if orphaned:
        raise ValueError("Orphaned query outputs: " + ", ".join(str(p) for p in sorted(orphaned)))
    if check and stale:
        raise ValueError(
            "Generated query drift: " + ", ".join(str(p.relative_to(root)) for p in stale)
        )
    if not check:
        for path in stale:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            if temporary.exists() or temporary.is_symlink():
                raise ValueError(f"Unmanaged temporary output: {temporary}")
            temporary.write_text(outputs[path])
            temporary.replace(path)


def check_architecture(root: Path = ROOT) -> None:
    for path in sorted((root / "backend/src/app").rglob("*.py")):
        if path.name == "migrate.py" or "generated" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                first = node.value.strip().split(maxsplit=1)
                if first and first[0].upper() in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
                    raise ValueError(f"{path}:{node.lineno}: inline SQL is forbidden")
    for path in sorted((root / "backend/src/app/apis").rglob("*.py")):
        if "generated" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        if path.name == "functions.py" and (path.parent / "sql").exists():
            expected = {p.stem[4:] for p in (path.parent / "sql").glob("*.sql")}
            called = {
                n.func.attr
                for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "queries"
                and n.func.attr[:1].islower()
            }
            if expected != called:
                raise ValueError(
                    f"{path}: SQL/function query mapping mismatch: {expected ^ called}"
                )
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and any(x in node.module.split(".") for x in ["psycopg", "db", "repository"])
            ):
                raise ValueError(f"{path}:{node.lineno}: provider import in operation")
            if isinstance(node, ast.Import) and any(
                a.name.split(".")[0] in {"psycopg", "boto3"} for a in node.names
            ):
                raise ValueError(f"{path}:{node.lineno}: provider import in operation")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                first = node.value.strip().split(maxsplit=1)
                if first and first[0].upper() in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
                    raise ValueError(f"{path}:{node.lineno}: inline SQL is forbidden")
            if (
                path.name == "router.py"
                and isinstance(node, ast.ImportFrom)
                and (node.module or "").endswith(("queries", "generated"))
            ):
                raise ValueError(f"{path}:{node.lineno}: routers must call functions")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    check_architecture()
    write_outputs(render(), check=args.check)
    print("Operation SQL, typed queries and architecture verified")


if __name__ == "__main__":
    main()
