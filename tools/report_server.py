import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "reports"), **kwargs)

    def translate_path(self, path):
        prefix = os.getenv("DOCS_BASE", "/design").removesuffix("/design")
        if prefix and path.startswith(prefix + "/"):
            path = path[len(prefix) :]
        return super().translate_path(path)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 4175), ReportHandler).serve_forever()
