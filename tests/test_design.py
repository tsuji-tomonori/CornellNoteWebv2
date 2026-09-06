import subprocess
import sys


def test_設計Markdownの再生成で差分が出ない():
    result = subprocess.run(
        [sys.executable, "tools/design.py", "--check"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_生成差分検査は読み取り専用で管理対象の旧文書だけ削除する(tmp_path):
    import pytest

    from tools.design import page, publish

    outputs = {"apis/example.gen.md": page("example", "actual")}
    publish(outputs, out=tmp_path)
    orphan = tmp_path / "obsolete.gen.md"
    orphan.write_text(page("obsolete", "old"))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.md")}
    with pytest.raises(ValueError, match="drift"):
        publish(outputs, check=True, out=tmp_path)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.md")}
    publish(outputs, out=tmp_path)
    assert not orphan.exists()
    orphan.write_text("manual notes")
    with pytest.raises(ValueError, match="Unowned"):
        publish(outputs, out=tmp_path)
    assert orphan.read_text() == "manual notes"


def test_Markdown生成でJSONとパス逸脱とシンボリックリンクを拒否する(tmp_path):
    import pytest

    from tools.design import publish

    for filename in ["schema.json", "../escape.md", "/outside.md"]:
        with pytest.raises(ValueError, match="owned Markdown"):
            publish({filename: "bad"}, out=tmp_path)
    target = tmp_path / "keep.txt"
    target.write_text("keep")
    (tmp_path / "output.md").symlink_to(target)
    with pytest.raises(ValueError, match="Symlink"):
        publish({"output.md": "bad"}, out=tmp_path)
    assert target.read_text() == "keep"


def test_シーケンスにHTTP分岐を残して内部実装を省く():
    import ast

    import pytest

    from tools.api_sequence import sequence

    node = ast.parse("""
def execute():
    try:
        with repo.transaction() as session:
            value = read(session)
        if not value:
            raise HTTPException(404, "missing")
        return value
    except Conflict:
        raise HTTPException(409, "conflict")
""").body[0]
    definition = {
        "responses": {"200": {"content": {"application/json": {"schema": {"type": "string"}}}}}
    }
    result = sequence(node, [], request="GET /example", definition=definition)
    assert "with repo.transaction()" not in result
    assert "participant Q" not in result
    assert "A->>A" not in result
    assert "HTTP 200" in result
    assert "HTTP 500" in result
    assert (
        result.index("alt not value")
        < result.index("404")
        < result.index("option catch Conflict")
        < result.index("409")
    )
    assert result.count("break 異常終了") == 2
    node = ast.parse("def execute():\n    while True:\n        pass").body[0]
    with pytest.raises(ValueError, match="Unsupported sequence"):
        sequence(node, [], request="GET /example", definition=definition)


def test_DDLとOpenAPIの実際の説明と制約を全API文書に出す():
    from tools.design import OUT, ROOT, api_docs, cell, database_docs, fields
    from tools.generate_queries import collect

    assert cell(["str | None"]) == "str \\| None"
    _, queries = collect()
    db = database_docs(queries)
    assert "schema_migrations" in db["database/er.gen.md"]
    assert "所有者のCognito sub" in db["database/tables/notes.gen.md"]
    assert "VARCHAR(128)" in db["database/tables/notes.gen.md"]
    assert "notes_share_idx" in db["database/tables/notes.gen.md"]
    docs = api_docs(queries, {"requirements": []})
    assert len([p for p in docs if p.endswith("if.gen.md")]) == 10
    assert "$.tasks[].text" in docs["apis/create_note/if.gen.md"]
    assert "maxLength: 500" in docs["apis/create_note/if.gen.md"]
    assert "409" in docs["apis/update_note/messages.gen.md"]
    assert "001_update_note.sql" in docs["apis/update_note/query.gen.md"]
    assert all(p.suffix == ".md" for p in OUT.rglob("*") if p.is_file())
    assert not (ROOT / "spec/requirements/requirements.json").exists()
    assert fields({"type": "string", "maxLength": 17}, {})[0][-1] == {"maxLength": 17}


def test_シーケンスにテーブルと入力と全HTTP応答を記録する():
    from tools.design import api_docs
    from tools.generate_queries import collect

    _, queries = collect()
    docs = api_docs(queries, {"requirements": []})
    listing = docs["apis/list_notes/sequence.gen.md"]
    diagram = listing.split("```mermaid\n")[1].split("```")[0]
    assert diagram.count("participant ") == 3
    assert "C->>A: GET /api/notes" in diagram
    assert "A->>D: SELECT notes" in diagram
    assert "HTTP 200 / application/json: Note[]" in diagram
    assert "HTTP 401" in diagram
    assert "HTTP 500 / text/plain: Internal Server Error" in diagram
    assert "HTTP 404" not in diagram
    assert "HTTP 422" not in diagram
    assert "WHERE owner_id = %(owner_id)s" in listing
    assert "ハンドラ到達前の共通応答" in listing
    assert "HTTP 204 / 本文なし" in docs["apis/delete_note/sequence.gen.md"]
    assert "HTTP 201" in docs["apis/create_note/sequence.gen.md"]
    assert "HTTP 422" in docs["apis/create_note/sequence.gen.md"]
    update = docs["apis/update_note/sequence.gen.md"]
    assert "catch UpdateConflict" in update
    assert "HTTP 404" in update and "HTTP 409" in update


def test_未対応の例外ハンドラー変更を検出する():
    import pytest
    from app.main import create_app

    from tools.api_sequence import verify_framework

    instance = create_app()
    verify_framework(instance)
    instance.debug = True
    with pytest.raises(ValueError, match="Custom error handling"):
        verify_framework(instance)
