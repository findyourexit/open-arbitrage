# Open Arbitrage Examples

This doc shows how to interact with the engine via CLI and HTTP, and what the JSON state looks like (including the per-city market and event logs).

## CLI

- Play the game loop:
  - `python -m open_arbitrage.cli play`
- Dump a fresh state (deterministic):
  - `python -m open_arbitrage.cli dump-state --seed 5`

Sample `dump-state` output (trimmed):

```json
{
  "version": 2,
  "day": 0,
  "city_index": 0,
  "cash": 2000.0,
  "loan": {"balance": 10000.0, "rate": 0.01, "max_balance": 200000.0},
  "inventory": {"holdings": {}, "capacity": 100},
  "market": {
    "goods": [
      {"name": "coffee", "base_value": 10.0, "min_value": 1.0, "max_value": 40.0}
    ],
    "boards": [
      [{"good": "coffee", "value": 10.74, "base_value": 10.74, "min_value": 1.07, "max_value": 42.9, "last_value": 10.74}, ...],
      ...one board per city...
    ]
  },
  "cities": ["Sydney", "Melbourne", "Zurich", "New York", "Milano", "Santa Barbara"],
  "rules": {
    "travel_cost": 60.0,
    "travel_time_days": 1,
    "inventory_capacity": 100,
    "win_net_worth": 20000.0,
    "max_days": 365,
    "trade_spread": 0.02,
    "price_reversion": 0.15,
    "price_volatility": 0.08,
    "city_price_spread": [0.7, 1.3],
    "daily_event_chance": 0.3,
    "travel_event_chance": 0.2,
    "daily_event_weights": {"demand_spike": 1.4, "cash_windfall": 1.1, "market_shock": 0.9, "theft": 0.8, "spoilage": 0.7, "creditor_call": 0.6, "insurance_payout": 0.5},
    "travel_event_weights": {"weather_delay": 0.6, "customs_fine": 0.4},
    "city_event_multipliers": {"Zurich": 1.1, "New York": 1.1, "Milano": 1.05, "Santa Barbara": 0.9},
    "spoilage_item_multipliers": {"spice": 1.2, "grain": 1.4}
  },
  "status": "ongoing",
  "seed": 5,
  "rng_state": {"version": 3, "internal": [ ... ], "gauss_next": null},
  "event_log": [],
  "last_loss_value": 0.0
}
```

### The market shape

- `market.goods` is the global catalog: each good has a `base_value`, `min_value`, `max_value`.
- `market.boards[city_index][good_index]` is that city's live quote for that good. `boards` is index-aligned with `cities`.
- A quote's `base_value` is the **city-specific** long-run mean the price reverts toward; `value` is the current mid price. Buy at `value * (1 + trade_spread)`, sell at `value * (1 - trade_spread)`.

Because each city has its own `base_value` per good (drawn from `city_price_spread` at creation), prices differ by location — that gap, net of the spread and travel cost, is the arbitrage profit.

### Determinism & save/load

`rng_state` captures the full Mersenne-Twister state, so `state_from_dict(state_to_dict(s))` reproduces an exact, byte-for-byte continuation of play — not just the seed. This makes saved games, replays, and agent training reproducible.

## Event log shape and persistence

Each event entry has `kind`, `day`, `city`, and a `details` payload keyed per kind:

- `demand_spike`: `good`, `multiplier`, `before_value`, `after_value` (in the current city).
- `theft`: `removed` mapping of good to quantity stolen, `loss_value`.
- `cash_windfall`: `amount` added to cash.
- `creditor_call`: `demand`, `paid` (cash applied to loan).
- `spoilage`: `good`, `removed`, `loss_value` (also tracked in `last_loss_value`).
- `market_shock`: `multiplier`, `scope` (`"global"` — applies to every city).
- `insurance_payout`: `base_loss`, `payout` (resets `last_loss_value`).
- `weather_delay`: `delay_days` (travel time added).
- `customs_fine`: `fine`, `added_to_loan` (portion exceeding cash).

Optional persistence: set `OPEN_ARBITRAGE_EVENT_LOG_PATH=/path/to/events.jsonl` before starting the API to append each new event as a JSON line (each line is tagged with its `game_id`). The in-memory log is capped by `rules.event_log_limit` (default 200 recent events).

## HTTP API (FastAPI)

Start the server:

- `uvicorn open_arbitrage.api:app --reload`

Endpoints — each game is an isolated, server-side session keyed by `game_id`:

- `POST /games` — create a game (returns `{ "game_id", "state" }`); optional overrides: `seed`, `travel_cost`, `trade_spread`, `inventory_capacity`, `win_net_worth`, `max_days`.
- `GET /games` — list active game ids.
- `GET /games/{game_id}` — full engine state JSON.
- `DELETE /games/{game_id}` — discard a game.
- `POST /games/{game_id}/commands` — apply an engine command:
  - Buy: `{"type": "buy", "args": {"good_name": "coffee", "quantity": 2}}`
  - Sell: `{"type": "sell", "args": {"good_name": "coffee", "quantity": 1}}`
  - Travel: `{"type": "travel", "args": {"destination_index": 1}}`
  - Advance day(s): `{"type": "advance_day", "args": {"days": 2}}`
  - Repay: `{"type": "repay", "args": {"amount": 100}}`

Example curl session (server on localhost:8000):

```sh
# Create a game with a seed and capture its id
GAME=$(curl -s -X POST http://localhost:8000/games \
  -H "Content-Type: application/json" \
  -d '{"seed": 5}' | jq -r '.game_id')

# Inspect coffee prices across cities to spot arbitrage
curl -s http://localhost:8000/games/$GAME \
  | jq '[.market.boards[] | .[] | select(.good=="coffee") | .value]'

# Buy 10 coffee where it is cheap
curl -s -X POST http://localhost:8000/games/$GAME/commands \
  -H "Content-Type: application/json" \
  -d '{"type": "buy", "args": {"good_name": "coffee", "quantity": 10}}' | jq '.cash, .inventory.holdings'

# Travel to a pricier market, then sell
curl -s -X POST http://localhost:8000/games/$GAME/commands \
  -H "Content-Type: application/json" \
  -d '{"type": "travel", "args": {"destination_index": 5}}' | jq '.day, .city_index'

curl -s -X POST http://localhost:8000/games/$GAME/commands \
  -H "Content-Type: application/json" \
  -d '{"type": "sell", "args": {"good_name": "coffee", "quantity": 10}}' | jq '.cash'
```

## Testing

Run all checks:

- `make lint typecheck test`
- `make cov` for a coverage report.
