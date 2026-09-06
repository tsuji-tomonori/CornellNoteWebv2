import re
import sys
from pathlib import Path

for name in sys.argv[1:]:
    text = Path(name).read_text()
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text) or re.search(
        r"AKIA[0-9A-Z]{16}", text
    ):
        raise SystemExit("Credential pattern found: " + name)
