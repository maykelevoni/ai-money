# Task 015: Deployment + setup docs

## Description
Make it run unattended on the VPS and document the one-time human setup. This closes the "operator only does setup" promise. (Plan Sections 1, 5; spec Story 1.)

## Files
- `SETUP.md` (create)
- `deploy/ai-money.service` (create — systemd unit)
- `deploy/Caddyfile` (create — HTTPS reverse proxy)
- `README.md` (modify — link setup + run instructions)
- `.gitignore` (create — landers/, data/, .env, __pycache__)

## Requirements
1. `SETUP.md`: step-by-step — create CPA account (+ note possible phone/interview), create traffic account & deposit, create Telegram bot & get chat_id, buy/point domain, fill `.env`, configure the CPA postback URL to `/postback`, record the initial deposit via budget ledger.
2. systemd unit runs `uvicorn src.main:app` with restart-on-failure, env from the file.
3. Caddyfile reverse-proxies the domain to the app with automatic HTTPS.
4. `.gitignore` excludes secrets, db, generated landers.

## Existing Code to Reference
- `src/main.py`, `config/.env.example`.
- spec.md Story 1 (setup is the only manual part), Section 5 (Caddy/systemd).

## Acceptance Criteria
- [ ] Following SETUP.md from scratch yields a running, reachable engine over HTTPS.
- [ ] systemd restarts the service on crash/reboot.
- [ ] Secrets/db/landers are gitignored.

## Dependencies
- Task 013, Task 010

## Commit Message
chore: VPS deployment (systemd + Caddy) and setup docs
