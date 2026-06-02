import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import db

_COOKIE_NAME = "dash_session"

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# ============================================================================
#  DASHBOARD PASSWORD  —  change this to whatever you want, then redeploy.
#  No env var needed. This is the password you type on the login page.
# ============================================================================
DASHBOARD_PASSWORD = "postforge"

# Env var still works as an override if ever set, but the line above is all you need.
_DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN") or DASHBOARD_PASSWORD


def _token_valid(token: str) -> bool:
    expected = _DASHBOARD_TOKEN
    return bool(token and expected and secrets.compare_digest(token, expected))


def _is_authed(request: Request) -> bool:
    """Authed via a saved cookie, a ?token= query param, or a Bearer header."""
    if _token_valid(request.cookies.get(_COOKIE_NAME, "")):
        return True
    if _token_valid(request.query_params.get("token", "")):
        return True
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and _token_valid(auth[7:]):
        return True
    return False


def _check_token(request: Request) -> None:
    if not _is_authed(request):
        raise HTTPException(status_code=403, detail="Invalid or missing dashboard token")


_LOGIN_PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PostForge · Dashboard Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,Segoe UI,Roboto,sans-serif;background:#0b0d12;
  color:#e8ecf4;min-height:100vh;display:grid;place-items:center}
.box{background:#12151d;border:1px solid #232838;border-radius:16px;padding:40px;width:min(92vw,380px)}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px;margin-bottom:8px}
.mark{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,#5b8cff,#7c5bff);
  display:grid;place-items:center;color:#fff;font-weight:800}
p.sub{color:#9aa3b5;font-size:14px;margin-bottom:24px}
label{display:block;font-size:13px;color:#9aa3b5;margin-bottom:8px}
input{width:100%;padding:12px 14px;border-radius:10px;border:1px solid #232838;background:#0b0d12;
  color:#e8ecf4;font-size:15px;margin-bottom:18px}
input:focus{outline:none;border-color:#5b8cff}
button{width:100%;padding:12px;border:0;border-radius:10px;font-weight:600;font-size:15px;cursor:pointer;
  background:linear-gradient(135deg,#5b8cff,#7c5bff);color:#fff}
.err{color:#ff6b6b;font-size:13px;margin-bottom:14px;__ERRDISPLAY__}
</style></head><body>
<form class="box" method="post" action="/dashboard/login">
  <div class="logo"><span class="mark">P</span> PostForge</div>
  <p class="sub">Operations dashboard</p>
  <div class="err">Incorrect token — try again.</div>
  <label for="token">Password</label>
  <input type="password" id="token" name="token" autocomplete="current-password"
         autofocus placeholder="Enter password">
  <button type="submit">Sign in</button>
</form></body></html>"""


def _login_page(error: bool = False) -> str:
    return _LOGIN_PAGE.replace("__ERRDISPLAY__", "" if error else "display:none")


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
        # Not signed in → show the login page (no 64-char URL token needed).
        if not _is_authed(request):
            return HTMLResponse(_login_page(), status_code=200)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        resp = _templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "now": now,
                "budget": _budget_data(),
                "campaigns": _campaigns_data(),
                "decisions": _decisions_data(),
                "pipeline": _pipeline_data(),
            },
        )
        # If they arrived via ?token=, drop a cookie so future visits just work.
        qtoken = request.query_params.get("token", "")
        if _token_valid(qtoken):
            resp.set_cookie(
                _COOKIE_NAME, qtoken, httponly=True, secure=True,
                samesite="lax", max_age=60 * 60 * 24 * 30,
            )
        return resp

    @app.post("/dashboard/login")
    async def dashboard_login(token: str = Form("")):
        if not _token_valid(token):
            return HTMLResponse(_login_page(error=True), status_code=401)
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie(
            _COOKIE_NAME, token, httponly=True, secure=True,
            samesite="lax", max_age=60 * 60 * 24 * 30,
        )
        return resp

    @app.get("/dashboard/logout")
    async def dashboard_logout():
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.delete_cookie(_COOKIE_NAME)
        return resp
