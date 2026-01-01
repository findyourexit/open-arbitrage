"""HTTP adapter for the Open Arbitrage engine (FastAPI)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .engine import (
    AdvanceDay,
    Buy,
    RepayLoan,
    Rules,
    Sell,
    Travel,
    apply_command,
    create_default_state,
    state_to_dict,
)
from .engine.core import Command

app = FastAPI(title="Open Arbitrage API", version="0.1.0")


class ResetPayload(BaseModel):
    seed: int | None = None
    travel_cost: float | None = None
    win_net_worth: float | None = None
    max_days: int | None = None


class CommandPayload(BaseModel):
    type: str = Field(..., examples=["buy", "sell", "travel", "advance_day", "repay"])
    args: dict[str, Any] = Field(default_factory=dict)


_state = create_default_state()
_event_log_path_env = os.environ.get("OPEN_ARBITRAGE_EVENT_LOG_PATH")
_event_log_path: Path | None = Path(_event_log_path_env) if _event_log_path_env else None


def _reset_state(payload: ResetPayload) -> None:
    rules = Rules()
    if payload.travel_cost is not None:
        rules.travel_cost = payload.travel_cost
    if payload.win_net_worth is not None:
        rules.win_net_worth = payload.win_net_worth
    if payload.max_days is not None:
        rules.max_days = payload.max_days

    global _state
    _state = create_default_state(seed=payload.seed, rules=rules)


@app.get("/state")
def get_state() -> dict[str, Any]:
    return state_to_dict(_state)


@app.post("/reset")
def reset(payload: ResetPayload) -> dict[str, Any]:
    _reset_state(payload)
    return state_to_dict(_state)


@app.post("/command")
def post_command(payload: CommandPayload) -> dict[str, Any]:
    before_len = len(_state.event_log)
    try:
        cmd = _to_command(payload)
        apply_command(_state, cmd)
    except ValueError as exc:  # noqa: PERF203 - user input validation
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_new_events(before_len)
    return state_to_dict(_state)


def _to_command(payload: CommandPayload) -> Command:
    t = payload.type.lower()
    args = payload.args
    if t == "buy":
        if "item_name" not in args:
            raise HTTPException(status_code=400, detail="item_name required")
        return Buy(item_name=str(args["item_name"]), quantity=int(args.get("quantity", 0)))
    if t == "sell":
        if "item_name" not in args:
            raise HTTPException(status_code=400, detail="item_name required")
        return Sell(item_name=str(args["item_name"]), quantity=int(args.get("quantity", 0)))
    if t == "travel":
        return Travel(destination_index=int(args.get("destination_index", -1)))
    if t == "advance_day":
        return AdvanceDay(days=int(args.get("days", 1)))
    if t == "repay":
        return RepayLoan(amount=float(args.get("amount", 0)))
    raise HTTPException(status_code=400, detail="Unsupported command type")


def _persist_new_events(previous_len: int) -> None:
    if not _event_log_path:
        return
    new_events = _state.event_log[previous_len:]
    if not new_events:
        return
    lines = [json.dumps(event) for event in new_events]
    _event_log_path.parent.mkdir(parents=True, exist_ok=True)
    with _event_log_path.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


__all__ = ["app"]
