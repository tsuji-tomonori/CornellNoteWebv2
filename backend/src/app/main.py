from fastapi import FastAPI
from mangum import Mangum

from app.apis.notes.create_note.router import router as create_note_router
from app.apis.notes.create_share.router import router as create_share_router
from app.apis.notes.delete_note.router import router as delete_note_router
from app.apis.notes.get_note.router import router as get_note_router
from app.apis.notes.get_shared.router import router as get_shared_router
from app.apis.notes.list_notes.router import router as list_notes_router
from app.apis.notes.revoke_share.router import router as revoke_share_router
from app.apis.notes.update_note.router import router as update_note_router
from app.apis.system.router import router as system_router
from app.auth import settings


def create_app() -> FastAPI:
    settings()
    instance = FastAPI(title="Cornell Note API", version="0.1.0")
    instance.include_router(system_router)
    instance.include_router(list_notes_router)
    instance.include_router(create_note_router)
    instance.include_router(get_note_router)
    instance.include_router(update_note_router)
    instance.include_router(delete_note_router)
    instance.include_router(create_share_router)
    instance.include_router(revoke_share_router)
    instance.include_router(get_shared_router)
    return instance


app = create_app()
handler = Mangum(app)
