from pathlib import Path

import pytest

from tools.docs_site import prepare
from tools.infra_design import infrastructure_docs
from tools.test_results import render_results


def test_設計Markdownのリンクを同じサイトのHTMLへ変換する(tmp_path):
    source = tmp_path / "docs/generated"
    (source / "database").mkdir(parents=True)
    (source / "README.gen.md").write_text("# 設計一覧\n\n[CRUD](database/crud.gen.md)\n")
    (source / "database/crud.gen.md").write_text("# CRUD図\n\n[戻る](../README.gen.md)\n")
    prepare(tmp_path, "/CornellNoteWebv2/design")
    result = (tmp_path / "documentation/src/content/docs/index.md").read_text()
    assert "](/CornellNoteWebv2/design/database/crud/)" in result
    assert ".gen.md)" not in result
    (source / "README.gen.md").write_text("# 設計一覧\n\n[不存在](missing.gen.md)\n")
    with pytest.raises(ValueError, match="Broken generated document link"):
        prepare(tmp_path)


def test_インフラ台帳に全リソースの設定と相互参照とIAM条件を含む():
    import json

    from tools.design import page, table

    template = json.loads(Path("cdk.out/CornellNote.template.json").read_text())
    docs = infrastructure_docs(template, page, table)
    types = [p for p in docs if "/types/" in p]
    assert len(types) == len({r["Type"] for r in template["Resources"].values()})
    for logical, r in template["Resources"].items():
        path = "infrastructure/types/" + r["Type"].replace("::", "-").lower() + ".gen.md"
        assert "## " + logical in docs[path]
    assert "Principal" in docs["infrastructure/iam.gen.md"]
    assert "Condition" in docs["infrastructure/iam.gen.md"]
    assert (
        "SigningBehavior" in docs["infrastructure/types/aws-cloudfront-originaccesscontrol.gen.md"]
    )
    assert "flowchart TD" in docs["infrastructure/topology.gen.md"]


def test_詳細設計はDB変更と出力元で説明しログとCRUDを生成する():
    from tools.design import api_docs, database_docs
    from tools.generate_queries import collect

    _, queries = collect()
    docs = api_docs(queries, {"requirements": []})
    listing = docs["apis/list_notes/detail-design.gen.md"]
    assert "正常系入力" in listing and "正常系リソース変更" in listing
    assert "DB: notes.title" in listing and "DB: notes.group_name" in listing
    assert "```python" not in listing
    assert "SQL式: version + 1" in docs["apis/update_note/detail-design.gen.md"]
    assert "INSERT" in docs["apis/create_note/detail-design.gen.md"]
    assert "list_notes.failed" in docs["apis/list_notes/messages.gen.md"]
    assert "exception_type" in docs["apis/list_notes/messages.gen.md"]
    assert "DDLテーブル" in docs["apis/list_notes/query.gen.md"]
    crud = database_docs(queries)["database/crud.gen.md"]
    assert "flowchart TD" in crud and "schema_migrations" in crud
    assert "list_notes" in crud and "|R|" in crud


def test_テスト一覧はJUnitの失敗と日本語名を実際の結果で表示する(tmp_path):
    (tmp_path / "pytest.xml").write_text(
        '<testsuite><testcase classname="backend.tests" name="test_入力を検証する" time="0.2"/><testcase classname="infra.tests" name="test_権限を限定する"><failure>確認&lt;失敗&gt;</failure></testcase></testsuite>'
    )
    output = render_results(tmp_path)
    assert "入力を検証する" in output and "権限を限定する" in output
    assert "失敗" in output and "確認&lt;失敗&gt;" in output
