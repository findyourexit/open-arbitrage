# Open Arbitrage

Deterministic, seedable trading/arbitrage game engine with a Typer/Rich CLI and a FastAPI adapter. The engine owns all state; the CLI and HTTP layers are thin façades over typed commands.

You start with cash and a compounding loan. Every city quotes its own price for every good, so the game is real arbitrage: **buy where a good is cheap, travel, and sell where it is dear** — all before the loan clock buries you or the day limit runs out.

## Features

- **Real per-city markets:** each city quotes its own price for every good. Prices follow a bounded, mean-reverting random walk in log space (always positive, anchored to a city-specific long-run mean), so durable arbitrage opportunities exist and persist.
- **Trading friction:** a configurable bid/ask half-spread (`trade_spread`) applies to every buy (ask) and sell (bid), so round-trips have a real cost.
- **Engine-first design:** pure dataclasses and commands (`Buy`, `Sell`, `Travel`, `AdvanceDay`, `RepayLoan`) with deterministic RNG seeding.
- **Truly deterministic save/load:** `state_to_dict`/`state_from_dict` serialize the full RNG state, so reloading mid-game and continuing reproduces play exactly.
- **Event system:** demand spikes, theft, cash windfalls, creditor calls, spoilage, market shocks, insurance payouts, weather delays, and customs fines; optional JSONL persistence via `OPEN_ARBITRAGE_EVENT_LOG_PATH`.
- **Multiple frontends:** interactive CLI loop, JSON dump utility, and a multi-session FastAPI adapter.
- **Extensible defaults:** swap seeds, tweak `Rules` (spread, volatility, mean reversion, city price spread, event weights), or embed the engine in another host.

## Requirements

- Python 3.11+

## Installation

```sh
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

## Usage

### CLI

- Play the interactive loop (prompts: buy, sell, travel, repay, advance day, quit):

  ```sh
  python -m open_arbitrage.cli play --seed 5 --travel-cost 60 --spread 0.02 --win-net-worth 20000 --max-days 365
  ```

  The board shows each good's buy (ask) and sell (bid) price in the current city, plus the **best city to sell** each good you hold — your arbitrage radar.

- Dump a fresh deterministic state for tooling/tests:

  ```sh
  python -m open_arbitrage.cli dump-state --seed 5
  ```

### HTTP API

- Start the server:

  ```sh
  uvicorn open_arbitrage.api:app --reload
  ```

- Endpoints (each game is an isolated, server-side session keyed by `game_id`):
  - `POST /games` — create a game; optional overrides: `seed`, `travel_cost`, `trade_spread`, `inventory_capacity`, `win_net_worth`, `max_days`. Returns `{ "game_id", "state" }`.
  - `GET /games` — list active game ids.
  - `GET /games/{game_id}` — current engine state.
  - `DELETE /games/{game_id}` — discard a game.
  - `POST /games/{game_id}/commands` — execute engine commands:
    - Buy: `{ "type": "buy", "args": { "good_name": "coffee", "quantity": 2 } }`
    - Sell: `{ "type": "sell", "args": { "good_name": "coffee", "quantity": 1 } }`
    - Travel: `{ "type": "travel", "args": { "destination_index": 1 } }`
    - Advance day(s): `{ "type": "advance_day", "args": { "days": 2 } }`
    - Repay: `{ "type": "repay", "args": { "amount": 100 } }`

See [docs/examples.md](docs/examples.md) for sample curl sessions, state JSON shape, and event log details.

### Engine as a library

```python
from open_arbitrage.engine import create_default_state, Buy, Travel, Sell, apply_command, net_worth

state = create_default_state(seed=42)
apply_command(state, Buy(good_name="coffee", quantity=10))  # buy where cheap
apply_command(state, Travel(destination_index=3))            # sail to a pricier market
apply_command(state, Sell(good_name="coffee", quantity=10))  # sell high
print(net_worth(state))
```

## Development and testing

- Install dev extras: `pip install -e '.[dev]'`
- Lint/format/type/test: `make lint typecheck test` (Ruff format+lint, MyPy strict, Pytest).
- Coverage: `make cov` (the suite holds 100% line coverage).
- Run targeted tests: `pytest tests/test_engine.py -q`
- Pre-commit: `pre-commit install` (hooks match `make lint` + strict mypy).

## Project layout

- Market model (goods + per-city price dynamics): [open_arbitrage/market.py](open_arbitrage/market.py)
- Engine and data models: [open_arbitrage/engine/core.py](open_arbitrage/engine/core.py)
- CLI entrypoint: [open_arbitrage/cli.py](open_arbitrage/cli.py)
- FastAPI adapter: [open_arbitrage/api.py](open_arbitrage/api.py)
- Docs: [docs/examples.md](docs/examples.md)

## License

MIT
