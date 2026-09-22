from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class StandingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    team: TeamRef
    played: int
    won: int
    drawn: int
    lost: int
    points: int
    goals_for: int
    goals_against: int


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]


class AskResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallRecord]
