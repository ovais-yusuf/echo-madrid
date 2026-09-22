"""Ingest the current La Liga table from football-data.org into Postgres."""

from __future__ import annotations

import logging
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_football_data_api_key
from app.database import SessionLocal
from app.models import Competition, IngestionRun, Season, Standing, Team, utc_now
from pipeline.ingest_matches import (
    FootballDataClient,
    upsert_competition,
    upsert_season,
    upsert_team,
)

logger = logging.getLogger(__name__)

SOURCE = "football-data.org"
ENTITY_TYPE = "standing"
LA_LIGA_CODE = "PD"


def upsert_standing(
    session: Session,
    season_id: int,
    team_id: int,
    row: dict[str, Any],
) -> Standing:
    existing = session.scalar(
        select(Standing).where(
            Standing.season_id == season_id,
            Standing.team_id == team_id,
        )
    )
    fields = {
        "position": row["position"],
        "played": row["playedGames"],
        "won": row["won"],
        "drawn": row["draw"],
        "lost": row["lost"],
        "points": row["points"],
        "goals_for": row["goalsFor"],
        "goals_against": row["goalsAgainst"],
        "updated_at": utc_now(),
    }
    if existing is None:
        standing = Standing(season_id=season_id, team_id=team_id, **fields)
        session.add(standing)
        session.flush()
        return standing
    for key, value in fields.items():
        setattr(existing, key, value)
    return existing


def _total_tables(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for standing in payload.get("standings") or []:
        if standing.get("type") == "TOTAL":
            tables.extend(standing.get("table") or [])
    return tables


def ingest_standings(session: Session, payload: dict[str, Any]) -> int:
    competitions: dict[int, Competition] = {}
    seasons: dict[int, Season] = {}
    teams: dict[int, Team] = {}

    competition = upsert_competition(session, payload["competition"], competitions)
    season = upsert_season(session, payload["season"], competition.id, seasons)

    rows = _total_tables(payload)
    if not rows:
        raise RuntimeError("Standings payload had no TOTAL table")

    for row in rows:
        team = upsert_team(session, row["team"], teams)
        upsert_standing(session, season.id, team.id, row)
    return len(rows)


def _mark_failed(session: Session, run_id: int, exc: BaseException) -> None:
    session.rollback()
    run = session.get(IngestionRun, run_id)
    if run is None:
        return
    run.status = "failed"
    run.finished_at = utc_now()
    run.error = f"{type(exc).__name__}: {exc}"
    session.commit()


def run_ingestion() -> IngestionRun:
    session = SessionLocal()
    run = IngestionRun(
        source=SOURCE,
        entity_type=ENTITY_TYPE,
        started_at=utc_now(),
        status="running",
        records_upserted=0,
    )
    session.add(run)
    session.commit()
    run_id = run.id

    try:
        api_key = get_football_data_api_key()
        with FootballDataClient(api_key) as client:
            payload = client.get_competition_standings(LA_LIGA_CODE)
        count = ingest_standings(session, payload)
        run.status = "success"
        run.finished_at = utc_now()
        run.records_upserted = count
        session.commit()
        session.refresh(run)
        session.expunge(run)
        return run
    except Exception as exc:
        logger.exception("Ingestion failed")
        _mark_failed(session, run_id, exc)
        run = session.get(IngestionRun, run_id)
        if run is None:
            raise
        session.expunge(run)
        return run
    finally:
        session.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run = run_ingestion()
    if run.status == "success":
        print(
            f"Ingestion complete: {run.records_upserted} standings upserted "
            f"(status={run.status})"
        )
        return 0
    print(
        f"Ingestion failed: {run.error} "
        f"(status={run.status}, standings upserted={run.records_upserted})"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
