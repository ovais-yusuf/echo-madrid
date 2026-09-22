from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Competition, Match, Season, Standing, Team

_MATCH_TEAM_LOAD = (
    selectinload(Match.home_team),
    selectinload(Match.away_team),
)


def list_teams(db: Session) -> list[Team]:
    return list(db.scalars(select(Team).order_by(Team.name)).all())


def get_team(db: Session, id: int) -> Team | None:
    return db.get(Team, id)


def get_team_matches(
    db: Session,
    team_id: int,
    limit: int = 10,
    status: str | None = None,
) -> list[Match]:
    stmt = (
        select(Match)
        .options(*_MATCH_TEAM_LOAD)
        .where(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))
        .order_by(Match.utc_date.desc())
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(Match.status == status)
    return list(db.scalars(stmt).all())


def list_competitions(db: Session) -> list[Competition]:
    return list(db.scalars(select(Competition).order_by(Competition.name)).all())


def get_match(db: Session, id: int) -> Match | None:
    return db.get(Match, id, options=_MATCH_TEAM_LOAD)


def find_team_by_name(db: Session, name: str) -> Team | None:
    needle = name.strip()
    if not needle:
        return None
    exact = db.scalar(
        select(Team).where(
            or_(
                func.lower(Team.name) == needle.lower(),
                func.lower(Team.short_name) == needle.lower(),
            )
        )
    )
    if exact is not None:
        return exact
    return db.scalar(
        select(Team)
        .where(
            or_(
                Team.name.ilike(f"%{needle}%"),
                Team.short_name.ilike(f"%{needle}%"),
            )
        )
        .order_by(Team.name)
        .limit(1)
    )


def get_standings(
    db: Session,
    limit: int | None = None,
    team_id: int | None = None,
) -> list[Standing]:
    latest_season_id = db.scalar(
        select(Season.id)
        .join(Standing)
        .order_by(Season.end_date.desc(), Season.id.desc())
        .limit(1)
    )
    stmt = (
        select(Standing)
        .options(selectinload(Standing.team))
        .order_by(Standing.position)
    )
    if latest_season_id is not None:
        stmt = stmt.where(Standing.season_id == latest_season_id)
    if team_id is not None:
        stmt = stmt.where(Standing.team_id == team_id)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def get_team_standing(db: Session, team_id: int) -> Standing | None:
    rows = get_standings(db, team_id=team_id, limit=1)
    return rows[0] if rows else None
