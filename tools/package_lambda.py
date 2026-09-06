import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "build/lambda"
if target.exists():
    shutil.rmtree(target)
target.mkdir(parents=True)
subprocess.run(
    [
        "uv",
        "export",
        "--frozen",
        "--no-dev",
        "--no-emit-project",
        "--output-file",
        "build/requirements.txt",
    ],
    cwd=root,
    check=True,
    stdout=subprocess.DEVNULL,
)
subprocess.run(
    [
        "uv",
        "pip",
        "install",
        "--requirements",
        "build/requirements.txt",
        "--target",
        str(target),
        "--python-version",
        "3.12",
        "--python-platform",
        "x86_64-manylinux2014",
        "--only-binary",
        ":all:",
    ],
    cwd=root,
    check=True,
)
shutil.copytree(
    root / "backend/src/app", target / "app", ignore=shutil.ignore_patterns("__pycache__")
)
shutil.copytree(root / "backend/migrations", target / "migrations")
