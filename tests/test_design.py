import subprocess
import sys


def test_generation_is_deterministic():
    result = subprocess.run(
        [sys.executable, "tools/design.py", "--check"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_markdown_check_is_read_only_and_removes_only_owned_orphans(tmp_path):
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


def test_markdown_rejects_json_escape_and_symlink(tmp_path):
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


def test_sequence_preserves_branches_transactions_and_exceptions():
    import ast

    import pytest

    from tools.design import sequence

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
    result = sequence(node, [])
    assert result.index("critical try") < result.index("with repo.transaction()")
    assert (
        result.index("alt not value")
        < result.index("404")
        < result.index("option except Conflict")
        < result.index("409")
    )
    assert result.count("break raise") == 2
    node = ast.parse("def execute():\n    while True:\n        pass").body[0]
    with pytest.raises(ValueError, match="Unsupported sequence"):
        sequence(node, [])


def test_ddl_and_openapi_emit_actual_comments_constraints_and_all_operations():
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
