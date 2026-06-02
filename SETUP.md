# Setup Checklist

One-time human setup. After completing this, the engine runs unattended.

---

## 1. VPS Prerequisites

```bash
# Ubuntu 22.04+ assumed. Install Python 3.11+ and Caddy.
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Caddy (https://caddyserver.com/docs/install)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

Clone the repo and install dependencies:

```bash
git clone <your-repo-url> /opt/ai-money
cd /opt/ai-money
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## 2. Domain

Point a domain (or free DuckDNS subdomain) at your VPS IP.

- **Paid domain:** buy at Namecheap / Porkbun (~$8–12/yr) → add an A record pointing to your VPS IP.
- **Free alternative:** go to https://www.duckdns.org, create a subdomain (e.g. `ai-money.duckdns.org`), and point it at your VPS IP. Run their update script to keep it current if your VPS IP changes.

Verify DNS has propagated before proceeding:
```bash
dig +short yourdomain.example.com
# should return your VPS IP
```

---

## 3. CPA Network Account

**Recommended: MyLead** (clean offers, instant approval, $20 min payout, API + postbacks)

1. Sign up at https://mylead.global/
2. **Note:** some CPA networks require a short phone/email verification or an account manager interview before the API and postbacks are activated. If prompted, complete this step — it typically takes <24h.
3. Once approved, go to **Settings → API** and copy your API key.
4. Confirm your account supports **conversion postbacks** — look for a Postback URL / Global Postback setting.

**Fallback: CPALead** (https://www.cpalead.com/) — instant approval, but catalog skews gray-hat. Use clean-vertical filter in `offers.py`.

---

## 4. Traffic Network Account

**PropellerAds** is the chosen network (API verified, push/pop/interstitial, already supported in code).

1. Sign up / log into https://ssp.propellerads.com/
2. Fund your advertiser account (minimum $100 by card, or keep using your existing balance).
3. Go to **Account Settings → API** and generate a self-serve API key.
4. Note your **Advertiser account ID** (shown in the URL or profile page).

---

## 5. Telegram Bot

1. Open Telegram, search for `@BotFather`, start a chat.
2. Send `/newbot`, follow the prompts, copy the **bot token** (looks like `123456789:ABCdef...`).
3. Start a chat with your new bot (or add it to a group).
4. Get your chat ID:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   # Look for "chat":{"id": ...} in the response
   ```
5. Keep the token and chat ID handy for the `.env` step below.

---

## 6. Configure `.env`

```bash
cp config/.env.example config/.env
nano config/.env   # or use your preferred editor
```

Fill in every value:

| Key | Where to get it |
|-----|----------------|
| `PROPELLERADS_API_KEY` | PropellerAds → Account Settings → API |
| `MYLEAD_API_KEY` | MyLead → Settings → API |
| `CPALEAD_AFFILIATE_ID` | CPALead → Account Info (only if using CPALead) |
| `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| `LLM_MODEL` | OpenRouter model id (optional; default `deepseek/deepseek-chat`) |
| `TELEGRAM_BOT_TOKEN` | @BotFather → your bot token |
| `TELEGRAM_CHAT_ID` | `getUpdates` response (step 5 above) |
| `DOMAIN` | Your domain, no trailing slash: `https://yourdomain.example.com` |
| `DASHBOARD_TOKEN` | Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `GLOBAL_BUDGET` | Your total lifetime ad spend ceiling in USD (e.g. `90.00`) |
| `DAILY_CAP` | Max ad spend per day in USD (e.g. `10.00`) |

Review the optimizer thresholds at the bottom of `.env` — the defaults are conservative and safe for a $100 seed budget.

---

## 7. Configure CPA Postback URL

In your CPA network dashboard, set your **Global Postback URL** to:

```
https://yourdomain.example.com/postback?subid={subid}&payout={payout}
```

Replace `yourdomain.example.com` with the value in `DOMAIN`. Use the macro names your network uses — MyLead and CPALead both support `{subid}` and `{payout}`.

This fires every time a visitor converts, crediting the revenue to the right campaign.

---

## 8. Record Initial Deposit in Budget Ledger

The engine tracks all spend against the budget ledger. Log your initial ad-account deposit so the remaining-budget display is accurate from day one:

```bash
cd /opt/ai-money
.venv/bin/python - <<'EOF'
from src.db import get_db
from src.budget import record_deposit

with get_db() as db:
    record_deposit(db, amount=100.00, note="Initial PropellerAds deposit")
    print("Deposit recorded.")
EOF
```

Adjust the `amount` to match what you actually deposited.

---

## 9. Deploy: systemd Service

```bash
sudo cp deploy/ai-money.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-money
sudo systemctl start ai-money
sudo systemctl status ai-money   # should show "active (running)"
```

Check logs:
```bash
sudo journalctl -u ai-money -f
```

---

## 10. Deploy: Caddy HTTPS

```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
# Edit /etc/caddy/Caddyfile — replace yourdomain.example.com with your actual domain
sudo systemctl reload caddy
```

Caddy automatically obtains and renews a Let's Encrypt TLS certificate. The engine is now reachable at `https://yourdomain.example.com`.

Verify:
```bash
curl https://yourdomain.example.com/health
# {"status":"ok"}
```

---

## 11. Verify End-to-End

1. **Dashboard:** open `https://yourdomain.example.com/dashboard?token=<DASHBOARD_TOKEN>` in a browser — you should see the budget bar and empty campaign table.
2. **Health:** `curl https://yourdomain.example.com/health` → `{"status":"ok"}`
3. **Postback test:** `curl "https://yourdomain.example.com/postback?subid=test&payout=1.00"` → should return 200 OK.
4. **Telegram:** the engine sends a startup notification — check that it arrives in your bot chat.

Once all four checks pass, the engine is live and running autonomously. You will receive a daily Telegram report each morning.

---

## Maintenance Notes

- **Top up ad budget:** when the PropellerAds balance is low, deposit more. The engine will resume spending as soon as `GLOBAL_BUDGET` headroom remains.
- **Review decisions:** check `/dashboard` weekly to see what the optimizer killed/scaled.
- **Swap CPA offers:** the engine cycles offers automatically, but you can manually mark an offer `excluded` in the DB if needed.
- **Update code:** `git pull && sudo systemctl restart ai-money`
