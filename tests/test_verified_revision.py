from tools.verified_revision import matches


def test_検証済みコミットとツリーが一致するときだけデプロイする():
    source, commit, tree = "a" * 40, "b" * 40, "c" * 40
    proof = f"{source}\n{commit}\n{tree}\n"
    assert matches(proof, source=source, commit=commit, tree=tree)
    assert not matches(proof, source="d" * 40, commit=commit, tree=tree)
    assert not matches(proof, source=source, commit="d" * 40, tree=tree)
    assert not matches(proof, source=source, commit=commit, tree="d" * 40)
    assert not matches(proof + "extra\n", source=source, commit=commit, tree=tree)
