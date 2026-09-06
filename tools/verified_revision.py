import json
import re
import subprocess
import tempfile
from pathlib import Path


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def matches(proof, *, source, commit, tree):
    lines = proof.splitlines()
    return (
        len(lines) == 3
        and all(re.fullmatch(r"[0-9a-f]{40}", value) for value in lines)
        and lines == [source, commit, tree]
    )


def main():
    subprocess.run(["git", "fetch", "origin", "dev"], check=True)
    tree, dev_tree = git("rev-parse", "HEAD^{tree}"), git("rev-parse", "origin/dev^{tree}")
    if tree != dev_tree:
        raise SystemExit("main and dev trees differ")
    dev = git("rev-parse", "origin/dev")
    runs = json.loads(
        subprocess.check_output(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                "verify.yml",
                "--branch",
                "dev",
                "--event",
                "push",
                "--status",
                "success",
                "--limit",
                "30",
                "--json",
                "databaseId,headSha",
            ],
            text=True,
        )
    )
    for run in runs:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    "gh",
                    "run",
                    "download",
                    str(run["databaseId"]),
                    "--name",
                    "verified-revision",
                    "--dir",
                    directory,
                ],
                capture_output=True,
                check=False,
            )
            proof = Path(directory) / "verified-revision.txt"
            if (
                result.returncode == 0
                and proof.is_file()
                and matches(proof.read_text(), source=run["headSha"], commit=dev, tree=tree)
            ):
                print(f"Verified exact dev commit/tree by successful run {run['databaseId']}")
                return
    raise SystemExit(
        "No successful dev push run attests this exact commit/tree; rerun dev verification"
    )


if __name__ == "__main__":
    main()
