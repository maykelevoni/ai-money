from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ai-money engine", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
