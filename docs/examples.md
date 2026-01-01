# Open Arbitrage Examples

This doc shows how to interact with the engine via CLI and HTTP, and what the JSON state looks like (including event logs).

## CLI

- Play the game loop:
  - `python -m open_arbitrage.cli play`
- Dump a fresh state (deterministic):
  - `python -m open_arbitrage.cli dump-state --seed 5`

Sample `dump-state` output (trimmed):

```json
{
  "version": 1,
  "day": 0,
  "city_index": 0,
  "cash": 250.0,
  "loan": {"balance": 10000.0, "rate": 0.01, "max_balance": 200000.0},
  "inventory": {"holdings": {}, "capacity": 100},
  "market": [{"name": "a", "value": 10.0, "base_value": 10.0, "min_value": 1.0, "max_value": 40.0, "last_value": 10.0}, ...],
  "cities": ["Sydney", "Melbourne", "Zurich", "New York", "Milano", "Santa Barbara"],
  "rules": {
    "travel_cost": 60.0,
    "travel_time_days": 1,
    "inventory_capacity": 100,
    "win_net_worth": 20000.0,
    "max_days": 365,
    "daily_event_chance": 0.3,
    "travel_event_chance": 0.2,
    "daily_event_weights": {"demand_spike": 1.4, "cash_windfall": 1.1, "market_shock": 0.9, "theft": 0.8, "spoilage": 0.7, "creditor_call": 0.6, "insurance_payout": 0.5},
    "travel_event_weights": {"weather_delay": 0.6, "customs_fine": 0.4},
    "city_event_multipliers": {"Zurich": 1.1, "New York": 1.1, "Milano": 1.05, "Santa Barbara": 0.9},
    "spoilage_item_multipliers": {"e": 1.2, "f": 1.4}
  },
  "status": "ongoing",
  "seed": 5,
  "event_log": [],
  "last_loss_value": 0.0
}
```

## Event log shape and persistence

Each event entry:

- `kind`: event type (e.g., `demand_spike`, `theft`, `cash_windfall`, `creditor_call`, `spoilage`, `market_shock`, `insurance_payout`, `weather_delay`, `customs_fine`).
- `day`: in-game day when it occurred.
- `city`: city at time of event.
- `details`: payload keyed per event kind (examples below).

Example details by event:

- `demand_spike`: `item`, `multiplier`, `before_value`, `after_value`.
- `theft`: `removed` mapping of item to quantity stolen.
- `cash_windfall`: `amount` added to cash.
- `creditor_call`: `demand`, `paid` (cash applied to loan).
- `spoilage`: `item`, `removed`, `loss_value` (also tracked in `last_loss_value`).
- `market_shock`: `multiplier`, `before`, `after` price maps.
- `insurance_payout`: `base_loss`, `payout` (resets `last_loss_value`).
- `weather_delay`: `delay_days` (travel time added).
- `customs_fine`: `fine`, `added_to_loan` (portion exceeding cash).

Optional persistence:

- Set `OPEN_ARBITRAGE_EVENT_LOG_PATH=/path/to/events.jsonl` before starting the API to append each new event as a JSON line. The in-memory log is capped by `rules.event_log_limit` (default 200 recent events).

## HTTP API (FastAPI)

Start the server:

- `uvicorn open_arbitrage.api:app --reload`

Endpoints:

- `GET /state` — returns the full engine state JSON (same shape as dump-state).
- `POST /reset` — reset with optional overrides:
  - Body example:

    ```json
    {"seed": 123, "travel_cost": 55, "win_net_worth": 15000, "max_days": 200}
    ```

- `POST /command` — apply an engine command:
  - Buy: `{"type": "buy", "args": {"item_name": "a", "quantity": 2}}`
  - Sell: `{"type": "sell", "args": {"item_name": "a", "quantity": 1}}`
  - Travel: `{"type": "travel", "args": {"destination_index": 1}}`
  - Advance day(s): `{"type": "advance_day", "args": {"days": 2}}`
  - Repay: `{"type": "repay", "args": {"amount": 100}}`

Example curl session (server on localhost:8000):

```sh
# Reset with a seed
curl -s -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"seed": 5}' | jq '.status, .cash, .rules.daily_event_chance'

# Buy 2 of item "a"
curl -s -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"type": "buy", "args": {"item_name": "a", "quantity": 2}}' | jq '.cash, .inventory.holdings'

# Advance one day
curl -s -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"type": "advance_day", "args": {"days": 1}}' | jq '.day, .event_log[-1]'
```

## Testing

Run all checks:

- `make lint typecheck test`
