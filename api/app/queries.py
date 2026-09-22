from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Competition, Match, Team

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
