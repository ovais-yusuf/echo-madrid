from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from openai import OpenAIError
from sqlalchemy.orm import Session

from app.ask_echo import ask_echo
from app.database import get_db
from app.queries import (
    get_match as fetch_match,
    get_team as fetch_team,
    get_team_matches as fetch_team_matches,
    list_competitions as fetch_competitions,
    list_teams as fetch_teams,
)
from app.schemas import AskRequest, AskResponse, CompetitionRead, MatchRead, TeamRead

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Echo Madrid API")


@app.get("/", include_in_schema=False)
def ask_echo_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/teams", response_model=list[TeamRead])
def list_teams(db: Session = Depends(get_db)) -> list[TeamRead]:
    return fetch_teams(db)


@app.get("/teams/{id}", response_model=TeamRead)
def get_team(id: int, db: Session = Depends(get_db)) -> TeamRead:
    team = fetch_team(db, id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {id} not found")
    return team


@app.get("/teams/{id}/matches", response_model=list[MatchRead])
def get_team_matches(
    id: int,
    limit: int = Query(default=10, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[MatchRead]:
    if fetch_team(db, id) is None:
        raise HTTPException(status_code=404, detail=f"Team {id} not found")
    return fetch_team_matches(db, id, limit=limit, status=status)


@app.get("/competitions", response_model=list[CompetitionRead])
def list_competitions(db: Session = Depends(get_db)) -> list[CompetitionRead]:
    return fetch_competitions(db)


@app.get("/matches/{id}", response_model=MatchRead)
def get_match(id: int, db: Session = Depends(get_db)) -> MatchRead:
    match = fetch_match(db, id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Match {id} not found")
    return match


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    try:
        answer, tool_calls = ask_echo(db, body.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail="Ask Echo failed to reach OpenAI") from exc
    return AskResponse(answer=answer, tool_calls=tool_calls)
