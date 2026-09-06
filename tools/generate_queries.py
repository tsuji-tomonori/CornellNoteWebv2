import argparse
import ast
import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend/src/app/apis"


def schema(root: Path) -> dict[str, dict[str, str]]:
    try:
        from tools.schema_model import ddl_state, primary_columns
    except ModuleNotFoundError:
        from schema_model import ddl_state, primary_columns
    tables = {}
    for name, (path, statement) in ddl_state(root)[0].items():
        fields = {}
        primary = primary_columns(statement.this)
        for column in statement.this.expressions:
            if not isinstance(column, exp.ColumnDef):
                continue
            kind = column.kind.sql(dialect="postgres").split("(")[0]
            types = {
                "UUID": "UUID",
                "VARCHAR": "str",
                "TEXT": "str",
                "INT": "int",
                "TIMESTAMPTZ": "datetime",
                "BOOLEAN": "bool",
                "DATE": "date",
            }
            if kind not in types:
                raise ValueError(f"{path}: unsupported column type {kind}")
            nonnull = column.name in primary or any(
                isinstance(c.kind, exp.NotNullColumnConstraint) for c in column.constraints
            )
            fields[column.name] = types[kind] + ("" if nonnull else " | None")
        tables[name] = fields
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
    if not table_nodes or any(n.name not in tables for n in table_nodes):
        raise ValueError(f"{path}: expected known tables")
    aliases = {n.alias_or_name: n.name for n in table_nodes}

    def field(column):
        if column.table:
            name = aliases.get(column.table)
            if name is None or column.name not in tables[name]:
                raise ValueError(f"{path}: unknown column {column.sql()}")
            return tables[name][column.name]
        choices = {n.name for n in table_nodes if column.name in tables[n.name]}
        if len(choices) != 1:
            raise ValueError(f"{path}: unknown column or ambiguous column {column.name}")
        return tables[next(iter(choices))][column.name]

    if statement.find(exp.Star):
        raise ValueError(f"{path}: enumerate columns instead of SELECT *")
    for column in statement.find_all(exp.Column):
        field(column)

    def origin(column):
        name = (
            aliases.get(column.table)
            if column.table
            else next(n.name for n in table_nodes if column.name in tables[n.name])
        )
        return name + "." + column.name

    param_sources, row_sources = {}, {}
    placeholders = list(statement.find_all(exp.Placeholder))
    params = {}
    for p in placeholders:
        name = p.this.name if isinstance(p.this, exp.Identifier) else ""
        if not isinstance(p.this, exp.Identifier):
            raise ValueError(f"{path}: named pyformat placeholders must match DDL columns")
        parent = p.parent
        if isinstance(parent, exp.Binary):
            peer = parent.this if parent.expression is p else parent.expression
            if not isinstance(peer, exp.Column) or peer.name != name:
                raise ValueError(f"{path}: placeholder must match its compared/assigned column")
        elif isinstance(parent, exp.Tuple) and isinstance(statement, exp.Insert):
            peer = exp.column(
                statement.this.expressions[parent.expressions.index(p)].name,
                table=table_nodes[0].alias_or_name,
            )
            if peer.name != name:
                raise ValueError(f"{path}: INSERT parameter/column mismatch")
        else:
            raise ValueError(f"{path}: unsupported parameter context {type(parent).__name__}")
        params[name] = field(peer)
        param_sources[name] = origin(peer)
    projection = statement if isinstance(statement, exp.Select) else statement.args.get("returning")
    rows = {}
    if projection:
        for result in projection.expressions:
            c = result.this if isinstance(result, exp.Alias) else result
            if not isinstance(c, exp.Column):
                raise ValueError(f"{path}: computed result requires explicit generator support")
            if result.alias_or_name in rows:
                raise ValueError(f"{path}: duplicate result column {c.name}")
            rows[result.alias_or_name] = field(c)
            row_sources[result.alias_or_name] = origin(c)
    name = path.stem[4:]
    return {
        "name": name,
        "summary": first[3:],
        "filename": path.name,
        "params": dict(sorted(params.items())),
        "rows": rows,
        "param_sources": param_sources,
        "row_sources": row_sources,
        "table": table_nodes[0].name,
        "tables": sorted({n.name for n in table_nodes}),
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
    if "date" in hints:
        imports += "from datetime import date, datetime\n"
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
            "I,F401",
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


def collect(root: Path = ROOT) -> tuple[dict, list[dict]]:
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
    return grouped, catalog


def render(root: Path = ROOT) -> dict[Path, str]:
    grouped, _ = collect(root)
    outputs = {}
    for operation, queries in grouped.items():
        if len({q["name"] for q in queries}) != len(queries):
            raise ValueError(f"{operation}: duplicate query name")
        outputs[operation / "generated/queries.py"] = render_module(queries)
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
        if path.name == "router.py" and (path.parent / "sql").exists():
            for handler in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
                transactions = [
                    n
                    for n in ast.walk(handler)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "transaction"
                ]
                if len(transactions) != 1:
                    raise ValueError(
                        f"{path}:{handler.lineno}: exactly one router transaction is required"
                    )
        for node in ast.walk(tree):
            if (
                path.name == "functions.py"
                and isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"transaction", "commit", "rollback"}
            ):
                raise ValueError(f"{path}:{node.lineno}: transaction belongs to router")
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
