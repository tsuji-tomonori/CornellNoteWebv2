import subprocess
import sys


def test_generation_is_deterministic():
    result = subprocess.run(
        [sys.executable, "tools/design.py", "--check"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
