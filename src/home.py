"""Public root homepage for the domain (e.g. getpostforge.cloud).

Serves a legitimate branded landing/about page at "/" so the bare domain shows
a real, professional site — required for CPA-network (MyLead) traffic-source
approval, where a reviewer visits the domain root.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def register_home_routes(app: FastAPI) -> None:
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(
            request,
            "index.html",
            {"year": datetime.now(timezone.utc).year},
        )

    @app.get("/robots.txt", response_class=PlainTextResponse)
    async def robots() -> PlainTextResponse:
        # Allow indexing of the homepage; keep tracker/dashboard paths out of crawlers.
        return PlainTextResponse(
            "User-agent: *\n"
            "Allow: /$\n"
            "Disallow: /lp/\n"
            "Disallow: /go/\n"
            "Disallow: /dashboard\n"
            "Disallow: /postback\n"
        )
