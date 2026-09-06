import ast
import json
import subprocess
from pathlib import Path


def collect_tests(root: Path) -> list[dict]:
    tests = []
    for folder in ("backend/tests", "infra/tests", "tests"):
        for path in sorted((root / folder).glob("test_*.py")):
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    tests.append(
                        {
                            "file": path.relative_to(root).as_posix(),
                            "name": node.name,
                            "title": node.name.removeprefix("test_").replace("_", " "),
                            "line": node.lineno,
                            "runner": "pytest",
                            "assertions": [
                                ast.unparse(n.test)
                                for n in ast.walk(node)
                                if isinstance(n, ast.Assert)
                            ],
                        }
                    )
    result = subprocess.run(
        ["node", "tools/test_catalog.mjs"], cwd=root, check=True, capture_output=True, text=True
    )
    return tests + json.loads(result.stdout)
