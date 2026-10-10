"""The web API. It accepts uploads and reports progress.

The check itself runs in a separate worker process.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import configure_logging
from app.migrate import upgrade_db
from app.api import auth, jobs, references


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    upgrade_db()
    yield


app = FastAPI(title="Document Verification API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(references.router, prefix="/references", tags=["references"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
