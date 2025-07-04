# RSS Feed Summarizer

> **RSS_llm** is a background worker that polls RSS/Atom feeds, stores entries in PostgreSQL, summarizes new articles using OpenAI, and dispatches results to external systems via a webhook.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [feeds.yml](#feedsyml)
  - [users.yml](#usersyml)
  - [Environment Variables](#environment-variables)
- [Database Initialization](#database-initialization)
- [Running Locally](#running-locally)
- [Docker Setup](#docker-setup)
- [Project Structure](#project-structure)
- [API Interface](#api-interface)
- [Contributing](#contributing)

## Features
- **Polling**: Periodically fetch new entries from configured RSS/Atom feeds.
- **Persistence**: Deduplicates and stores articles in PostgreSQL.
- **Summarization**: Generates concise summaries using OpenAI.
- **Webhook Dispatch**: Posts summarized data to a configurable HTTP endpoint.
- **ASGI & Web UI**: Serves the FastAPI backend via Uvicorn and the Gradio-based frontend.
- **Async Fetch Loop**: Executes the polling logic to fetch new feed entries asynchronously.
- **Async Summarization Loop**: Summarizes newly fetched articles asynchronously in the background.
- **Dockerized**: Ready to run via Docker Compose for easy deployment.

## Prerequisites
- Python 3.12+
- PostgreSQL (or Docker via `docker-compose`)
- OpenAI API key

## Installation
```bash
git clone https://github.com/your-org/RSS_llm.git
cd RSS_llm
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration

### feeds.yml
Customize `app/config/feeds.yml` with your feed list and default polling interval:
```yaml
feeds:
  - name: ExampleFeed
    url: https://example.com/rss
interval: 300
```

### users.yml
Customize `app/config/users.yml` to configure user interests and their target webhooks:
```yaml
users:
  - username: alice
    webhook: https://your.webhook/for/alice
    interests:
      - "AI"
      - "OpenAI"
  - username: bob
    webhook: https://bob.webhook/notify
    interests:
      - "cloud"
      - "python"
```

### llm.yml
Configure the default LLM model and parameters used for summarization and daily plugins:
```yaml
model_name: gpt-4.1
model_temperature: 0.5
model_max_tokens: 4096
openai_api_base: ""
```

### Environment Variables
Copy `.env.example` to `.env` and update the values, or export these variables manually.

```dotenv
# OpenAI API key for summarization
OPENAI_API_KEY=your_openai_api_key

# Webhook URL for dispatching summaries
WEBHOOK_URL=https://your.webhook.endpoint

# PostgreSQL settings (used by Docker Compose)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=rss

# Polling interval in seconds
POLL_INTERVAL=300
# Dispatch interval in seconds (how often to send AI summaries; default: 3600)
DISPATCH_INTERVAL=3600
# Plugin interval in seconds (how often to run custom plugins; default: 86400)
PLUGIN_INTERVAL=86400
# Plugin scheduling: per-plugin override of running method
# Plugins are listed in `backend/app/plugins/__init__.py` via the `__all__` list.
# Each plugin sets scheduling fields on its Plugin subclass:
# - `schedule_type`: "interval" or "daily".
# - `schedule_interval`: seconds between runs for interval mode (fallback to PLUGIN_INTERVAL if None).
# - `schedule_time`: "HH:MM" local time for daily mode.
# Summarization interval in seconds (how often to summarize fetched articles; default: same as POLL_INTERVAL)
SUMMARIZE_INTERVAL=300
# HTTP API port
API_PORT=8000

# Summarization model (for OpenAI-compatible or self-hosted endpoints)
MODEL_NAME=gpt-4.1
MODEL_TEMPERATURE=0.5
MODEL_MAX_TOKENS=150
# Optional: override base URL for self-hosted OpenAI-compatible API
OPENAI_API_BASE=
```

## Database Initialization
The service auto-creates tables on startup. To manually initialize:
```bash
python -c "from app.db import init_db; init_db()"
```

## Running Locally
```bash
# Ensure venv activated and environment variables set (including UI_PORT for Gradio UI)
# Launch the backend API server:
uvicorn backend.main:app --reload --host 127.0.0.1 --port ${API_PORT:-8000}
# In a separate shell (with same env), launch the Gradio frontend:
python frontend/ui_main.py
# The API will be at http://127.0.0.1:${API_PORT:-8000}/api
# The Gradio Admin UI will be at http://127.0.0.1:${UI_PORT:-7860}/
```

## Docker Setup
With Docker Compose the backend and frontend will each start in their own container. Build and run the database, API, and Gradio UI:
```bash
docker-compose up --build
```

**Note:** The Postgres container initializes its data directory only on first startup. If you change the `POSTGRES_DB` (or other credentials) after an initial run, the existing volume will prevent re-initialization and your new database will not be created. To force a fresh database initialization, remove the volume and restart:
```bash
docker-compose down -v
docker-compose up --build
```
Or manually create the new database in the running container:
```bash
docker-compose exec db psql -U $POSTGRES_USER -c "CREATE DATABASE $POSTGRES_DB;"
```

The HTTP API will be exposed on `API_PORT` (default 8000) under `/api`, and the Gradio UI will be exposed on `UI_PORT` (default 7860).

## Gradio Admin UI

The Gradio-based admin interface is available for viewing articles, managing feeds, and configuring user webhooks.
It starts automatically on application startup and listens on port configured by `UI_PORT` (default 7860).

Browse to `http://localhost:${UI_PORT:-7860}/` to access the Gradio Admin UI.

### LLM Settings
Use the Admin UI to view and modify the LLM configuration for summarization (model name, temperature, max tokens, and OpenAI API base URL).  These settings apply to both on-demand summaries and the daily summary plugin.

## Project Structure
```text
RSS_llm/
├── backend/                  # FastAPI backend service and scheduled plugins
│   ├── Dockerfile
│   └── app/                  # backend application code
│       └── plugins/          # custom scheduled plugins (see below)
├── frontend/                 # Gradio frontend service
│   ├── Dockerfile
│   └── app/                  # frontend application code (UI layer)
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── .dockerignore
└── README.md
```

## Plugins

Custom scheduled plugins live under `backend/app/plugins`.  Each plugin must expose a `plugin` instance of a `Plugin` subclass (from `base.py`) and be listed in the `__all__` array in `backend/app/plugins/__init__.py`:

```python
from .daily_summary import plugin as daily_summary

__all__ = [
    "daily_summary",
]
```

The `Plugin` base model provides built-in scheduling fields:

| Field              | Type    | Description                                                    |
|--------------------|---------|----------------------------------------------------------------|
| `schedule_type`    | str     | `"interval"` or `"daily"`                                   |
| `schedule_interval`| int     | Seconds between runs when `schedule_type="interval"`         |
| `schedule_time`    | str     | `"HH:MM"` local time when `schedule_type="daily"`          |

If `schedule_interval` is `null`, the loop falls back to the `PLUGIN_INTERVAL` env var (default `86400`s).  If `schedule_time` is unset or malformed, it defaults to `00:00`.

Example `DailySummaryPlugin` in `daily_summary.py`:

```python
class DailySummaryPlugin(Plugin):
    @property
    def name(self) -> str:
        return "daily_summary"

    # run once per day at 08:00 local time
    schedule_type     = "daily"
    schedule_time     = "08:00"
    schedule_interval = None

    def run(self, session):
        # plugin logic here...
        ...

plugin = DailySummaryPlugin()
```

## API Interface

# API Interface
The service runs as an ASGI application (Uvicorn + FastAPI backend). It exposes the following HTTP endpoints under the `/api` prefix (default port configurable via `API_PORT`, default 8000):

### Feeds
- `GET /api/feeds`
  List configured RSS feeds.
- `POST /api/feeds`
  Add a new feed. JSON body: `{ "name": "...", "url": "..." }`.
- `PUT /api/feeds/{name}`
  Update the URL of an existing feed. JSON body: `{ "url": "..." }`.
- `DELETE /api/feeds/{name}`
  Remove a feed by name.

### Articles
- `GET /api/articles`
  List stored articles. Optional query parameters:
  - `since` (ISO 8601 timestamp) — only articles updated at or after this time.
  - `status` (comma-separated `new`, `summarized`, `error`) — filter by status.
  - `limit` (integer) — max number of articles to return.

### Fetch
- `POST /api/fetch`
  Trigger an immediate fetch and summarization run. Optional JSON body: `{ "feeds": ["FeedName1", "..."] }`.

### Health
- `GET /api/health`
  Health check; returns `{ "status": "ok" }`.

## Contributing
Contributions, issues, and feature requests are welcome. Feel free to open a pull request!