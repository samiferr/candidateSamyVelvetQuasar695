import yaml
from fastapi import FastAPI
from lockstream.infrastructure.database import Base, engine, SessionLocal
from lockstream.presentation.routers import router
from lockstream.services.lockstream_service import rebuild_projection_service

app = FastAPI()


# Use the contractual schema
def custom_openapi():
    with open("lockstream/openapi/openapi.yaml") as f:
        return yaml.safe_load(f)


@app.on_event("startup")
def _rebuild_projection_on_startup() -> None:
    """
    On startup:
      1) ensure in-memory tables exist
      2) replay append-only JSONL event log into the in-memory DB projection
    """
    db = SessionLocal()
    try:
        rebuild_projection_service(db)
    finally:
        db.close()


app.openapi = custom_openapi
Base.metadata.create_all(bind=engine)
app.include_router(router)
