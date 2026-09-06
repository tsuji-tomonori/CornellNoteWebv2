import json
import os
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def slug(name):
    value = name.removesuffix(".gen.md").removesuffix(".md").lower()
    return "" if value == "readme" else value.removesuffix("/index")


def prepare(root=ROOT, base=None):
    base = (base or os.getenv("DOCS_BASE", "/design")).rstrip("/")
    source = root / "docs/generated"
    content = root / "documentation/src/content/docs"
    if content.exists():
        shutil.rmtree(content)
    content.mkdir(parents=True)
    files = sorted(source.rglob("*.md"))
    for path in files:
        text = path.read_text()
        heading, body = text.split("\n", 1)
        title = heading.removeprefix("# ").strip()

        def replace(match, path=path):
            target = unquote(match[1])
            if "://" in target or not target.split("#")[0].endswith(".md"):
                return match[0]
            name, _, anchor = target.partition("#")
            resolved = (path.parent / name).resolve()
            if not resolved.is_relative_to(source.resolve()) or not resolved.is_file():
                raise ValueError("Broken generated document link: " + target)
            destination = slug(resolved.relative_to(source).as_posix())
            return (
                "]("
                + base
                + "/"
                + (destination + "/" if destination else "")
                + ("#" + anchor if anchor else "")
                + ")"
            )

        body = re.sub(r"\]\(([^)]+)\)", replace, body)
        name = slug(path.relative_to(source).as_posix())
        destination = content / (
            (name + ("/index.md" if path.name == "index.gen.md" else ".md")) if name else "index.md"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "---\ntitle: " + json.dumps(title, ensure_ascii=False) + "\n---\n" + body
        )
    print(f"Prepared {len(files)} HTML document sources", flush=True)


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"a", "link", "script", "img"}:
            self.links.extend(values[key] for key in ("href", "src") if values.get(key))


def verify_html(root=ROOT, base=None):
    base = base or os.getenv("DOCS_BASE", "/design")
    prefix = base.rstrip("/").removesuffix("/design")
    reports = root / "reports"
    pages = sorted((reports / "design").rglob("*.html"))
    count = 0
    for page in pages:
        for target in Links(page.read_text()).links:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = unquote(parsed.path)
            if prefix and path.startswith(prefix + "/"):
                path = path[len(prefix) :]
            destination = (
                (reports / path.lstrip("/")) if path.startswith("/") else page.parent / path
            ).resolve()
            if destination.is_dir():
                destination = destination / "index.html"
            if not destination.is_relative_to(reports.resolve()) or not destination.is_file():
                raise ValueError(f"Broken HTML link in {page.relative_to(reports)}: {target}")
            count += 1
    if not pages:
        raise ValueError("No built documentation pages")
    print(f"Verified {len(pages)} HTML pages and {count} internal links/assets", flush=True)


if __name__ == "__main__":
    prepare()
    subprocess.run(
        ["npm", "--prefix", "documentation", "run", "build", "--", "--force"],
        cwd=ROOT,
        check=True,
    )

    verify_html()
