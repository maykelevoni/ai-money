import os
import uuid
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src import db

# Generated lander HTML must contain this placeholder where the CTA href goes.
# generate.py is expected to emit this token in the lander template.
CTA_PLACEHOLDER = "__CTA_URL__"

LANDERS_DIR = Path("landers")
STATIC_DIR = Path("static")

# Optional: set POSTBACK_SECRET in .env; if set, postback requests must include ?secret=<value>
_POSTBACK_SECRET = os.getenv("POSTBACK_SECRET", "")


def _build_offer_url(tracking_url: str, click_id: str) -> str:
    """Append click_id as subid query param to the CPA offer tracking URL."""
    parsed = urlparse(tracking_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["subid"] = [click_id]
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


def register_tracker_routes(app: FastAPI) -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    LANDERS_DIR.mkdir(parents=True, exist_ok=True)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/landers", StaticFiles(directory=str(LANDERS_DIR)), name="landers")

    @app.get("/lp/{slug}", response_class=HTMLResponse)
    async def landing_page(slug: str, request: Request) -> HTMLResponse:
        zone = request.query_params.get("zone", "")
        country = request.query_params.get("country", "")
        try:
            cost = float(request.query_params.get("cost", "0"))
        except ValueError:
            cost = 0.0

        campaign = db.fetchone(
            "SELECT id, lander_path FROM campaigns WHERE id = ?", (slug,)
        )
        if campaign is None:
            return HTMLResponse("<h1>Not Found</h1>", status_code=404)

        lander_file = (
            Path(campaign["lander_path"])
            if campaign["lander_path"]
            else LANDERS_DIR / slug / "index.html"
        )
        if not lander_file.exists():
            return HTMLResponse("<h1>Lander Not Found</h1>", status_code=404)

        click_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO clicks (click_id, campaign_id, zone, cost, country) VALUES (?, ?, ?, ?, ?)",
            (click_id, campaign["id"], zone, cost, country),
        )

        html = lander_file.read_text(encoding="utf-8")
        html = html.replace(CTA_PLACEHOLDER, f"/go/{click_id}")
        return HTMLResponse(html)

    @app.get("/go/{click_id}")
    async def go_redirect(click_id: str) -> Response:
        row = db.fetchone(
            """
            SELECT o.tracking_url
              FROM clicks c
              JOIN campaigns ca ON ca.id = c.campaign_id
              JOIN offers o ON o.id = ca.offer_id
             WHERE c.click_id = ?
            """,
            (click_id,),
        )
        if row is None:
            return Response(status_code=404)

        redirect_url = _build_offer_url(row["tracking_url"], click_id)
        return RedirectResponse(url=redirect_url, status_code=302)

    @app.api_route("/postback", methods=["GET", "POST"])
    async def postback(request: Request) -> Response:
        if request.method == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}
            subid = body.get("subid") or request.query_params.get("subid", "")
            payout_raw = str(body.get("payout") or request.query_params.get("payout", "0"))
        else:
            subid = request.query_params.get("subid", "")
            payout_raw = request.query_params.get("payout", "0")

        if not subid:
            return Response(content="missing subid", status_code=400)

        if _POSTBACK_SECRET:
            if request.query_params.get("secret", "") != _POSTBACK_SECRET:
                return Response(content="forbidden", status_code=403)

        try:
            payout = float(payout_raw)
        except ValueError:
            payout = 0.0

        # Only insert if the click exists; return 200 either way so CPA network
        # does not retry indefinitely on an unknown subid.
        if db.fetchone("SELECT id FROM clicks WHERE click_id = ?", (subid,)) is not None:
            db.execute(
                "INSERT INTO conversions (click_id, payout) VALUES (?, ?)",
                (subid, payout),
            )

        return Response(content="ok", status_code=200)
