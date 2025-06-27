# RSS Feed Summarizer

> **RSS_llm** is a background worker that polls RSS/Atom feeds, stores entries in PostgreSQL, summarizes new articles using OpenAI, and dispatches results to external systems via a webhook.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [feeds.yml](#feedsyml)
  - [Environment Variables](#environment-variables)
- [Database Initialization](#database-initialization)
- [Running Locally](#running-locally)
- [Docker Setup](#docker-setup)
- [Project Structure](#project-structure)
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
Customize `app/feeds.yml` with your feed list and default polling interval:
```yaml
feeds:
  - name: ExampleFeed
    url: https://example.com/rss
interval: 300
```

### Environment Variables
Create a `.env` file or export these variables:
```dotenv
# OpenAI credentials
OPENAI_API_KEY=sk-...

# Webhook for summaries
WEBHOOK_URL=https://your.service/webhook

# (Optional) Database and polling settings
DATABASE_URL=postgresql://user:pass@host:5432/dbname
POLL_INTERVAL=300
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

## Project Structure
```
RSS_llm/
├── app/
│   ├── db.py
│   ├── models.py
│   ├── main.py
│   └── feeds.yml
├── Dockerfile
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Contributing
Contributions, issues, and feature requests are welcome. Feel free to open a pull request!