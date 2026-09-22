from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Competition(Base):
    __tablename__ = "competition"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_competition_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(20))
    type: Mapped[str | None] = mapped_column(String(50))

    seasons: Mapped[list[Season]] = relationship(back_populates="competition")
    matches: Mapped[list[Match]] = relationship(back_populates="competition")


class Season(Base):
    __tablename__ = "season"
    __table_args__ = (UniqueConstraint("external_id", name="uq_season_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competition.id"), nullable=False
    )
    year_label: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    competition: Mapped[Competition] = relationship(back_populates="seasons")
    matches: Mapped[list[Match]] = relationship(back_populates="season")
    standings: Mapped[list[Standing]] = relationship(back_populates="season")
    squad_memberships: Mapped[list[SquadMembership]] = relationship(
        back_populates="season"
    )


class Team(Base):
    __tablename__ = "team"
    __table_args__ = (UniqueConstraint("external_id", name="uq_team_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    crest_url: Mapped[str | None] = mapped_column(String(512))

    home_matches: Mapped[list[Match]] = relationship(
        back_populates="home_team", foreign_keys="Match.home_team_id"
    )
    away_matches: Mapped[list[Match]] = relationship(
        back_populates="away_team", foreign_keys="Match.away_team_id"
    )
    standings: Mapped[list[Standing]] = relationship(back_populates="team")
    squad_memberships: Mapped[list[SquadMembership]] = relationship(
        back_populates="team"
    )


class Player(Base):
    __tablename__ = "player"
    __table_args__ = (UniqueConstraint("external_id", name="uq_player_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(50))
    nationality: Mapped[str | None] = mapped_column(String(100))
    dob: Mapped[date | None] = mapped_column(Date)

    squad_memberships: Mapped[list[SquadMembership]] = relationship(
        back_populates="player"
    )


class SquadMembership(Base):
    __tablename__ = "squad_membership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id"), nullable=False)
    shirt_number: Mapped[int | None] = mapped_column(Integer)

    team: Mapped[Team] = relationship(back_populates="squad_memberships")
    player: Mapped[Player] = relationship(back_populates="squad_memberships")
    season: Mapped[Season] = relationship(back_populates="squad_memberships")


class Match(Base):
    __tablename__ = "match"
    __table_args__ = (UniqueConstraint("external_id", name="uq_match_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competition.id"), nullable=False
    )
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id"), nullable=False)
    utc_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    matchday: Mapped[int | None] = mapped_column(Integer)

    competition: Mapped[Competition] = relationship(back_populates="matches")
    season: Mapped[Season] = relationship(back_populates="matches")
    home_team: Mapped[Team] = relationship(
        back_populates="home_matches", foreign_keys=[home_team_id]
    )
    away_team: Mapped[Team] = relationship(
        back_populates="away_matches", foreign_keys=[away_team_id]
    )


class Standing(Base):
    __tablename__ = "standing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    played: Mapped[int] = mapped_column(Integer, nullable=False)
    won: Mapped[int] = mapped_column(Integer, nullable=False)
    drawn: Mapped[int] = mapped_column(Integer, nullable=False)
    lost: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    goals_for: Mapped[int] = mapped_column(Integer, nullable=False)
    goals_against: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    season: Mapped[Season] = relationship(back_populates="standings")
    team: Mapped[Team] = relationship(back_populates="standings")


class IngestionRun(Base):
    __tablename__ = "ingestion_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    records_upserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
