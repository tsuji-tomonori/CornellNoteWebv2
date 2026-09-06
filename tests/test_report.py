import json
import struct

import pytest

from tools.report import case_tree, collect_cases, coverage_values, e2e_body


def evidence(tmp_path, *, missing=False):
    image = tmp_path / "capture.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 1280, 720))
    attachments = [
        {"name": f"{kind}: 日本語の操作", "contentType": "image/png", "path": str(image)}
        for kind in ["Given", "When", "Then"]
    ]
    if missing:
        attachments.pop()
    attachments.append({"name": "screenshot", "contentType": "image/png", "path": str(image)})
    return {
        "suites": [
            {
                "title": "notes.spec.ts",
                "suites": [
                    {
                        "title": "<共有>",
                        "specs": [
                            {
                                "title": "<script>alert(1)</script>",
                                "tests": [
                                    {
                                        "projectName": "desktop",
                                        "results": [
                                            {"status": "passed", "attachments": attachments}
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }


def test_GWT証跡だけ掲載してケース名を安全に表示する(tmp_path):
    reports = tmp_path / "reports"
    (reports / "screenshots").mkdir(parents=True)
    (reports / "screenshots/obsolete.png").write_bytes(b"old")
    cases, count = collect_cases(evidence(tmp_path), tmp_path, reports)
    assert count == 3
    assert 'width="1280" height="720"' in e2e_body(cases, count)
    assert cases[0]["status"] == "passed"
    assert len(list((reports / "screenshots").glob("*.png"))) == 3
    tree = case_tree(cases)
    assert tree.index("PC") < tree.index("notes.spec.ts") < tree.index("&lt;共有&gt;")
    assert 'href="#case-1"' in tree
    assert "<script>" not in e2e_body(cases, count)
    assert [s["kind"] for s in cases[0]["steps"]] == ["Given", "When", "Then"]


def test_画像不足と再試行成功を通常成功として表示しない(tmp_path):
    data = evidence(tmp_path, missing=True)
    cases, _ = collect_cases(data, tmp_path, tmp_path / "reports")
    assert cases[0]["status"] == "missing"
    assert cases[0]["errors"]
    test = data["suites"][0]["suites"][0]["specs"][0]["tests"][0]
    test["status"] = "flaky"
    test["results"].insert(0, {"status": "failed", "attachments": []})
    cases, count = collect_cases(data, tmp_path, tmp_path / "reports")
    assert cases[0]["status"] == "flaky"
    assert count == 2


def test_画面が閉じても失敗したGWT段階を記録する(tmp_path):
    data = evidence(tmp_path, missing=True)
    result = data["suites"][0]["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result.update(status="failed", steps=[{"title": "Then: ページが閉じられた"}])
    cases, count = collect_cases(data, tmp_path, tmp_path / "reports")
    assert cases[0]["status"] == "failed"
    assert cases[0]["steps"][-1] == {"kind": "Then", "text": "ページが閉じられた", "image": None}
    assert count == 2
    result["attachments"][0]["path"] = str(tmp_path.parent / "outside.png")
    with pytest.raises(ValueError, match="escaped repository"):
        collect_cases(data, tmp_path, tmp_path / "reports")


def test_未計測カバレッジと実測ゼロを区別する(tmp_path):
    assert all(value == "未計測" for _, value, _ in coverage_values(tmp_path))
    (tmp_path / "frontend-coverage").mkdir()
    (tmp_path / "frontend-coverage/coverage-summary.json").write_text(
        json.dumps({"total": {"statements": {"covered": 0, "total": 8}}})
    )
    assert coverage_values(tmp_path)[2][1] == "0.0% (0/8)"
