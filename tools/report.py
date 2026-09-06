import html
import json
import os
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
reports = root / "reports"
reports.mkdir(exist_ok=True)
images = reports / "screenshots"
images.mkdir(exist_ok=True)
esc = html.escape
cards = []
count = 0


def walk(suite):
    global count
    for spec in suite.get("specs", []):
        for test in spec.get("tests", []):
            results = test.get("results", [])
            result = results[-1] if results else {}
            steps = []
            for attachment in result.get("attachments", []):
                if attachment.get("contentType") != "image/png" or not attachment.get("path"):
                    continue
                source = Path(attachment["path"])
                if not source.is_absolute():
                    source = root / "frontend" / source
                if not source.exists():
                    raise RuntimeError("Missing screenshot " + str(source))
                count += 1
                destination = images / f"{count:03}.png"
                shutil.copyfile(source, destination)
                steps.append(
                    f'<div class="step"><p>{esc(attachment["name"])}</p><img src="screenshots/{destination.name}" alt="{esc(attachment["name"])}" loading="lazy"></div>'
                )
            error = "".join(
                f"<pre>{esc(e.get('message', ''))}</pre>" for e in result.get("errors", [])
            )
            cards.append(
                f"<article><h2>{esc(spec['title'])} <small>{esc(test.get('projectName', ''))} · {esc(result.get('status', 'not-run'))}</small></h2>{''.join(steps)}{error}</article>"
            )
    for child in suite.get("suites", []):
        walk(child)


file = reports / "playwright.json"
if file.exists():
    data = json.loads(file.read_text())
    for suite in data.get("suites", []):
        walk(suite)
else:
    cards.append('<p class="failed">E2E未実行。成功として扱いません。</p>')
quality = (
    json.loads((reports / "quality.json").read_text())
    if (reports / "quality.json").exists()
    else []
)
checks = "".join(
    f"<article><h2>{esc(x['name'])} <small>{'PASS' if x['exit_code'] == 0 else 'FAIL'}</small></h2><pre>{esc(x['output'])}</pre></article>"
    for x in quality
)
sql_diagnostics = reports / "sqlfluff.json"
if sql_diagnostics.exists():
    sql_sections = []
    for entry in json.loads(sql_diagnostics.read_text()):
        source = (root / entry["filepath"]).resolve()
        if not source.is_relative_to(root):
            raise ValueError("SQL diagnostic path escaped repository")
        lines = "\n".join(
            f"{index:3}  {esc(line)}"
            for index, line in enumerate(source.read_text().splitlines(), 1)
        )
        findings = (
            esc(json.dumps(entry["violations"], ensure_ascii=False, indent=2))
            if entry["violations"]
            else "指摘なし"
        )
        sql_sections.append(
            f"<article><h2>{esc(entry['filepath'])}</h2><p>{findings}</p><pre><code>{lines}</code></pre></article>"
        )
    (reports / "sql.html").write_text(
        '<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SQLFluff / SQLソース</title><style>body{font:16px/1.8 system-ui;margin:32px;background:#f0f6f4;color:#12211d}article{background:white;padding:24px;margin:20px 0;border:1px solid #dce7e2;border-radius:12px}h2{font-size:16px;overflow-wrap:anywhere}pre{overflow:auto;font-size:13px}</style><a href="index.html">品質レポートに戻る</a><h1>SQLFluffとSQLソース</h1>'
        + "".join(sql_sections)
        + "</html>"
    )
documentation = root / "docs/generated"
if documentation.exists():
    shutil.copytree(documentation, reports / "docs", dirs_exist_ok=True)
    doclinks = "".join(
        f'<li><a href="https://github.com/tsuji-tomonori/CornellNoteWebv2/blob/dev/docs/generated/{p.relative_to(documentation).as_posix()}">{esc(p.relative_to(documentation).as_posix())}</a> · <a href="docs/{p.relative_to(documentation).as_posix()}">Markdown</a></li>'
        for p in sorted(documentation.rglob("*.md"))
    )
    (reports / "docs.html").write_text(
        '<!doctype html><html lang="ja"><meta charset="utf-8"><title>自動生成仕様書</title><style>body{font:16px/1.8 system-ui;margin:32px;background:#f0f6f4}a{color:#236b56}</style><a href="index.html">品質レポート</a><h1>実装・要件から自動生成したMarkdown</h1><p>文書名はGitHub表示、MarkdownはこのCI実行で生成したファイルです。</p><ul>'
        + doclinks
        + "</ul></html>"
    )
links = []
for filename, label in [
    ("docs.html", "自動生成Markdown仕様書"),
    ("sql.html", "SQLFluff診断・SQLソース"),
    ("python-coverage/index.html", "Python コード行カバレッジ"),
    ("frontend-coverage/index.html", "TypeScript コード行カバレッジ"),
    ("playwright/index.html", "Playwright 標準レポート"),
]:
    if (reports / filename).exists():
        links.append(f'<a href="{filename}">{label}</a>')
commit = os.getenv("VERIFIED_SHA", os.getenv("GITHUB_SHA", "local"))
body = f"""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cornell 品質レポート</title><style>body{{font:15px/1.8 system-ui,sans-serif;margin:0;background:#f0f6f4;color:#12211d}}header,main{{max-width:1440px;margin:auto;padding:32px}}h1{{font-size:32px}}h2{{font-size:19px}}small{{font-size:12px;color:#4e6862}}nav{{display:flex;gap:20px;flex-wrap:wrap}}a{{color:#236b56}}article{{background:white;border:1px solid #dce7e2;border-radius:12px;padding:24px;margin:20px 0}}.step{{display:grid;grid-template-columns:minmax(0, 1fr) minmax(0, 2fr);border-top:1px solid #dce7e2;padding:22px 0;gap:14px}}img{{width:100%;border:1px solid #dce7e2}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:none}}.failed{{color:#963a29}}@media(max-width:700px){{header,main{{padding:16px}}.step{{grid-template-columns:1fr}}}}</style><header><p>CORNELL / QUALITY REPORT</p><h1>テストで確かめる、ノートの使い心地。</h1><p>対象commit: <code>{esc(commit)}</code> · スクリーンショット {count}枚</p><nav><a href="#e2e">日本語Given / When / Then</a><a href="#quality">静的解析・単体テスト</a>{"".join(links)}</nav><p>すべてのケースを展開表示。スクリーンショットは各段階の実際の操作結果です。カバレッジは単体・結合テストの実測値です。</p></header><main><section id="e2e">{"".join(cards)}</section><section id="quality"><h1>品質検査の結果</h1>{checks}</section></main></html>"""
(reports / "index.html").write_text(body)
(reports / ".nojekyll").touch()
print(f"Report: {len(cards)} cases, {count} screenshots")
