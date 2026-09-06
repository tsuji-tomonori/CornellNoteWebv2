import html
import json
import os
import re
import shutil
import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
esc = html.escape
GWT = re.compile(r"^(Given|When|Then):\s*(.+)$", re.DOTALL)
NAV = [
    ("index.html", "サマリー"),
    ("e2e.html", "E2E"),
    ("static.html", "静的解析"),
    ("tests.html", "単体・結合テスト"),
    ("coverage.html", "カバレッジ"),
    ("docs.html", "設計書"),
]
LABELS = {
    "passed": "成功",
    "failed": "失敗",
    "unexpected": "予期しない結果",
    "timedOut": "時間切れ",
    "interrupted": "中断",
    "skipped": "スキップ",
    "not-run": "未実行",
    "flaky": "再試行で成功",
    "missing": "証跡不足",
}


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def badge(status):
    return f'<span class="badge {esc(status.lower())}">{esc(LABELS.get(status, status))}</span>'


def shell(title, body, *, active, commit, wide=False):
    nav = "".join(
        f'<a href="{path}"{chr(32) + "aria-current=page" if path == active else ""}>{label}</a>'
        for path, label in NAV
    )
    return f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · Cornell Quality</title><link rel="stylesheet" href="assets/report.css"><script src="assets/report.js" defer></script></head><body><a class="skip" href="#main">本文へ移動</a><header class="topbar"><a class="brand" href="index.html">CORNELL / QUALITY</a><nav class="global-nav" aria-label="レポートの分類">{nav}</nav></header>{body if wide else '<main class="wrap" id="main">' + body + "</main>"}<footer class="page-footer">対象commit: <code>{esc(commit)}</code> · 実行結果に基づく品質レポート</footer></body></html>'


def collect_cases(data, root, reports):
    cases, count = [], 0
    images = reports / "screenshots"
    images.mkdir(parents=True, exist_ok=True)
    for old in images.glob("*.png"):
        old.unlink()

    def walk(suite, parents):
        title = suite.get("title", "")
        hierarchy = (
            (*parents, title) if title and (not parents or title != parents[-1]) else parents
        )
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                nonlocal count
                result = next(iter(reversed(test.get("results", []))), {})
                state = result.get("status", "not-run")
                if test.get("status") in {"flaky", "unexpected"}:
                    state = test["status"]
                steps, problems = [], []
                for attachment in result.get("attachments", []):
                    match = GWT.fullmatch(attachment.get("name", ""))
                    if not match or attachment.get("contentType") != "image/png":
                        continue
                    step = {"kind": match[1], "text": match[2], "image": None}
                    path = attachment.get("path")
                    if path:
                        source = Path(path)
                        if not source.is_absolute():
                            source = root / "frontend" / source
                        source = source.resolve()
                        if not source.is_relative_to(root.resolve()):
                            raise ValueError("Screenshot escaped repository")
                        if source.is_file():
                            count += 1
                            name = f"{count:03}.png"
                            shutil.copyfile(source, images / name)
                            step["image"] = "screenshots/" + name
                            with source.open("rb") as stream:
                                header = stream.read(24)
                            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) == 24:
                                step["dimensions"] = struct.unpack(">II", header[16:24])
                    if not step["image"]:
                        problems.append(match[0] + "：画像がありません")
                    steps.append(step)

                # Failed steps may end before an attachment can be written (for example page closed).
                def missing_steps(items, steps, problems):
                    for item in items:
                        match = GWT.fullmatch(item.get("title", ""))
                        if match and not any(
                            s["kind"] == match[1] and s["text"] == match[2] for s in steps
                        ):
                            steps.append({"kind": match[1], "text": match[2], "image": None})
                            problems.append(match[0] + "：画像を取得できませんでした")
                        missing_steps(item.get("steps", []), steps, problems)

                missing_steps(result.get("steps", []), steps, problems)
                if state == "passed" and (
                    {s["kind"] for s in steps} != {"Given", "When", "Then"} or problems
                ):
                    state = "missing"
                    problems.append("成功ケースのGiven / When / Then証跡が揃っていません")
                cases.append(
                    {
                        "id": f"case-{len(cases) + 1}",
                        "title": spec["title"],
                        "project": test.get("projectName", "未指定"),
                        "hierarchy": hierarchy or (spec.get("file", "テスト"),),
                        "status": state,
                        "steps": steps,
                        "errors": [e.get("message", "") for e in result.get("errors", [])]
                        + problems,
                        "duration": result.get("duration", 0),
                    }
                )
        for child in suite.get("suites", []):
            walk(child, hierarchy)

    for suite in data.get("suites", []):
        walk(suite, ())
    return cases, count


def case_tree(cases):
    tree = {}
    for case in cases:
        branch = tree
        for name in (case["project"], *case["hierarchy"]):
            branch = branch.setdefault(name, {"groups": {}, "cases": []})["groups"]
        branch.setdefault("", {"groups": {}, "cases": []})["cases"].append(case)

    def render(branch):
        result = "<ul>"
        for name, value in branch.items():
            if name:
                label = {"desktop": "PC", "mobile": "スマートフォン"}.get(name, name)
                result += f'<li><span class="group-label">{esc(label)}</span>{render(value["groups"])}</li>'
            for case in value["cases"]:
                result += f'<li><a href="#{case["id"]}">{esc(case["title"])}<br>{badge(case["status"])}</a></li>'
        return result + "</ul>"

    return '<nav class="case-tree" aria-label="テストケース一覧">' + render(tree) + "</nav>"


def e2e_body(cases, count):
    cards = []
    for case in cases:
        steps = []
        for step in case["steps"]:
            caption = step["kind"] + ": " + step["text"]
            dimensions = step.get("dimensions")
            size = f' width="{dimensions[0]}" height="{dimensions[1]}"' if dimensions else ""
            shot = (
                f'<a class="shot" data-screenshot data-caption="{esc(caption)}" href="{step["image"]}" target="_blank" rel="noopener" aria-label="{esc(caption)}の画像を拡大"><img src="{step["image"]}" alt="{esc(caption)}"{size} loading="lazy"><span>クリックして拡大 ↗</span></a>'
                if step["image"]
                else '<p class="notice">この段階の画像は取得できませんでした。</p>'
            )
            steps.append(
                f'<section class="step"><div><span class="phase">{step["kind"]}</span><p class="step-text">{esc(step["text"])}</p></div>{shot}</section>'
            )
        errors = "".join(f'<pre class="notice">{esc(e)}</pre>' for e in case["errors"])
        cards.append(
            f'<article class="case" id="{case["id"]}"><p class="case-meta">{esc(case["project"])} / {esc(" / ".join(case["hierarchy"]))} · {case["duration"] / 1000:.1f}秒</p><h2>{esc(case["title"])}</h2>{badge(case["status"])}{"".join(steps)}{errors}</article>'
        )
    dialog = '<dialog class="zoom" id="screenshot-dialog" aria-labelledby="screenshot-title"><header><h2 id="screenshot-title">スクリーンショット</h2><button type="button">閉じる</button></header><div class="image-stage"><img alt=""></div><footer><a data-original target="_blank" rel="noopener">原寸画像を開く</a> · Escキーでも閉じられます</footer></dialog>'
    return (
        '<div class="layout"><aside class="sidebar"><h2>テストケース</h2>'
        + case_tree(cases)
        + '</aside><main id="main"><div class="intro"><p class="eyebrow">END TO END</p><h1>操作と結果を、段階ごとに。</h1>'
        + f'<p>{len(cases)}ケース · Given / When / Thenの画像 {count}枚</p><p class="muted">左の一覧からケースへ移動できます。全ケースを常時表示し、各段階の画像だけを掲載しています。</p></div>'
        + ("".join(cards) or '<p class="notice">E2Eは未実行です。</p>')
        + "</main></div>"
        + dialog
    )


def check_summary(checks):
    if not checks:
        return "未実行"
    failures = sum(c["exit_code"] != 0 for c in checks)
    return f"{len(checks) - failures} / {len(checks)} 成功" + (
        f" · {failures} 失敗" if failures else ""
    )


def check_details(checks):
    return (
        "".join(
            f'<article class="panel"><h2>{esc(c["name"])}</h2>{badge("passed" if c["exit_code"] == 0 else "failed")}<pre>{esc(c["output"])}</pre></article>'
            for c in checks
        )
        or '<p class="notice">検査結果がありません。</p>'
    )


def coverage_values(reports):
    py = load(reports / "python-coverage.json", {}).get("totals", {})
    ts = load(reports / "frontend-coverage/coverage-summary.json", {}).get("total", {})

    def fraction(hit, total):
        return f"{hit / total * 100:.1f}% ({hit}/{total})" if total else "対象なし"

    return [
        (
            "Python 行",
            fraction(py["covered_lines"], py["num_statements"]) if py else "未計測",
            "python-coverage/index.html",
        ),
        (
            "Python 分岐",
            fraction(py.get("covered_branches", 0), py.get("num_branches", 0)) if py else "未計測",
            "python-coverage/index.html",
        ),
        *[
            (
                "TypeScript " + label,
                fraction(ts[key]["covered"], ts[key]["total"]) if key in ts else "未計測",
                "frontend-coverage/index.html",
            )
            for key, label in [("lines", "行"), ("branches", "分岐"), ("functions", "関数")]
        ],
    ]


def generate(root=ROOT):
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    data = load(reports / "playwright.json", {})
    cases, count = collect_cases(data, root, reports)
    quality = load(reports / "quality.json", [])
    static = [c for c in quality if not c["name"].startswith(("pytest", "Vitest"))]
    unit = [c for c in quality if c["name"].startswith(("pytest", "Vitest"))]
    ui = load(reports / "report-ui.json", {})
    if ui:
        stats = ui.get("stats", {})
        unit.append(
            {
                "name": "レポートUI (Playwright)",
                "exit_code": 1
                if stats.get("unexpected", 0)
                or stats.get("flaky", 0)
                or not stats.get("expected", 0)
                else 0,
                "output": f"成功 {stats.get('expected', 0)} / 失敗 {stats.get('unexpected', 0)} / スキップ {stats.get('skipped', 0)}",
            }
        )
    commit = os.getenv("VERIFIED_SHA", os.getenv("GITHUB_SHA", "local"))
    states = Counter(c["status"] for c in cases)
    summary = " · ".join(f"{LABELS.get(k, k)} {v}" for k, v in sorted(states.items())) or "未実行"
    coverage = coverage_values(reports)
    intro = (
        '<div class="intro"><p class="eyebrow">QUALITY OVERVIEW</p><h1>品質の状態を、ひと目で。</h1><p>各検査の結果から、詳しい証跡へ進めます。</p>'
        + f'<p class="revision">対象commit: <code>{esc(commit)}</code></p></div>'
    )

    def card(title, value, detail, href):
        return f'<article class="panel"><h2>{title}</h2><p class="metric">{esc(value)}</p><p class="muted">{esc(detail)}</p><a class="card-link" href="{href}">{title}の詳細を見る →</a></article>'

    dashboard = (
        intro
        + '<section class="grid" aria-label="検査結果のサマリー">'
        + card("E2E", f"{len(cases)} ケース", summary + f" / GWT画像 {count}枚", "e2e.html")
        + card(
            "静的解析",
            check_summary(static),
            "リンター・フォーマッター・型検査・SQL・生成差分",
            "static.html",
        )
        + card(
            "単体・結合テスト",
            check_summary(unit),
            "Python / TypeScript / CDK assertions・nag・snapshot",
            "tests.html",
        )
        + card(
            "カバレッジ",
            "行・分岐・関数",
            "Python行 " + coverage[0][1] + " / TypeScript行 " + coverage[2][1],
            "coverage.html",
        )
        + card("自動生成設計書", "Markdown", "API・DB・画面・インフラ・要件の仕様", "docs.html")
        + "</section>"
    )
    run_errors = data.get("errors", [])
    if run_errors:
        dashboard += (
            '<section class="panel"><h2>E2E実行エラー</h2>'
            + "".join(f"<pre>{esc(e.get('message', str(e)))}</pre>" for e in run_errors)
            + "</section>"
        )
    pages = {
        "index.html": ("品質サマリー", dashboard, False),
        "e2e.html": ("E2Eテスト", e2e_body(cases, count), True),
        "static.html": (
            "静的解析",
            '<h1>静的解析・フォーマット</h1><p><a href="sql.html">SQLFluffの指摘をSQLソースで確認 →</a></p>'
            + check_details(static),
            False,
        ),
        "tests.html": (
            "単体・結合テスト",
            '<h1>単体・結合テスト</h1><p>実行コマンドの成否と検証結果です。コード行の実測値は<a href="coverage.html">カバレッジ</a>から確認できます。</p>'
            + check_details(unit),
            False,
        ),
    }
    coverage_rows = "".join(
        f"<tr><td>{label}</td><td>{esc(value)}</td><td>"
        + (
            f'<a href="{link}">コード行の詳細 →</a>'
            if (reports / link).exists()
            else "レポート未生成"
        )
        + "</td></tr>"
        for label, value, link in coverage
    )
    pages["coverage.html"] = (
        "カバレッジ",
        '<h1>コードから確認するカバレッジ</h1><p>単体・結合テストで計測した値です。未計測を0%や成功として扱いません。</p><div class="table-wrap"><table><thead><tr><th>対象</th><th>カバレッジ</th><th>詳細</th></tr></thead><tbody>'
        + coverage_rows
        + "</tbody></table></div>",
        False,
    )
    sql_sections = []
    for entry in load(reports / "sqlfluff.json", []):
        path = (root / entry["filepath"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("SQL diagnostic path escaped repository")
        findings = (
            esc(json.dumps(entry["violations"], ensure_ascii=False, indent=2))
            if entry["violations"]
            else "指摘なし"
        )
        lines = "\n".join(
            f"{i:3}  {esc(line)}" for i, line in enumerate(path.read_text().splitlines(), 1)
        )
        sql_sections.append(
            f'<article class="panel"><h2>{esc(entry["filepath"])}</h2><p>{findings}</p><pre><code>{lines}</code></pre></article>'
        )
    pages["sql.html"] = (
        "SQLFluff",
        "<h1>SQLFluff・SQLソース</h1>"
        + ("".join(sql_sections) or '<p class="notice">未実行です。</p>'),
        False,
    )
    documentation = root / "docs/generated"
    doclinks = []
    if documentation.exists():
        shutil.copytree(documentation, reports / "docs", dirs_exist_ok=True)
        for path in sorted(documentation.rglob("*.md")):
            name = path.relative_to(documentation).as_posix()
            doclinks.append(
                f'<li><a href="https://github.com/tsuji-tomonori/CornellNoteWebv2/blob/dev/docs/generated/{esc(name)}">{esc(name)}</a> · <a href="docs/{esc(name)}">Markdown</a></li>'
            )
    pages["docs.html"] = (
        "自動生成仕様書",
        '<h1>実装・要件から自動生成した仕様書</h1><p>文書名はGitHub表示、Markdownはこの実行時点の生成物です。</p><ul class="summary-list">'
        + "".join(doclinks)
        + "</ul>",
        False,
    )
    for filename, (title, body, wide) in pages.items():
        (reports / filename).write_text(
            shell(title, body, active=filename, commit=commit, wide=wide)
        )
    shutil.copytree(ROOT / "tools/report_assets", reports / "assets", dirs_exist_ok=True)
    (reports / ".nojekyll").touch()
    print(f"Report: {len(cases)} cases, {count} GWT screenshots, dashboard + hierarchical E2E")
    return not any(c["status"] == "missing" for c in cases)


if __name__ == "__main__":
    raise SystemExit(0 if generate() else 1)
