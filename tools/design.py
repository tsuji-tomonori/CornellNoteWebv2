import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import sqlglot
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/design/generated"


def render() -> dict[str, str]:
    subprocess.run([sys.executable, "tools/generate_queries.py", "--check"], cwd=ROOT, check=True)
    queries = json.loads((OUT / "queries.gen.json").read_text())
    openapi = app.openapi()
    operations = []
    for path, methods in sorted(openapi["paths"].items()):
        for method, definition in sorted(methods.items()):
            operations.append(
                {
                    "id": definition["operationId"],
                    "method": method.upper(),
                    "path": path,
                    "authenticated": bool(definition.get("security")),
                    "request": definition.get("requestBody"),
                    "responses": definition["responses"],
                }
            )
    python_files = []
    discovered = []
    for path in sorted((ROOT / "backend/src/app").rglob("*.py")):
        tree = ast.parse(path.read_text())
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "parameters": [ast.unparse(arg) for arg in node.args.args],
                        "return": ast.unparse(node.returns) if node.returns else None,
                        "calls": [
                            ast.unparse(c.func) for c in ast.walk(node) if isinstance(c, ast.Call)
                        ],
                    }
                )
                for dec in node.decorator_list:
                    if (
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr in {"get", "post", "put", "delete"}
                    ):
                        discovered.extend(
                            ast.literal_eval(k.value)
                            for k in dec.keywords
                            if k.arg == "operation_id"
                        )
        python_files.append({"path": str(path.relative_to(ROOT)), "functions": functions})
    if set(discovered) != {op["id"] for op in operations} or len(discovered) != len(operations):
        raise ValueError("OpenAPI and implementation are not one-to-one")
    database = []
    for path in sorted((ROOT / "backend/migrations").glob("*.sql")):
        database.append(
            {
                "path": str(path.relative_to(ROOT)),
                "statements": [
                    node.sql(dialect="postgres")
                    for node in sqlglot.parse(path.read_text(), dialect="postgres")
                    if node
                ],
            }
        )
    template = json.loads((ROOT / "cdk.out/CornellNote.template.json").read_text())
    for resource in template["Resources"].values():
        if resource["Type"] == "AWS::Lambda::Function":
            resource["Properties"]["Code"] = {"Artifact": "uv.lock runtime bundle"}
    frontend = json.loads(
        subprocess.check_output(["node", "tools/frontend_design.mjs"], cwd=ROOT, text=True)
    )
    source_paths = sorted(
        [
            *ROOT.glob("backend/src/**/*.py"),
            *ROOT.glob("backend/migrations/*.sql"),
            *ROOT.glob("backend/src/app/apis/*/*/sql/*.sql"),
            ROOT / "tools/generate_queries.py",
            *ROOT.glob("frontend/src/*.ts"),
            *ROOT.glob("frontend/src/*.tsx"),
            ROOT / "frontend/src/style.css",
            ROOT / "infra/stack.py",
            ROOT / "uv.lock",
            ROOT / "tools/design.py",
            ROOT / "tools/frontend_design.mjs",
        ]
    )
    manifest = {
        "generators": [
            {
                "name": "queries",
                "category": "codegen",
                "command": "uv run python tools/generate_queries.py",
                "check": "uv run python tools/generate_queries.py --check",
                "inputs": [
                    "backend/src/app/apis/*/*/sql/*.sql",
                    "backend/migrations/*.sql",
                    "tools/generate_queries.py",
                ],
                "outputs": [
                    "backend/src/app/apis/*/*/generated/queries.py",
                    "docs/design/generated/queries.gen.json",
                ],
                "dependencies": [],
                "ci_safe": True,
                "unsupported": "Computed projections, joins and subqueries fail closed until explicitly supported",
            },
            {
                "name": "design",
                "command": "uv run python tools/design.py",
                "check": "uv run python tools/design.py --check",
                "inputs": [str(p.relative_to(ROOT)) for p in source_paths],
                "outputs": [
                    "docs/design/generated/" + name
                    for name in [
                        "DESIGN.gen.md",
                        "openapi.gen.json",
                        "operations.gen.json",
                        "python.gen.json",
                        "database.gen.json",
                        "frontend.gen.json",
                        "infrastructure.gen.json",
                        "manifest.gen.json",
                    ]
                ],
                "dependencies": ["queries", "CDK synth", "TypeScript parser", "FastAPI OpenAPI"],
                "ci_safe": True,
            },
        ],
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source_paths
        },
        "unsupported_surface": [
            {
                "path": "backend/src/app/apis/notes",
                "reason": "SQL単位の型・操作・テーブルを生成するが、DB実行結果と業務要件充足は結合テストで検証",
                "support_status": "structural-only",
            },
            {
                "path": "frontend/src",
                "reason": "型・関数・JSX属性は抽出。画面の見た目はE2Eスクリーンショットで検証",
                "support_status": "AST-plus-E2E",
            },
        ],
        "infrastructure_code_normalization": "Lambda bundle S3 object location is excluded; backend sources and uv.lock are hashed separately",
    }
    md = (
        "# 実装由来設計（自動生成）\n\n直接編集しない。実装の構造・インターフェースを記載し、要件充足はテストで検証する。\n\n## API\n\n| Operation | Method | Path | 認証 |\n|---|---|---|---|\n"
        + "".join(
            f"| {op['id']} | {op['method']} | `{op['path']}` | {'JWT' if op['authenticated'] else '公開 / local限定'} |\n"
            for op in operations
        )
    )
    md += "\n## DB\n\n" + "".join(
        "```sql\n" + "\n".join(db["statements"]) + "\n```\n" for db in database
    )
    md += (
        "\n## API別SQL / CRUD\n\n| API | SQL source | Table | Operation | Wrapper |\n|---|---|---|---|---|\n"
        + "".join(
            f"| {q['api']} | `{q['source']}` | {q['table']} | {q['operation']} | `{q['name']}` |\n"
            for q in queries
        )
    )
    md += "\n## 画面と関数\n\n" + "".join(
        f"- `{file['path']}`: " + ", ".join(f["name"] for f in file["functions"]) + "\n"
        for file in frontend
    )
    md += "\n## AWSリソース\n\n| Logical ID | Type |\n|---|---|\n" + "".join(
        f"| {key} | {value['Type']} |\n" for key, value in sorted(template["Resources"].items())
    )
    result = {"DESIGN.gen.md": md}
    for name, value in {
        "openapi.gen.json": openapi,
        "operations.gen.json": operations,
        "python.gen.json": python_files,
        "database.gen.json": database,
        "frontend.gen.json": frontend,
        "infrastructure.gen.json": template,
        "manifest.gen.json": manifest,
    }.items():
        result[name] = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = render()
    if args.check:
        stale = [
            name
            for name, data in files.items()
            if not (OUT / name).exists() or (OUT / name).read_text() != data
        ]
        if stale:
            raise SystemExit("Generated design drift: " + ", ".join(stale))
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            temporary = OUT / (name + ".tmp")
            temporary.write_text(data)
            temporary.replace(OUT / name)
    print("Design generation verified")


if __name__ == "__main__":
    main()
