from app.migrate import migrate


def handler(event: object, context: object) -> dict[str, str]:
    migrate()
    return {"status": "migrated"}
