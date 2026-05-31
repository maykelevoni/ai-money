from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db import init_db
from src.tracker import register_tracker_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ai-money engine", docs_url=None, redoc_url=None, lifespan=lifespan)

register_tracker_routes(app)


@app.get("/health")
def health():
    return {"status": "ok"}
