"""HTTP adapter for the Open Arbitrage engine (FastAPI).

Exposes the engine as a multi-game REST service. Each call to ``POST /games``
creates an isolated, server-side game session addressed by ``game_id``; the
engine owns all state, the HTTP layer is a thin, thread-safe façade.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .engine import (
    AdvanceDay,
    Buy,
    GameState,
    RepayLoan,
    Rules,
    Sell,
    Travel,
    apply_command,
    create_default_state,
    state_to_dict,
)
from .engine.core import Command

app = FastAPI(title="Open Arbitrage API", version="0.2.0")


class CreateGamePayload(BaseModel):
    seed: int | None = None
    travel_cost: float | None = None
    trade_spread: float | None = None
    inventory_capacity: int | None = None
    win_net_worth: float | None = None
    max_days: int | None = None


class CommandPayload(BaseModel):
    type: str = Field(..., examples=["buy", "sell", "travel", "advance_day", "repay"])
    args: dict[str, Any] = Field(default_factory=dict)


class GameStore:
    """Thread-safe registry of in-memory game sessions."""

    def __init__(self, event_log_path: Path | None = None) -> None:
        self._games: dict[str, GameState] = {}
        self._lock = threading.Lock()
        self.event_log_path = event_log_path

    def create(self, payload: CreateGamePayload) -> tuple[str, GameState]:
        rules = Rules()
        if payload.travel_cost is not None:
            rules.travel_cost = payload.travel_cost
        if payload.trade_spread is not None:
            rules.trade_spread = payload.trade_spread
        if payload.inventory_capacity is not None:
            rules.inventory_capacity = payload.inventory_capacity
        if payload.win_net_worth is not None:
            rules.win_net_worth = payload.win_net_worth
        if payload.max_days is not None:
            rules.max_days = payload.max_days

        game_id = uuid.uuid4().hex
        state = create_default_state(seed=payload.seed, rules=rules)
        with self._lock:
            self._games[game_id] = state
        return game_id, state

    def get(self, game_id: str) -> GameState:
        with self._lock:
            state = self._games.get(game_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Game not found")
        return state

    def delete(self, game_id: str) -> None:
        with self._lock:
            if self._games.pop(game_id, None) is None:
                raise HTTPException(status_code=404, detail="Game not found")

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._games)

    def run_command(self, game_id: str, command: Command) -> GameState:
        with self._lock:
            state = self._games.get(game_id)
            if state is None:
                raise HTTPException(status_code=404, detail="Game not found")
            before_len = len(state.event_log)
            try:
                apply_command(state, command)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            self._persist_new_events(game_id, state, before_len)
            return state

    def _persist_new_events(self, game_id: str, state: GameState, previous_len: int) -> None:
        if not self.event_log_path:
            return
        new_events = state.event_log[previous_len:]
        if not new_events:
            return
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            for event in new_events:
                handle.write(json.dumps({"game_id": game_id, **event}) + "\n")


_event_log_path_env = os.environ.get("OPEN_ARBITRAGE_EVENT_LOG_PATH")
_store = GameStore(
    event_log_path=Path(_event_log_path_env) if _event_log_path_env else None,
)


@app.post("/games", status_code=201)
def create_game(payload: CreateGamePayload) -> dict[str, Any]:
    game_id, state = _store.create(payload)
    return {"game_id": game_id, "state": state_to_dict(state)}


@app.get("/games")
def list_games() -> dict[str, list[str]]:
    return {"games": _store.ids()}


@app.get("/games/{game_id}")
def get_game(game_id: str) -> dict[str, Any]:
    return state_to_dict(_store.get(game_id))


@app.delete("/games/{game_id}", status_code=204)
def delete_game(game_id: str) -> None:
    _store.delete(game_id)


@app.post("/games/{game_id}/commands")
def post_command(game_id: str, payload: CommandPayload) -> dict[str, Any]:
    command = _to_command(payload)
    state = _store.run_command(game_id, command)
    return state_to_dict(state)


def _to_command(payload: CommandPayload) -> Command:
    kind = payload.type.lower()
    args = payload.args
    if kind == "buy":
        if "good_name" not in args:
            raise HTTPException(status_code=400, detail="good_name required")
        return Buy(good_name=str(args["good_name"]), quantity=int(args.get("quantity", 0)))
    if kind == "sell":
        if "good_name" not in args:
            raise HTTPException(status_code=400, detail="good_name required")
        return Sell(good_name=str(args["good_name"]), quantity=int(args.get("quantity", 0)))
    if kind == "travel":
        return Travel(destination_index=int(args.get("destination_index", -1)))
    if kind == "advance_day":
        return AdvanceDay(days=int(args.get("days", 1)))
    if kind == "repay":
        return RepayLoan(amount=float(args.get("amount", 0)))
    raise HTTPException(status_code=400, detail="Unsupported command type")


__all__ = ["app"]
