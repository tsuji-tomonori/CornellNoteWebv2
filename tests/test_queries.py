import pytest

from tools.generate_queries import ROOT, analyze, check_architecture, render, schema, write_outputs


@pytest.fixture
def project(tmp_path):
    migration = tmp_path / "backend/migrations"
    migration.mkdir(parents=True)
    for path in (ROOT / "backend/migrations").glob("*.sql"):
        (migration / path.name).write_text(path.read_text())
    sql = tmp_path / "backend/src/app/apis/notes/get_note/sql"
    sql.mkdir(parents=True)
    source = ROOT / "backend/src/app/apis/notes/get_note/sql/001_select_note.sql"
    (sql / source.name).write_text(source.read_text())
    return tmp_path


def test_SQL生成が決定的で差分検査が書き込まない(project):
    first = render(project)
    assert first == render(project)
    write_outputs(first, check=False, root=project)
    write_outputs(first, check=True, root=project)
    output = next(path for path in first if path.name == "queries.py")
    assert "id: UUID" in output.read_text()
    assert "owner_id: str" in output.read_text()
    output.write_text(output.read_text() + "\n# drift\n")
    modified = output.read_bytes()
    with pytest.raises(ValueError, match="drift"):
        write_outputs(first, check=True, root=project)
    assert output.read_bytes() == modified


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("SELECT * FROM notes", "enumerate"),
        ("SELECT missing FROM notes", "unknown column"),
        ("SELECT id FROM notes; DELETE FROM notes", "exactly one"),
        ("SELECT id FROM notes WHERE id = :id", "pyformat"),
        ("SELECT id FROM notes WHERE owner_id = %(id)s", "compared/assigned"),
        ("SELECT count(id) FROM notes", "computed result"),
        ("SELECT x.id FROM notes n JOIN users u ON n.owner_id=u.id", "unknown column"),
    ],
)
def test_未対応または不正なSQLを明示的に拒否する(tmp_path, sql, message):
    path = tmp_path / "001_invalid.sql"
    path.write_text("-- 不正なSQLの検知\n" + sql + ";\n")
    with pytest.raises(ValueError, match=message):
        analyze(path, schema(ROOT))


def test_インラインSQLとルーターからの直接クエリ利用を拒否する(project):
    operation = project / "backend/src/app/apis/notes/get_note"
    function = operation / "functions.py"
    function.write_text('statement = "SELECT id FROM notes"\n')
    with pytest.raises(ValueError, match="inline SQL"):
        check_architecture(project)
    function.unlink()
    (operation / "router.py").write_text("from .generated import queries\n")
    with pytest.raises(ValueError, match="routers must call functions"):
        check_architecture(project)


def test_生成SQLの出力でシンボリックリンクを辿らない(project, tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("unchanged")
    output = project / "backend/src/app/apis/notes/get_note/generated/queries.py"
    output.parent.mkdir(parents=True)
    output.symlink_to(target)
    with pytest.raises(ValueError, match="Unsafe generated output"):
        write_outputs({output: "overwritten"}, check=False, root=project)
    assert target.read_text() == "unchanged"


def test_JOINの型と参照元をDDLから導出する():
    path = ROOT / "backend/src/app/apis/notes/list_tasks/sql/001_select_tasks.sql"
    query = analyze(path, schema(ROOT))
    assert query["tables"] == ["note_tasks", "notes"]
    assert query["row_sources"]["title"] == "notes.title"
    assert query["row_sources"]["done"] == "note_tasks.done"
    assert query["rows"]["done"] == "bool"
    assert query["rows"]["due"] == "date | None"
    assert query["param_sources"]["owner_id"] == "notes.owner_id"


def test_関数層のトランザクション開始を拒否する(tmp_path):
    operation = tmp_path / "backend/src/app/apis/notes/invalid"
    operation.mkdir(parents=True)
    (operation / "functions.py").write_text(
        "def save(repo):\n    with repo.transaction():\n        pass\n"
    )
    with pytest.raises(ValueError, match="transaction belongs to router"):
        check_architecture(tmp_path)
