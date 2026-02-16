# Telegram AI Student Bot (FastAPI, Webhook, PostgreSQL, Redis)

Production-oriented MVP architecture for a Telegram SaaS bot.

## 1. Prerequisites (macOS)

Install tools:

```bash
xcode-select --install
brew install python@3.11 docker docker-compose ngrok
```

Check versions:

```bash
python3 --version
docker --version
docker compose version
ngrok --version
```

## 2. Project setup

```bash
cd "/Users/oleksandrrevko/Documents/New project"
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp token.env.example token.env
```

Open `token.env` and set:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET` (any random string)
- `ADMIN_TOKEN` (random admin secret)
- `OPENAI_API_KEY` (optional for now; without it bot returns fallback MVP answers)
- `OPENAI_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_IMAGE_MODEL` (default `gpt-image-1`)
- `STUDENT_PRICE_USD` and `PRO_PRICE_USD` for subscription card prices
- `GOOGLE_SHEETS_ID`
- `GOOGLE_SHEETS_WORKSHEET` (for example `users`)
- `GOOGLE_SERVICE_ACCOUNT_FILE` (path to service-account JSON)

## 3. Start PostgreSQL + Redis

```bash
docker compose up -d
```

Services:
- PostgreSQL: `localhost:5432`, db `student_bot`
- Redis: `localhost:6379`

## 4. Start FastAPI locally

```bash
source .venv/bin/activate
./scripts/run_dev.sh
```

Health check:

```bash
curl http://localhost:8000/health
```

## 5. Start ngrok tunnel

In another terminal:

```bash
ngrok http 8000
```

Copy HTTPS URL, for example:
`https://abc123.ngrok-free.app`

Set env var and restart API server:

```bash
export TELEGRAM_WEBHOOK_URL="https://abc123.ngrok-free.app"
./scripts/run_dev.sh
```

On startup, app will call Telegram `setWebhook` using:
`https://abc123.ngrok-free.app/telegram/webhook/<TELEGRAM_WEBHOOK_SECRET>`

Manual webhook check:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

## 6. Test bot flow

In Telegram:
1. Send `/start`
2. Optional: send `/help` for quick usage hints
3. Bot auto-detects language via `language_code`
4. If unsupported language: language picker appears
5. Use menu buttons:
   - Explain / Solve / Summary consume limits
   - Image generation is PRO-only and uses separate image limits
   - Photo analysis works from uploaded photos and is limited by plan
   - Long texts work on `student` and `pro` with separate daily/monthly limits
   - My limit shows daily+monthly usage
   - Subscription lets user choose `free`, `student`, or `pro`
6. Use `/cancel` to reset current pending mode
7. In `💳 Subscription`, user can choose plan with inline buttons (`FREE` / `STUDENT` / `PRO`) in demo mode

## 7. Admin API (CRM foundation)

Use header `X-Admin-Token: <ADMIN_TOKEN>`.

List users:

```bash
curl -H "X-Admin-Token: change_me" "http://localhost:8000/admin/users"
```

Ban user:

```bash
curl -X POST -H "X-Admin-Token: change_me" "http://localhost:8000/admin/users/<telegram_id>/ban"
```

Set plan (free/student/pro):

```bash
curl -X POST -H "X-Admin-Token: change_me" "http://localhost:8000/admin/users/<telegram_id>/plan/student"
```

Query logs:

```bash
curl -H "X-Admin-Token: change_me" "http://localhost:8000/admin/query-logs?limit=20"
```

Admin stats:

```bash
curl -H "X-Admin-Token: change_me" "http://localhost:8000/admin/stats"
```

Reset limits (daily/monthly/all):

```bash
curl -X POST -H "X-Admin-Token: change_me" "http://localhost:8000/admin/users/<telegram_id>/reset-limits?scope=all"
```

Grant bonus image credits:

```bash
curl -X POST -H "X-Admin-Token: change_me" "http://localhost:8000/admin/users/<telegram_id>/grant-image-credits?amount=5"
```

Window CRM page:

```bash
open http://localhost:8000/crm
```

In CRM page:
- paste `X-Admin-Token`
- see subscribers count and usage cards
- filter/search/sort users by all main parameters
- manage user plan/ban/limits/bonus credits via buttons
- run Google Sheets sync (`Sheets Pull/Push/Both`)

Google Sheets setup (two-way sync):
1. Create Google Cloud project and enable Google Sheets API.
2. Create Service Account and download JSON key.
3. Save key file to path from `GOOGLE_SERVICE_ACCOUNT_FILE` (default `credentials/google-service-account.json`).
4. Create Google Sheet and copy Spreadsheet ID from URL to `GOOGLE_SHEETS_ID`.
5. Create worksheet tab (default name `users`) and set `GOOGLE_SHEETS_WORKSHEET`.
6. Share the sheet with service-account email (`...@...gserviceaccount.com`) with Editor rights.

Manual sync API:

```bash
curl -X POST -H "X-Admin-Token: change_me" "http://localhost:8000/admin/sync/google-sheets?direction=both"
```

## 8. Limits logic in MVP

- Daily requests limit: Redis key by user and date.
- Monthly requests/tokens + plan: PostgreSQL `users` table.
- Free plan:
  - 50 requests/month
  - 5 requests/day
  - max output profile = 400 tokens
  - image generation: disabled
  - photo analysis: 8/month, 1/day
- Student plan:
  - 250 requests/month
  - 25 requests/day
  - 120k tokens/month
  - image generation: disabled
  - photo analysis: 60/month, 6/day
  - long texts: 40/month, 4/day
- Pro plan:
  - 1000 requests/month
  - 100 requests/day
  - 300k tokens/month
  - image generation: 30/month, 2/day
  - photo analysis: 300/month, 30/day
  - long texts: 120/month, 12/day

## 9. Architecture overview

- `app/main.py`: FastAPI app + startup bootstrap + optional webhook registration.
- `app/api/telegram.py`: Telegram webhook endpoint.
- `app/services/bot_logic.py`: message handling, menu routing, limits, LLM calls, audit logs.
- `app/services/limits.py`: Redis + PostgreSQL limits logic.
- `app/services/llm.py`: OpenAI Responses API integration + fallback mode.
- `app/api/admin.py`: basic CRM/admin endpoints.
- `app/core/i18n.py`: multilingual strings and menu labels.
- `app/models/user.py`: user/tariff/usage domain model.
- `app/models/query_log.py`: audit log for prompt/usage/status.

## 10. Always-online setup

### A) Railway (staging, 24/7)

Files already added for Railway:
- `Procfile` -> `web: bash scripts/run_prod.sh`
- `scripts/run_prod.sh` -> uses `PORT` automatically

Steps:
1. Push this project to GitHub.
2. In Railway create new project from repo.
3. Add Postgres and Redis plugins in Railway.
4. In app service add env vars:
   - `DATABASE_URL` (from Railway Postgres)
   - `REDIS_URL` (from Railway Redis)
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_WEBHOOK_SECRET`
   - `ADMIN_TOKEN`
   - `OPENAI_API_KEY`
   - `TELEGRAM_WEBHOOK_URL=https://<your-railway-domain>`
5. Deploy. After startup app sets webhook automatically to:
   - `https://<your-railway-domain>/telegram/webhook/<TELEGRAM_WEBHOOK_SECRET>`
6. Check:
   - `https://<your-railway-domain>/health`
   - `https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo`

### B) VPS (production, 24/7)

Use `systemd` with restart policy. Template added:
- `deploy/systemd/student-bot.service`

Quick install example (Ubuntu):

```bash
sudo mkdir -p /opt/student-bot
sudo chown -R $USER:$USER /opt/student-bot
git clone <your_repo_url> /opt/student-bot
cd /opt/student-bot
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp token.env.example token.env
# fill token.env with production values
```

Copy service file:

```bash
sudo cp deploy/systemd/student-bot.service /etc/systemd/system/student-bot.service
sudo systemctl daemon-reload
sudo systemctl enable student-bot
sudo systemctl start student-bot
sudo systemctl status student-bot
```

Logs:

```bash
sudo journalctl -u student-bot -f
```

Recommended on VPS:
- Nginx + HTTPS (Let's Encrypt)
- `TELEGRAM_WEBHOOK_URL=https://bot.yourdomain.com`
- managed/external Postgres + Redis (or Docker with volumes/backups)

## 11. Next recommended steps

1. Add Alembic migrations instead of `create_all`.
2. Add structured logging + Sentry.
3. Add background jobs (Celery/RQ) for heavy LLM tasks.
4. Add provider routing for OpenAI/Anthropic/Groq behind one interface.
5. Deploy staging on Railway with managed Postgres/Redis.
6. Deploy production on VPS with Docker + reverse proxy + HTTPS.
