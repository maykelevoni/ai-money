# Task 002: Project scaffold + config

## Description
Stand up the Python project skeleton: dependencies, config loader, FastAPI app that boots and serves /health. Everything else builds on this. (Plan Sections 1, 7.)

## Files
- `requirements.txt` (create)
- `config/.env.example` (modify — expand to ALL keys + thresholds, documented)
- `src/config.py` (create)
- `src/main.py` (create)
- `README.md` (create — short: what it is + honest odds from spec)

## Requirements
1. `requirements.txt`: fastapi, uvicorn, apscheduler, httpx, anthropic, jinja2, python-dotenv, pillow.
2. `config/.env.example` documents every var: CPA + traffic + ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DOMAIN, DASHBOARD_TOKEN, and all optimizer thresholds (GLOBAL_BUDGET, DAILY_CAP, SCALE_ROI, KILL_ROI, KILL_SPEND, MIN_ZONE_CLICKS, MIN_CREATIVE_CLICKS, MIN_CONV).
3. `config.py` loads `.env`, validates required keys are present, exposes a typed `settings` object; fails fast with a clear message if a required key is missing.
4. `main.py`: FastAPI app with `/health` returning `{"status":"ok"}`. Runnable via `uvicorn src.main:app`.

## Existing Code to Reference
- `.ship/plan.md` Section 7 (deps) and Section 8 (file map).

## Acceptance Criteria
- [ ] `pip install -r requirements.txt` succeeds.
- [ ] `uvicorn src.main:app` boots; `GET /health` returns ok.
- [ ] Missing a required env var produces a clear startup error naming the var.

## Dependencies
- Task 001 (uses its key names)

## Commit Message
chore: project scaffold, config loader, FastAPI health endpoint
