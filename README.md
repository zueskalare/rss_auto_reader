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
- [Web Interface](#web-interface)
- [Project Structure](#project-structure)
- [API Interface](#api-interface)
- [Contributing](#contributing)

## Features
- **Polling**: Periodically fetch new entries from configured RSS/Atom feeds.
- **Persistence**: Deduplicates and stores articles in PostgreSQL.
- **Summarization**: Generates concise summaries using OpenAI.
- **Webhook Dispatch**: Posts summarized data to a configurable HTTP endpoint.
- **Dockerized**: Ready to run via Docker Compose for easy deployment.

## Prerequisites
- Python 3.9+
- PostgreSQL (or Docker via `docker-compose`)
- OpenAI API key

## Installation
```bash
git clone https://github.com/your-org/RSS_llm.git
cd RSS_llm
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r app/requirements.txt
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
# Ensure venv activated and env vars set
python -u app/main.py
```

## Docker Setup
Build and run both the database and worker with Docker Compose:
```bash
docker-compose up --build
```

The HTTP API will be exposed on the port configured by `API_PORT` (default 8000).

## Web Interface

A simple built-in web UI is available for managing RSS feeds and user interests. Once the service is running (locally or via Docker Compose), browse to:

- `/web/feeds` to add, view, and remove feeds.
- `/web/users` to add, view, and remove users and their interest filters.

## Project Structure
```
RSS_llm/
├── app/
│   ├── api/
│   │   └── views.py          # HTTP API & web UI routes
│   ├── config/
│   │   ├── feeds.yml         # RSS feed list & polling interval
│   │   └── users.yml         # User interests & webhooks
│   ├── db.py
│   ├── main.py
│   ├── models/
│   │   └── article.py
│   ├── requirements.txt
│   └── services/
│       ├── dispatcher.py     # Webhook dispatcher for summarized articles
│       └── summarize.py      # Summarization logic
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .dockerignore
└── README.md
```

## API Interface

The service exposes the following HTTP endpoints (default port configurable via `API_PORT`, default 8000):

### Feeds
- `GET /feeds`
  List configured RSS feeds and polling interval.
- `POST /feeds`
  Add a new feed. JSON body: `{ "name": "...", "url": "..." }`.
- `PUT /feeds/{name}`
  Update the URL of an existing feed. JSON body: `{ "url": "..." }`.
- `DELETE /feeds/{name}`
  Remove a feed by name.

### Articles
- `GET /articles`
  List stored articles. Optional query parameters:
  - `since` (ISO 8601 timestamp) — only articles updated at or after this time.
  - `status` (comma-separated `new`, `summarized`, `error`) — filter by status.
  - `limit` (integer) — max number of articles to return.

### Fetch
- `POST /fetch`
  Trigger an immediate fetch and summarization run. Optional JSON body: `{ "feeds": ["FeedName1", "..."] }`.

### Health
- `GET /health`
  Health check; returns `{ "status": "ok" }`.

## Contributing
Contributions, issues, and feature requests are welcome. Feel free to open a pull request!