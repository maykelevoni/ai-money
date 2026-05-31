from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db import init_db
from src.scheduler import create_scheduler
from src.tracker import register_tracker_routes
from src.dashboard import register_dashboard_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = create_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="ai-money engine", docs_url=None, redoc_url=None, lifespan=lifespan)

register_tracker_routes(app)
register_dashboard_routes(app)


@app.get("/health")
def health():
    return {"status": "ok"}
