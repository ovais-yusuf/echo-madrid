"""Ask Echo: natural-language answers grounded on local match and standings data."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_openai_api_key
from app.queries import find_team_by_name, get_standings, get_team_matches
from app.schemas import MatchRead, StandingRead, ToolCallRecord

REAL_MADRID_TEAM_ID = 2
DEFAULT_MATCH_LIMIT = 10
MAX_MATCH_LIMIT = 100
MAX_STANDINGS_LIMIT = 20
ALLOWED_STATUSES = frozenset({"SCHEDULED", "FINISHED"})
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are Ask Echo, a Real Madrid and La Liga assistant.

You may ONLY answer from the data returned by tools. Those tools read our
local database; they are the sole source of truth.

Available tools:
- get_team_matches: Real Madrid fixtures and results (dates, opponents, scores).
- get_standings: the current La Liga table (position, points, played, W/D/L,
  goals, team names). Use this for league position, points, or table questions.
  Pass team_name to filter to one club; omit it for the full table.

Pick the tool that matches the question. You may call more than one if needed.

Rules:
- If the tool results do not contain the answer, say you do not have that data.
- Never fabricate scores, dates, opponents, positions, points, or any other stats.
- Never use prior football knowledge to fill gaps.
- If no tool was used or the rows are empty, say you do not have that data.
- Prefer concise, factual answers that cite only values present in the tool result.
"""

GET_TEAM_MATCHES_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_team_matches",
        "description": (
            "Return Real Madrid's matches from the local database, most recent "
            "first. Each row includes utc_date, status, home_team, away_team, "
            "home_score, away_score, and matchday. "
            "Use this for fixtures, results, or recent form. "
            "Optional limit (default 10). Optional status filter: SCHEDULED "
            "for upcoming fixtures or FINISHED for completed results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum number of matches to return. Defaults to 10."
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": ["SCHEDULED", "FINISHED"],
                    "description": (
                        "If set, only return matches with this status."
                    ),
                },
            },
        },
    },
}

GET_STANDINGS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_standings",
        "description": (
            "Return the current La Liga table from the local database, ordered "
            "by position. Each row includes team name, position, played, won, "
            "drawn, lost, points, goals_for, and goals_against. "
            "Use this for league position, points, or standings questions. "
            "Optional team_name filters to that club's row (e.g. "
            "'Real Madrid'). Optional limit returns the top N rows."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum number of table rows to return, from the top. "
                        "Omit for the full table."
                    ),
                },
                "team_name": {
                    "type": "string",
                    "description": (
                        "If set, return only that team's standings row. "
                        "Match on club name (for example 'Real Madrid' or "
                        "'Barcelona'). Do not pass a numeric team id."
                    ),
                },
            },
        },
    },
}

TOOLS: list[dict[str, Any]] = [GET_TEAM_MATCHES_TOOL, GET_STANDINGS_TOOL]


def _parse_json_object(raw_arguments: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _serialize_matches(matches: list[Any]) -> list[dict[str, Any]]:
    return [MatchRead.model_validate(match).model_dump(mode="json") for match in matches]


def _serialize_standings(rows: list[Any]) -> list[dict[str, Any]]:
    return [StandingRead.model_validate(row).model_dump(mode="json") for row in rows]


def parse_get_team_matches_args(raw_arguments: str) -> dict[str, Any]:
    """Parse model-supplied args. Team is never taken from the model."""
    parsed = _parse_json_object(raw_arguments)
    limit = _clamp_int(
        parsed.get("limit", DEFAULT_MATCH_LIMIT),
        DEFAULT_MATCH_LIMIT,
        1,
        MAX_MATCH_LIMIT,
    )
    status = parsed.get("status")
    if status is not None:
        status = str(status).upper()
        if status not in ALLOWED_STATUSES:
            status = None
    return {"limit": limit, "status": status}


def parse_get_standings_args(raw_arguments: str) -> dict[str, Any]:
    """Parse model-supplied args. Team ids from the model are ignored."""
    parsed = _parse_json_object(raw_arguments)
    limit = parsed.get("limit")
    if limit is not None:
        limit = _clamp_int(limit, MAX_STANDINGS_LIMIT, 1, MAX_STANDINGS_LIMIT)
    team_name = parsed.get("team_name")
    if team_name is not None:
        team_name = str(team_name).strip() or None
    return {"limit": limit, "team_name": team_name}


def execute_get_team_matches(
    db: Session, arguments: dict[str, Any]
) -> list[dict[str, Any]]:
    matches = get_team_matches(
        db,
        REAL_MADRID_TEAM_ID,
        limit=arguments.get("limit", DEFAULT_MATCH_LIMIT),
        status=arguments.get("status"),
    )
    return _serialize_matches(matches)


def execute_get_standings(
    db: Session, arguments: dict[str, Any]
) -> list[dict[str, Any]]:
    team_id = None
    team_name = arguments.get("team_name")
    if team_name:
        team = find_team_by_name(db, team_name)
        if team is None:
            return []
        team_id = team.id
    rows = get_standings(
        db,
        limit=arguments.get("limit"),
        team_id=team_id,
    )
    return _serialize_standings(rows)


_TOOL_HANDLERS: dict[
    str,
    tuple[Callable[[str], dict[str, Any]], Callable[[Session, dict[str, Any]], Any]],
] = {
    "get_team_matches": (parse_get_team_matches_args, execute_get_team_matches),
    "get_standings": (parse_get_standings_args, execute_get_standings),
}


def ask_echo(db: Session, question: str) -> tuple[str, list[ToolCallRecord]]:
    client = OpenAI(api_key=get_openai_api_key())
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    tool_calls: list[ToolCallRecord] = []

    first = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )
    message = first.choices[0].message

    if not message.tool_calls:
        return message.content or "I do not have that data.", tool_calls

    messages.append(message)
    for call in message.tool_calls:
        handler = _TOOL_HANDLERS.get(call.function.name)
        if handler is None:
            arguments: dict[str, Any] = {}
            payload: Any = {"error": f"Unknown tool: {call.function.name}"}
        else:
            parse, execute = handler
            arguments = parse(call.function.arguments)
            payload = execute(db, arguments)
        tool_calls.append(ToolCallRecord(name=call.function.name, arguments=arguments))
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(payload),
            }
        )

    final = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    answer = final.choices[0].message.content or "I do not have that data."
    return answer, tool_calls
