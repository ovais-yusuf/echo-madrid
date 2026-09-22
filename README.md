# Echo Madrid

A football data platform with a natural-language query interface. Ask questions
about Real Madrid in plain English and get answers grounded in real data — never
hallucinated.

**Live demo:** https://echo-madrid-production.up.railway.app

## What it does

"Ask Echo" lets you ask questions like *"Where is Real Madrid in the La Liga
table?"* or *"What was their last result?"* and returns answers computed from a
live database of matches and standings. The language model never invents
statistics — it can only answer from data returned by real database queries, and
says so when the data isn't there.

## Architecture

Echo Madrid is a four-layer system, not a chatbot:

1. **Ingestion pipeline** (`/pipeline`) — scheduled, idempotent jobs that pull
   match and standings data from the football-data.org API and upsert it into
   Postgres. Re-running never creates duplicates (upserts keyed on external IDs
   and composite keys), and every run is logged to an `ingestion_run` table.
2. **Database** — a normalized PostgreSQL schema (teams, matches, standings,
   seasons, competitions), evolved through versioned Alembic migrations.
3. **API** (`/api`) — a typed FastAPI service exposing the data. All query logic
   lives in a shared data-access layer reused by both the REST endpoints and the
   AI layer.
4. **Ask Echo** — a grounded natural-language interface built on OpenAI tool
   calling. The model translates a question into a call against the same query
   functions the API uses, the app executes the real query, and the model
   phrases an answer from the returned rows only.

### Grounding design

The core design principle: the LLM is a translator, not a knowledge source. It
selects which query function to call and with what arguments; the application
executes the query and returns real rows; the model answers only from those rows.
This means Ask Echo cannot fabricate a scoreline or a league position — every
number traces to a database row, and missing data yields "I don't have that"
rather than an invention.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **AI:** OpenAI API (function/tool calling)
- **Infra:** Docker, Docker Compose, deployed on Railway
- **Data source:** football-data.org API

## Running locally

```bash
# Start Postgres
docker compose up -d

# Set up the API
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, OPENAI_API_KEY, FOOTBALL_DATA_API_KEY
alembic upgrade head

# Ingest data
cd ..
python -m pipeline.ingest_matches
python -m pipeline.ingest_standings

# Run the app
cd api
uvicorn app.main:app --reload
# open http://localhost:8000
```

## Notes

Echo Madrid is a solo-built engineering project. It is an unofficial fan project
and is not affiliated with Real Madrid CF.