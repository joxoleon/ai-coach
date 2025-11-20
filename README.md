# Adaptive Daily Task Scheduler

Minimal FastAPI + HTMX app that rotates daily tasks from plaintext configs, augments with OpenAI selection, and serves a mobile-friendly dashboard.

## Features
- Loads human-readable YAML task groups from `configs/` automatically.
- FastAPI + SQLite + SQLAlchemy; APScheduler runs a midnight job (00:05 local) to build the plan.
- Optional OpenAI (gpt-4.1 / gpt-4.1-mini) selector with validation and deterministic fallback.
- HTMX + Tailwind UI to view, mark done, and see reasons; lightweight admin refresh/history.
- Docker Compose with Nginx reverse proxy for self-hosting.

## Quickstart (local)
1. Requirements: Python 3.11, Docker + Docker Compose (for container run).
2. Copy your OpenAI key into environment: `export OPENAI_API_KEY=sk-...` (or set `USE_AI_SELECTOR=false` to force fallback).
3. Run directly (development):
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
   Visit http://localhost:8000.
4. Or with Docker Compose:
   ```bash
   docker-compose up --build
   ```
   Nginx will listen on port 80 and proxy to the app.

## Configuration
- `configs/*.yaml` are auto-discovered; format:
  ```yaml
  group: "DSA Fundamentals"
  items:
    - name: "Binary Search"
      importance: 5
      tags: [optional]
      url: [optional]
  ```
- Environment:
  - `OPENAI_API_KEY`: enables AI selector when set.
  - `USE_AI_SELECTOR`: set to `false` to force fallback scoring.
  - `TZ`: timezone for the scheduler (defaults to `UTC`).
- Database: SQLite stored at `db.sqlite` (mounted in Docker for persistence).

## API
- `GET /today` – tasks grouped by category for today.
- `POST /done` – mark a task completed `{name, group, difficulty?, task_id?}`.
- `POST /feedback` – store difficulty rating without marking done.
- `GET /history?days=N` – recent history entries.
- `POST /refresh` – regenerate today manually (exposed on `/admin` page).

## Scheduler
- APScheduler job runs daily at 00:05 local time, loading configs, summarizing recent history, calling AI (or fallback), and persisting to `today_tasks`.
- On startup, if no tasks exist for today, generation runs immediately.

## Deployment (Hetzner VPS quick path)
1. Provision Ubuntu 22.04 VPS, point DNS to the server IP.
2. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER # re-login
   ```
3. Clone the repo:
   ```bash
   git clone <this-repo> ai-coach && cd ai-coach
   ```
4. Set environment values in your shell or a `.env` file (Compose will pick them up):
   ```bash
   echo "OPENAI_API_KEY=sk-..." >> .env
   echo "USE_AI_SELECTOR=true" >> .env
   echo "TZ=Europe/Berlin" >> .env
   ```
5. Start services:
   ```bash
   docker-compose up -d --build
   ```
6. Confirm: `curl http://<server-ip>/today` or visit `http://<server-ip>/`.
7. Optional: set up a basic firewall (allow 22/80) and enable automatic updates.

## Project Layout
```
app/
  main.py
  api/ (task + admin routes)
  core/ (config, db, scheduler, AI selector)
  models/ (SQLAlchemy models)
  services/ (config loader, fallback selector)
  templates/ (HTMX pages)
configs/ (YAML task groups)
docker-compose.yml
Dockerfile
nginx.conf
```

## Notes
- If OpenAI is unavailable or fails validation, the deterministic fallback selector runs (importance, recency, streak, difficulty bias).
- Tailwind is pulled via CDN for simplicity; adjust `app/templates/` or add compiled assets if desired.
- The system is intentionally lightweight—extend tables, prompts, or UI without changing the core flow.
