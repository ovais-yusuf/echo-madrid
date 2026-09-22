"""Ask Echo: natural-language answers grounded on local match data."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_openai_api_key
from app.queries import get_team_matches
from app.schemas import MatchRead, ToolCallRecord

REAL_MADRID_TEAM_ID = 2
DEFAULT_MATCH_LIMIT = 10
MAX_MATCH_LIMIT = 100
ALLOWED_STATUSES = frozenset({"SCHEDULED", "FINISHED"})
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are Ask Echo, a Real Madrid match assistant.

You may ONLY answer from the data returned by tools. Those tools read our
local database; they are the sole source of truth.

Rules:
- If the tool results do not contain the answer, say you do not have that data.
- Never fabricate scores, dates, opponents, venues, lineups, or any other stats.
- Never use prior football knowledge to fill gaps.
- If no tool was used or the rows are empty, say you do not have that data.
- Prefer concise, factual answers that cite dates, opponents, and scores only
  when those values appear in the tool result.
"""

GET_TEAM_MATCHES_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_team_matches",
        "description": (
            "Return Real Madrid's matches from the local database, most recent "
            "first. Each row includes utc_date, status, home_team, away_team, "
            "home_score, away_score, and matchday. "
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

TOOLS: list[dict[str, Any]] = [GET_TEAM_MATCHES_TOOL]


def _serialize_matches(matches: list[Any]) -> list[dict[str, Any]]:
    return [MatchRead.model_validate(match).model_dump(mode="json") for match in matches]


def parse_get_team_matches_args(raw_arguments: str) -> dict[str, Any]:
    """Parse model-supplied args. Team is never taken from the model."""
    try:
        parsed = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    limit = parsed.get("limit", DEFAULT_MATCH_LIMIT)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = DEFAULT_MATCH_LIMIT
    limit = max(1, min(limit, MAX_MATCH_LIMIT))

    status = parsed.get("status")
    if status is not None:
        status = str(status).upper()
        if status not in ALLOWED_STATUSES:
            status = None

    return {"limit": limit, "status": status}


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


def _tool_result_payload(name: str, db: Session, arguments: dict[str, Any]) -> Any:
    if name != "get_team_matches":
        return {"error": f"Unknown tool: {name}"}
    return execute_get_team_matches(db, arguments)


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
        return message.content or (
            "I do not have that data."
        ), tool_calls

    messages.append(message)
    for call in message.tool_calls:
        arguments = parse_get_team_matches_args(call.function.arguments)
        tool_calls.append(ToolCallRecord(name=call.function.name, arguments=arguments))
        payload = _tool_result_payload(call.function.name, db, arguments)
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
