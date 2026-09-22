from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamRef(BaseModel):
    """Nested team on match responses: id + name only."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str | None
    crest_url: str | None


class CompetitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None
    type: str | None


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    utc_date: datetime
    status: str
    home_team: TeamRef
    away_team: TeamRef
    home_score: int | None
    away_score: int | None
    matchday: int | None
