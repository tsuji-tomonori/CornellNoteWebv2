import html
import json

from defusedxml import ElementTree as ET


def test_results(reports):
    rows = []
    junit = reports / "pytest.xml"
    if junit.exists():
        for case in ET.fromstring(junit.read_text()).iter("testcase"):
            failure = case.find("failure")
            error = case.find("error")
            state = (
                "skipped"
                if case.find("skipped") is not None
                else "failed"
                if failure is not None or error is not None
                else "passed"
            )
            rows.append(
                (
                    "pytest",
                    case.get("classname", ""),
                    case.get("name", "").removeprefix("test_").replace("_", " "),
                    state,
                    case.get("time", "0"),
                    (
                        failure.text
                        if failure is not None
                        else error.text
                        if error is not None
                        else ""
                    )
                    or "",
                )
            )
    vitest = reports / "vitest.json"
    if vitest.exists():
        for suite in json.loads(vitest.read_text()).get("testResults", []):
            name = suite["name"].split("/frontend/")[-1]
            for case in suite.get("assertionResults", []):
                rows.append(
                    (
                        "Vitest",
                        name,
                        case["fullName"],
                        case["status"],
                        str(case.get("duration", 0) / 1000),
                        "\n".join(case.get("failureMessages", [])),
                    )
                )
    return rows


def render_results(reports):
    rows = test_results(reports)
    if not rows:
        return '<p class="notice">個別テスト結果は未生成です。</p>'
    groups = {}
    for runner, file, title, state, duration, error in rows:
        groups.setdefault((runner, file), []).append((title, state, duration, error))
    labels = {"passed": "成功", "failed": "失敗", "skipped": "スキップ", "pending": "未実行"}
    result = f"<h2>日本語のテスト一覧</h2><p>実行結果 {len(rows)}件。pytestのパラメーター展開後とVitestの各ケースを表示します。</p>"
    for (runner, file), cases in groups.items():
        result += f'<section class="panel unit-suite"><h3>{html.escape(runner + " / " + file)}</h3><div class="table-wrap"><table><thead><tr><th>テストケース</th><th>結果</th><th>秒</th></tr></thead><tbody>'
        for title, state, duration, error in cases:
            result += f"<tr><td>{html.escape(title)}</td><td>{labels.get(state, html.escape(state))}</td><td>{float(duration):.3f}</td></tr>"
            if error:
                result += '<tr><td colspan="3"><pre>' + html.escape(error) + "</pre></td></tr>"
        result += "</tbody></table></div></section>"
    return result
