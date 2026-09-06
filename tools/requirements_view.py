import json

try:
    from tools import quintflow
except ModuleNotFoundError:
    import quintflow


def derive() -> tuple[dict, str]:
    """Keep the pinned Dev Standard validation; serialize the catalog only in memory."""
    receipt = quintflow._receipt()
    quintflow._preflight(receipt)
    actual = quintflow.safe_io.read_bytes_nofollow(quintflow.SKILLS_JSON, root=quintflow.ROOT)
    if actual != quintflow._canonical_json(quintflow._skills_view()).encode():
        raise ValueError("Skill contract drift")
    outputs = quintflow._derived(receipt)
    return (
        json.loads(outputs[quintflow.REQUIREMENTS_JSON]),
        outputs[quintflow.REQUIREMENTS_DOC].decode(),
    )
