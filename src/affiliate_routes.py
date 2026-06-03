"""Public routes: serve affiliate pages and track click-throughs."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from src import db
from src.clients import digistore24

_PAGES_DIR = Path("pages")


def register_affiliate_routes(app: FastAPI) -> None:
    @app.get("/p/{slug}", response_class=HTMLResponse)
    async def serve_page(slug: str) -> Response:
        row = db.fetchone(
            "SELECT file_path, status FROM affiliate_pages WHERE slug = ?", (slug,)
        )
        if row is None or row["status"] == "paused":
            return HTMLResponse("<h1>Not Found</h1>", status_code=404)

        page_file = Path(row["file_path"])
        if not page_file.exists():
            return HTMLResponse("<h1>Not Found</h1>", status_code=404)

        db.execute(
            "UPDATE affiliate_pages SET views = views + 1 WHERE slug = ?", (slug,)
        )
        return HTMLResponse(page_file.read_text(encoding="utf-8"))

    @app.get("/aff/{slug}")
    async def affiliate_redirect(slug: str) -> Response:
        row = db.fetchone(
            """
            SELECT ap.product_id
              FROM affiliate_pages ap
             WHERE ap.slug = ? AND ap.status = 'live'
            """,
            (slug,),
        )
        if row is None:
            return Response(status_code=404)

        db.execute(
            "UPDATE affiliate_pages SET clicks = clicks + 1 WHERE slug = ?", (slug,)
        )

        affiliate_name = digistore24.resolve_affiliate_name()
        url = digistore24.build_promolink(row["product_id"], affiliate_name, slug)
        return RedirectResponse(url=url, status_code=302)
