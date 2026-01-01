# Open Arbitrage

Deterministic, seedable trading/arbitrage game engine with a Typer/Rich CLI and a FastAPI adapter. The engine owns all state; the CLI and HTTP layers are thin façades over typed commands.

## Features

- Engine-first design: pure data classes and commands (`buy`, `sell`, `travel`, `advance_day`, `repay`) with deterministic RNG seeding and JSON (de)serialization (`state_to_dict`/`state_from_dict`).
- Price dynamics: bounded random-walk pricing with configurable inventory capacity, travel cost/time, win-condition net worth, max days, and adjustable event weights (daily and travel).
- Event system: demand spikes, theft, cash windfalls, creditor calls, spoilage, market shocks, insurance payouts, weather delays, and customs fines; optional JSONL persistence via `OPEN_ARBITRAGE_EVENT_LOG_PATH` with in-memory log trimming.
- Multiple frontends: interactive CLI loop, JSON dump utility, and FastAPI adapter exposing `/state`, `/reset`, and `/command` endpoints.
- Extensible defaults: swap seeds, tweak `Rules` (city and spoilage multipliers, event chances), or plug the engine into other hosts without rewriting game logic.
- No legacy paths: the codebase targets the engine-driven CLI/API only (legacy script mode removed).

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
  python -m open_arbitrage.cli play --seed 5 --travel-cost 50 --win-net-worth 20000 --max-days 365
  ```

- Dump a fresh deterministic state for tooling/tests:

  ```sh
  python -m open_arbitrage.cli dump-state --seed 5
  ```

### HTTP API

- Start the server:

  ```sh
  uvicorn open_arbitrage.api:app --reload
  ```

- Endpoints:
  - `GET /state` — current engine state (same shape as `dump-state`).
  - `POST /reset` — optional overrides: `seed`, `travel_cost`, `win_net_worth`, `max_days`.
  - `POST /command` — execute engine commands:
    - Buy: `{ "type": "buy", "args": { "item_name": "a", "quantity": 2 } }`
    - Sell: `{ "type": "sell", "args": { "item_name": "a", "quantity": 1 } }`
    - Travel: `{ "type": "travel", "args": { "destination_index": 1 } }`
    - Advance day(s): `{ "type": "advance_day", "args": { "days": 2 } }`
    - Repay: `{ "type": "repay", "args": { "amount": 100 } }`

See [docs/examples.md](docs/examples.md) for sample curl sessions, state JSON shape, and event log details.

### Engine as a library

```python
from open_arbitrage.engine import create_default_state, Buy, apply_command

state = create_default_state(seed=42)
apply_command(state, Buy(item_name="a", quantity=1))
```

## Development and testing

- Install dev extras: `pip install -e .[dev]`
- Lint/format/type/test: `make lint typecheck test` (uses Ruff format+lint, MyPy strict, Pytest).
- Run targeted tests: `pytest tests/test_engine.py -q`
- Pre-commit: `pre-commit install` (optional, hooks match `make lint`).

## Project layout

- Engine and data models: [open_arbitrage/engine/core.py](open_arbitrage/engine/core.py)
- CLI entrypoint: [open_arbitrage/cli.py](open_arbitrage/cli.py)
- FastAPI adapter: [open_arbitrage/api.py](open_arbitrage/api.py)
- Docs: [docs/examples.md](docs/examples.md)

## License

MIT
