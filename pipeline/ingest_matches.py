"""Ingest Real Madrid matches from football-data.org into Postgres."""

from __future__ import annotations

import logging
import sys
import time
from collections import deque
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_football_data_api_key
from app.database import SessionLocal
from app.models import (
    Competition,
    IngestionRun,
    Match,
    Season,
    Team,
    utc_now,
)

logger = logging.getLogger(__name__)

SOURCE = "football-data.org"
ENTITY_TYPE = "match"
REAL_MADRID_TEAM_ID = 86
API_BASE_URL = "https://api.football-data.org/v4"

# football-data.org free tier: 10 requests per minute.
FREE_TIER_MAX_REQUESTS = 10
FREE_TIER_WINDOW_SECONDS = 60.0


class RateLimiter:
    """Sliding-window limiter so later endpoints cannot exceed the free tier."""

    def __init__(
        self,
        max_requests: int = FREE_TIER_MAX_REQUESTS,
        window_seconds: float = FREE_TIER_WINDOW_SECONDS,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: deque[float] = deque()

    def wait(self) -> None:
        now = time.monotonic()
        self._evict(now)
        if len(self._hits) >= self.max_requests:
            sleep_for = self.window_seconds - (now - self._hits[0])
            if sleep_for > 0:
                logger.info("Rate limit reached; sleeping %.1fs", sleep_for)
                time.sleep(sleep_for)
            self._evict(time.monotonic())
        self._hits.append(time.monotonic())

    def _evict(self, now: float) -> None:
        while self._hits and now - self._hits[0] >= self.window_seconds:
            self._hits.popleft()


class FootballDataClient:
    def __init__(self, api_key: str) -> None:
        self._limiter = RateLimiter()
        self._client = httpx.Client(
            base_url=API_BASE_URL,
            headers={"X-Auth-Token": api_key},
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FootballDataClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        self._limiter.wait()
        response = self._client.get(path, params=params or None)
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", FREE_TIER_WINDOW_SECONDS))
            logger.warning("Received 429; retrying after %.0fs", retry_after)
            time.sleep(retry_after)
            self._limiter.wait()
            response = self._client.get(path, params=params or None)
        response.raise_for_status()
        return response.json()

    def get_team_matches(self, team_id: int = REAL_MADRID_TEAM_ID) -> dict[str, Any]:
        return self.get(f"/teams/{team_id}/matches")

    def get_competition_standings(self, competition_code: str = "PD") -> dict[str, Any]:
        return self.get(f"/competitions/{competition_code}/standings")


def parse_utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def year_label(start: date, end: date) -> str:
    if start.year == end.year:
        return str(start.year)
    return f"{start.year}/{end.year}"


def upsert_by_external_id(
    session: Session,
    model: type,
    external_id: int,
    cache: dict[int, Any],
    **fields: Any,
) -> Any:
    instance = cache.get(external_id)
    if instance is None:
        instance = session.scalar(
            select(model).where(model.external_id == external_id)
        )
    if instance is None:
        instance = model(external_id=external_id, **fields)
        session.add(instance)
        session.flush()
    else:
        for key, value in fields.items():
            setattr(instance, key, value)
    cache[external_id] = instance
    return instance


def upsert_competition(
    session: Session, payload: dict[str, Any], cache: dict[int, Competition]
) -> Competition:
    return upsert_by_external_id(
        session,
        Competition,
        payload["id"],
        cache,
        name=payload["name"],
        code=payload.get("code"),
        type=payload.get("type"),
    )


def upsert_season(
    session: Session,
    payload: dict[str, Any],
    competition_id: int,
    cache: dict[int, Season],
) -> Season:
    start = date.fromisoformat(payload["startDate"])
    end = date.fromisoformat(payload["endDate"])
    return upsert_by_external_id(
        session,
        Season,
        payload["id"],
        cache,
        competition_id=competition_id,
        year_label=year_label(start, end),
        start_date=start,
        end_date=end,
    )


def upsert_team(
    session: Session, payload: dict[str, Any], cache: dict[int, Team]
) -> Team:
    return upsert_by_external_id(
        session,
        Team,
        payload["id"],
        cache,
        name=payload["name"],
        short_name=payload.get("shortName"),
        crest_url=payload.get("crest"),
    )


def upsert_match(
    session: Session,
    payload: dict[str, Any],
    competition_id: int,
    season_id: int,
    home_team_id: int,
    away_team_id: int,
    cache: dict[int, Match],
) -> Match:
    full_time = (payload.get("score") or {}).get("fullTime") or {}
    return upsert_by_external_id(
        session,
        Match,
        payload["id"],
        cache,
        competition_id=competition_id,
        season_id=season_id,
        utc_date=parse_utc_datetime(payload["utcDate"]),
        status=payload["status"],
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_score=full_time.get("home"),
        away_score=full_time.get("away"),
        matchday=payload.get("matchday"),
    )


def ingest_matches(session: Session, matches: list[dict[str, Any]]) -> int:
    competitions: dict[int, Competition] = {}
    seasons: dict[int, Season] = {}
    teams: dict[int, Team] = {}
    stored_matches: dict[int, Match] = {}

    for raw in matches:
        competition = upsert_competition(session, raw["competition"], competitions)
        season = upsert_season(session, raw["season"], competition.id, seasons)
        home_team = upsert_team(session, raw["homeTeam"], teams)
        away_team = upsert_team(session, raw["awayTeam"], teams)
        upsert_match(
            session,
            raw,
            competition.id,
            season.id,
            home_team.id,
            away_team.id,
            stored_matches,
        )
    return len(matches)


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
            payload = client.get_team_matches(REAL_MADRID_TEAM_ID)
        matches = payload.get("matches") or []
        count = ingest_matches(session, matches)
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
            f"Ingestion complete: {run.records_upserted} matches upserted "
            f"(status={run.status})"
        )
        return 0
    print(
        f"Ingestion failed: {run.error} "
        f"(status={run.status}, matches upserted={run.records_upserted})"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
