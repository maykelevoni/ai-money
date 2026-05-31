import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import db

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")


def _check_token(request: Request) -> None:
    token = request.query_params.get("token", "")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    expected = _DASHBOARD_TOKEN
    if not token or not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing dashboard token")


def _budget_data() -> dict:
    rows = db.fetchall("SELECT kind, amount FROM budget_ledger")
    funded = sum(r["amount"] for r in rows if r["kind"] == "deposit")
    spent = sum(r["amount"] for r in rows if r["kind"] == "spend")
    remaining = max(funded - spent, 0.0)
    try:
        from src.config import settings
        cap = settings.global_budget
    except Exception:
        cap = float(os.getenv("GLOBAL_BUDGET", "90"))
    pct = min((spent / cap * 100) if cap > 0 else 0.0, 100.0)
    return {
        "funded": funded,
        "spent": spent,
        "remaining": remaining,
        "cap": cap,
        "pct": round(pct, 1),
        "near_cap": pct >= 80,
    }


def _campaigns_data() -> list[dict]:
    rows = db.fetchall(
        """
        SELECT
            c.id,
            c.status,
            c.daily_cap,
            o.name    AS offer_name,
            o.payout  AS offer_payout,
            COALESCE(ss.spend, 0.0)   AS spend,
            COALESCE(cv.revenue, 0.0) AS revenue,
            COALESCE(cv.conv, 0)      AS conversions
        FROM campaigns c
        JOIN offers o ON o.id = c.offer_id
        LEFT JOIN (
            SELECT campaign_id, SUM(spend) AS spend
            FROM spend_snapshots
            GROUP BY campaign_id
        ) ss ON ss.campaign_id = c.id
        LEFT JOIN (
            SELECT ca.id AS campaign_id,
                   COUNT(cv2.id) AS conv,
                   SUM(cv2.payout) AS revenue
            FROM conversions cv2
            JOIN clicks cl ON cl.click_id = cv2.click_id
            JOIN campaigns ca ON ca.id = cl.campaign_id
            GROUP BY ca.id
        ) cv ON cv.campaign_id = c.id
        ORDER BY c.created_at DESC
        """
    )
    result = []
    for r in rows:
        spend = r["spend"] or 0.0
        revenue = r["revenue"] or 0.0
        conv = r["conversions"] or 0
        roi = ((revenue - spend) / spend * 100) if spend > 0 else 0.0
        profitable = revenue > spend and conv > 0
        result.append(
            {
                "id": r["id"],
                "offer_name": r["offer_name"],
                "status": r["status"],
                "spend": spend,
                "revenue": revenue,
                "roi": round(roi, 1),
                "conversions": conv,
                "profitable": profitable,
                "daily_cap": r["daily_cap"] or 0.0,
            }
        )
    return result


def _decisions_data(limit: int = 50) -> list[dict]:
    rows = db.fetchall(
        "SELECT ts, scope, target_id, action, reason FROM decisions ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


def _pipeline_data() -> dict:
    rows = db.fetchall("SELECT status, COUNT(*) AS cnt FROM offers GROUP BY status")
    counts = {r["status"]: r["cnt"] for r in rows}
    return {
        "candidate": counts.get("candidate", 0),
        "testing": counts.get("testing", 0),
        "winner": counts.get("winner", 0),
        "loser": counts.get("loser", 0),
        "excluded": counts.get("excluded", 0),
    }


def register_dashboard_routes(app: FastAPI) -> None:
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/dash-static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="dashboard-static",
    )

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        _check_token(request)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return _templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "now": now,
                "budget": _budget_data(),
                "campaigns": _campaigns_data(),
                "decisions": _decisions_data(),
                "pipeline": _pipeline_data(),
            },
        )
