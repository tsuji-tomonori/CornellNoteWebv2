import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
(root / "reports").mkdir(exist_ok=True)
checks = [
    (
        "Ruff formatter",
        ["uv", "run", "ruff", "format", "--check", "backend", "infra", "tests", "tools"],
    ),
    ("Ruff lint", ["uv", "run", "ruff", "check", "backend", "infra", "tests", "tools"]),
    (
        "SQLFluff",
        [
            "uv",
            "run",
            "sqlfluff",
            "lint",
            "backend/src/app/apis",
            "backend/migrations",
            "--format",
            "json",
        ],
    ),
    ("SQL codegen / architecture", ["uv", "run", "python", "tools/generate_queries.py", "--check"]),
    ("mypy strict", ["uv", "run", "mypy"]),
    ("Pyright strict", ["uv", "run", "pyright"]),
    ("TypeScript build", ["npm", "--prefix", "frontend", "run", "build"]),
    ("ESLint", ["npm", "--prefix", "frontend", "run", "lint"]),
    ("Prettier", ["npm", "--prefix", "frontend", "run", "format:check"]),
    ("Vitest coverage", ["npm", "--prefix", "frontend", "test"]),
    (
        "pytest / CDK nag / snapshot",
        [
            "uv",
            "run",
            "pytest",
            "--cov=app",
            "--cov=infra",
            "--cov-branch",
            "--cov-report=html:reports/python-coverage",
            "--cov-report=json:reports/python-coverage.json",
            "--junitxml=reports/pytest.xml",
        ],
    ),
    ("Quint / Markdown as-built drift", ["uv", "run", "python", "tools/design.py", "--check"]),
]
results = []
for name, command in checks:
    print(name, flush=True)
    result = subprocess.run(
        command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
    )
    output = result.stdout
    if name == "SQLFluff":
        diagnostics = [
            {"filepath": item["filepath"], "violations": item["violations"]}
            for item in json.loads(output)
        ]
        (root / "reports/sqlfluff.json").write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n"
        )
        output = "\n".join(
            f"{item['filepath']}: {len(item['violations'])} violations" for item in diagnostics
        )
    results.append(
        {"name": name, "command": command, "exit_code": result.returncode, "output": output}
    )
    (root / "reports/quality.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    )
    print(output[-1500:], flush=True)
sys.exit(1 if any(r["exit_code"] for r in results) else 0)
