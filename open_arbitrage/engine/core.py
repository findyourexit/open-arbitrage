"""Pure game engine: state, commands, and deterministic logic (UI-agnostic)."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..market import Good, Market, Quote, build_market

DEFAULT_GOODS: list[Good] = [
    Good("coffee", 10.00),
    Good("watches", 50.00),
    Good("wine", 25.00),
    Good("silk", 30.00),
    Good("spice", 5.00),
    Good("grain", 1.00),
]
DEFAULT_CITIES: Sequence[str] = (
    "Sydney",
    "Melbourne",
    "Zurich",
    "New York",
    "Milano",
    "Santa Barbara",
)


@dataclass
class LoanAccount:
    balance: float
    rate: float
    max_balance: float

    def compound(self, days: int) -> None:
        for _ in range(days):
            self.balance += self.balance * self.rate

    def repay(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Repayment must be positive")
        repaid = min(amount, self.balance)
        self.balance -= repaid
        return repaid


@dataclass
class Inventory:
    holdings: dict[str, int] = field(default_factory=dict)
    capacity: int | None = None

    def add(self, good_name: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("Quantity must be non-negative")
        if quantity == 0:
            return
        new_total = self.total_quantity() + quantity
        if self.capacity is not None and new_total > self.capacity:
            raise ValueError("Inventory capacity exceeded")
        self.holdings[good_name] = self.holdings.get(good_name, 0) + quantity

    def remove(self, good_name: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("Quantity must be non-negative")
        current = self.holdings.get(good_name, 0)
        if quantity > current:
            raise ValueError("Not enough inventory to remove")
        remaining = current - quantity
        if remaining == 0:
            self.holdings.pop(good_name, None)
        else:
            self.holdings[good_name] = remaining

    def total_quantity(self) -> int:
        return sum(self.holdings.values())

    def quantity(self, good_name: str) -> int:
        return self.holdings.get(good_name, 0)


class GameOutcome(StrEnum):
    ONGOING = "ongoing"
    WON = "won"
    LOST = "lost"


@dataclass
class Rules:
    travel_cost: float = 60.0
    travel_time_days: int = 1
    inventory_capacity: int | None = 100
    win_net_worth: float = 20_000.0
    max_days: int | None = 365
    # Trading friction: half-spread applied to every buy (ask) and sell (bid).
    trade_spread: float = 0.02
    # Per-city price dynamics.
    price_reversion: float = 0.15
    price_volatility: float = 0.08
    city_price_spread: tuple[float, float] = (0.7, 1.3)
    daily_event_chance: float = 0.3
    travel_event_chance: float = 0.2
    event_log_limit: int | None = 200
    daily_event_weights: dict[str, float] = field(
        default_factory=lambda: {
            "demand_spike": 1.4,
            "cash_windfall": 1.1,
            "market_shock": 0.9,
            "theft": 0.8,
            "spoilage": 0.7,
            "creditor_call": 0.6,
            "insurance_payout": 0.5,
        }
    )
    travel_event_weights: dict[str, float] = field(
        default_factory=lambda: {
            "weather_delay": 0.6,
            "customs_fine": 0.4,
        }
    )
    city_event_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "Zurich": 1.1,
            "New York": 1.1,
            "Milano": 1.05,
            "Santa Barbara": 0.9,
        }
    )
    spoilage_item_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "spice": 1.2,
            "grain": 1.4,
        }
    )


@dataclass
class GameState:
    day: int
    city_index: int
    cash: float
    loan: LoanAccount
    inventory: Inventory
    market: Market
    cities: Sequence[str]
    rng: random.Random
    rules: Rules
    status: GameOutcome = GameOutcome.ONGOING
    seed: int | None = None
    event_log: list[dict[str, Any]] = field(default_factory=list)
    last_loss_value: float = 0.0

    def current_city(self) -> str:
        return self.cities[self.city_index]


# Commands
@dataclass
class Buy:
    good_name: str
    quantity: int


@dataclass
class Sell:
    good_name: str
    quantity: int


@dataclass
class Travel:
    destination_index: int


@dataclass
class RepayLoan:
    amount: float


@dataclass
class AdvanceDay:
    days: int = 1


@dataclass
class SetSeed:
    seed: int


Command = Buy | Sell | Travel | RepayLoan | AdvanceDay | SetSeed


def create_default_state(seed: int | None = None, rules: Rules | None = None) -> GameState:
    rng = random.Random(seed)
    game_rules = rules or Rules()
    market = build_market(
        DEFAULT_GOODS,
        DEFAULT_CITIES,
        rng,
        city_price_spread=game_rules.city_price_spread,
    )
    return GameState(
        day=0,
        city_index=0,
        cash=2_000.0,
        loan=LoanAccount(balance=10_000.0, rate=0.01, max_balance=200_000.0),
        inventory=Inventory(capacity=game_rules.inventory_capacity),
        market=market,
        cities=DEFAULT_CITIES,
        rng=rng,
        rules=game_rules,
        status=GameOutcome.ONGOING,
        seed=seed,
    )


# --- Pricing helpers ------------------------------------------------------


def _mid_price(state: GameState, good_name: str) -> float:
    return state.market.quote(state.city_index, good_name).value


def ask_price(state: GameState, good_name: str) -> float:
    """Price to buy one unit in the current city (mid + half-spread)."""
    return _mid_price(state, good_name) * (1.0 + state.rules.trade_spread)


def bid_price(state: GameState, good_name: str) -> float:
    """Price received to sell one unit in the current city (mid - half-spread)."""
    return _mid_price(state, good_name) * (1.0 - state.rules.trade_spread)


def _fluctuate_world(state: GameState) -> None:
    state.market.fluctuate(
        state.rng,
        reversion=state.rules.price_reversion,
        volatility=state.rules.price_volatility,
    )


def apply_command(state: GameState, command: Command) -> None:
    _ensure_ongoing(state)

    if isinstance(command, SetSeed):
        state.rng.seed(command.seed)
        state.seed = command.seed
        return

    if isinstance(command, AdvanceDay):
        if command.days < 1:
            raise ValueError("Days to advance must be positive")
        for _ in range(command.days):
            _fluctuate_world(state)
            _apply_daily_event(state)
            state.loan.compound(1)
            state.day += 1
        _evaluate_outcome(state)
        return

    if isinstance(command, Travel):
        if command.destination_index < 0 or command.destination_index >= len(state.cities):
            raise ValueError("Invalid destination")
        if command.destination_index == state.city_index:
            return
        if state.cash < state.rules.travel_cost:
            raise ValueError("Insufficient cash for travel")
        state.cash -= state.rules.travel_cost
        state.city_index = command.destination_index
        travel_days = state.rules.travel_time_days + _apply_travel_event(state)
        for _ in range(travel_days):
            _fluctuate_world(state)
            state.loan.compound(1)
            state.day += 1
        _evaluate_outcome(state)
        return

    if isinstance(command, Buy):
        if command.quantity <= 0:
            raise ValueError("Quantity must be positive")
        unit_price = ask_price(state, command.good_name)
        cost = unit_price * command.quantity
        if cost > state.cash:
            raise ValueError("Insufficient cash")
        state.inventory.add(command.good_name, command.quantity)
        state.cash -= cost
        _evaluate_outcome(state)
        return

    if isinstance(command, Sell):
        if command.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if state.inventory.quantity(command.good_name) < command.quantity:
            raise ValueError("Insufficient inventory")
        unit_price = bid_price(state, command.good_name)
        state.inventory.remove(command.good_name, command.quantity)
        state.cash += unit_price * command.quantity
        _evaluate_outcome(state)
        return

    if isinstance(command, RepayLoan):
        if command.amount <= 0:
            raise ValueError("Repayment must be positive")
        if command.amount > state.cash:
            raise ValueError("Insufficient cash to repay loan")
        repaid = state.loan.repay(command.amount)
        state.cash -= repaid
        _evaluate_outcome(state)
        return

    raise ValueError("Unsupported command")


def _inventory_value(state: GameState) -> float:
    """Liquidation value of held goods at the current city's bid prices."""
    value = 0.0
    for name, qty in state.inventory.holdings.items():
        value += bid_price(state, name) * qty
    return value


def net_worth(state: GameState) -> float:
    return state.cash + _inventory_value(state) - state.loan.balance


def _weighted_choice(weights: dict[str, float], rng: random.Random) -> str | None:
    filtered = {k: v for k, v in weights.items() if v > 0}
    if not filtered:
        return None
    total = sum(filtered.values())
    roll = rng.uniform(0, total)
    upto = 0.0
    for key, weight in filtered.items():
        upto += weight
        if roll <= upto:
            return key
    return None


def _append_event(state: GameState, kind: str, details: dict[str, Any]) -> None:
    state.event_log.append(
        {
            "kind": kind,
            "day": state.day,
            "city": state.current_city(),
            "details": details,
        }
    )
    if state.rules.event_log_limit and state.rules.event_log_limit > 0:
        state.event_log = state.event_log[-state.rules.event_log_limit :]


def _apply_daily_event(state: GameState) -> None:
    if state.rules.daily_event_chance <= 0:
        return
    city_multiplier = state.rules.city_event_multipliers.get(state.current_city(), 1.0)
    effective_chance = state.rules.daily_event_chance * city_multiplier
    if effective_chance <= 0:
        return
    if state.rng.random() > effective_chance:
        return

    event_kind = _weighted_choice(state.rules.daily_event_weights, state.rng)
    if event_kind is None:
        return

    if event_kind == "demand_spike":
        _event_demand_spike(state)
    elif event_kind == "theft":
        _event_theft(state)
    elif event_kind == "cash_windfall":
        _event_cash_windfall(state)
    elif event_kind == "creditor_call":
        _event_creditor_call(state)
    elif event_kind == "spoilage":
        _event_spoilage(state)
    elif event_kind == "market_shock":
        _event_market_shock(state)
    elif event_kind == "insurance_payout":
        _event_insurance_payout(state)


def _apply_travel_event(state: GameState) -> int:
    if state.rules.travel_event_chance <= 0:
        return 0
    if state.rng.random() > state.rules.travel_event_chance:
        return 0

    event_kind = _weighted_choice(state.rules.travel_event_weights, state.rng)
    if event_kind is None:
        return 0

    if event_kind == "weather_delay":
        return _event_weather_delay(state)
    if event_kind == "customs_fine":
        _event_customs_fine(state)
        return 0
    return 0


def _clamp_quote(quote: Quote, value: float) -> None:
    quote.value = min(max(value, quote.min_value), quote.max_value)


def _event_demand_spike(state: GameState) -> None:
    board = state.market.board(state.city_index)
    quote = state.rng.choice(board)
    before_value = quote.value
    multiplier = state.rng.uniform(1.25, 1.6)
    _clamp_quote(quote, quote.value * multiplier)
    _append_event(
        state,
        "demand_spike",
        {
            "good": quote.good,
            "multiplier": multiplier,
            "before_value": before_value,
            "after_value": quote.value,
        },
    )


def _event_theft(state: GameState) -> None:
    total_qty = state.inventory.total_quantity()
    if total_qty == 0:
        return
    fraction = state.rng.uniform(0.05, 0.2)
    to_remove = max(1, int(total_qty * fraction))

    removed: dict[str, int] = {}
    for _ in range(to_remove):
        weighted_items = [
            (name, qty / total_qty) for name, qty in state.inventory.holdings.items() if qty > 0
        ]
        if not weighted_items:  # pragma: no cover - defensive guard
            break
        names: list[str] = [name for name, _ in weighted_items]
        weights: list[float] = [weight for _, weight in weighted_items]
        choice = state.rng.choices(names, weights=weights, k=1)[0]
        state.inventory.remove(choice, 1)
        removed[choice] = removed.get(choice, 0) + 1
        total_qty -= 1

    loss_value = 0.0
    for name, qty in removed.items():
        loss_value += _mid_price(state, name) * qty
    state.last_loss_value += loss_value

    _append_event(
        state,
        "theft",
        {
            "removed": removed,
            "loss_value": loss_value,
        },
    )


def _event_weather_delay(state: GameState) -> int:
    delay = state.rng.randint(1, 2)
    _append_event(
        state,
        "weather_delay",
        {
            "delay_days": delay,
        },
    )
    return delay


def _event_cash_windfall(state: GameState) -> None:
    amount = state.rng.uniform(200, 800)
    state.cash += amount
    _append_event(
        state,
        "cash_windfall",
        {
            "amount": amount,
        },
    )


def _event_creditor_call(state: GameState) -> None:
    demand = state.rng.uniform(250, 750)
    pay_amount = min(demand, state.cash)
    if pay_amount > 0:
        repaid = state.loan.repay(pay_amount)
        state.cash -= repaid
    else:
        repaid = 0.0
    _append_event(
        state,
        "creditor_call",
        {
            "demand": demand,
            "paid": repaid,
        },
    )


def _event_spoilage(state: GameState) -> None:
    total_qty = state.inventory.total_quantity()
    if total_qty == 0:
        return
    items = list(state.inventory.holdings.keys())
    if state.rules.spoilage_item_multipliers:
        weights = [state.rules.spoilage_item_multipliers.get(name, 1.0) for name in items]
        good_name = state.rng.choices(items, weights=weights, k=1)[0]
    else:
        good_name = state.rng.choice(items)
    current_qty = state.inventory.quantity(good_name)
    if current_qty == 0:
        return
    fraction = state.rng.uniform(0.1, 0.3)
    to_remove = max(1, int(current_qty * fraction))
    to_remove = min(to_remove, current_qty)
    state.inventory.remove(good_name, to_remove)
    loss_value = _mid_price(state, good_name) * to_remove
    state.last_loss_value += loss_value
    _append_event(
        state,
        "spoilage",
        {
            "good": good_name,
            "removed": to_remove,
            "loss_value": loss_value,
        },
    )


def _event_market_shock(state: GameState) -> None:
    multiplier = state.rng.uniform(0.85, 1.15)
    for board in state.market.boards:
        for quote in board:
            _clamp_quote(quote, quote.value * multiplier)
    _append_event(
        state,
        "market_shock",
        {
            "multiplier": multiplier,
            "scope": "global",
        },
    )


def _event_insurance_payout(state: GameState) -> None:
    base_loss = state.last_loss_value
    payout = 0.0 if base_loss <= 0 else base_loss * state.rng.uniform(0.2, 0.4)
    state.cash += payout
    state.last_loss_value = 0.0
    _append_event(
        state,
        "insurance_payout",
        {
            "base_loss": base_loss,
            "payout": payout,
        },
    )


def _event_customs_fine(state: GameState) -> None:
    fine = state.rng.uniform(100, 300)
    if state.cash >= fine:
        state.cash -= fine
        added_to_loan = 0.0
    else:
        deficit = fine - state.cash
        state.cash = 0.0
        state.loan.balance += deficit
        added_to_loan = deficit
    _append_event(
        state,
        "customs_fine",
        {
            "fine": fine,
            "added_to_loan": added_to_loan,
        },
    )


def _evaluate_outcome(state: GameState) -> None:
    if state.status is not GameOutcome.ONGOING:
        return

    if state.loan.balance >= state.loan.max_balance:
        state.status = GameOutcome.LOST
        return

    if state.rules.max_days is not None and state.day >= state.rules.max_days:
        if net_worth(state) >= state.rules.win_net_worth:
            state.status = GameOutcome.WON
        else:
            state.status = GameOutcome.LOST
        return

    if net_worth(state) >= state.rules.win_net_worth:
        state.status = GameOutcome.WON


def _ensure_ongoing(state: GameState) -> None:
    if state.status is not GameOutcome.ONGOING:
        raise ValueError("Game is finished")


STATE_VERSION = 2


def _encode_rng_state(rng: random.Random) -> dict[str, Any]:
    version, internal, gauss_next = rng.getstate()
    return {
        "version": version,
        "internal": list(internal),
        "gauss_next": gauss_next,
    }


def _decode_rng_state(data: dict[str, Any]) -> tuple[int, tuple[int, ...], float | None]:
    return (
        int(data["version"]),
        tuple(int(value) for value in data["internal"]),
        data["gauss_next"],
    )


def state_to_dict(state: GameState) -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "day": state.day,
        "city_index": state.city_index,
        "cash": state.cash,
        "loan": {
            "balance": state.loan.balance,
            "rate": state.loan.rate,
            "max_balance": state.loan.max_balance,
        },
        "inventory": {
            "holdings": state.inventory.holdings,
            "capacity": state.inventory.capacity,
        },
        "market": {
            "goods": [
                {
                    "name": good.name,
                    "base_value": good.base_value,
                    "min_value": good.min_value,
                    "max_value": good.max_value,
                }
                for good in state.market.goods
            ],
            "boards": [
                [
                    {
                        "good": quote.good,
                        "value": quote.value,
                        "base_value": quote.base_value,
                        "min_value": quote.min_value,
                        "max_value": quote.max_value,
                        "last_value": quote.last_value,
                    }
                    for quote in board
                ]
                for board in state.market.boards
            ],
        },
        "cities": list(state.cities),
        "rules": {
            "travel_cost": state.rules.travel_cost,
            "travel_time_days": state.rules.travel_time_days,
            "inventory_capacity": state.rules.inventory_capacity,
            "win_net_worth": state.rules.win_net_worth,
            "max_days": state.rules.max_days,
            "trade_spread": state.rules.trade_spread,
            "price_reversion": state.rules.price_reversion,
            "price_volatility": state.rules.price_volatility,
            "city_price_spread": list(state.rules.city_price_spread),
            "daily_event_chance": state.rules.daily_event_chance,
            "travel_event_chance": state.rules.travel_event_chance,
            "event_log_limit": state.rules.event_log_limit,
            "daily_event_weights": state.rules.daily_event_weights,
            "travel_event_weights": state.rules.travel_event_weights,
            "city_event_multipliers": state.rules.city_event_multipliers,
            "spoilage_item_multipliers": state.rules.spoilage_item_multipliers,
        },
        "status": state.status.value,
        "seed": state.seed,
        "rng_state": _encode_rng_state(state.rng),
        "event_log": list(state.event_log),
        "last_loss_value": state.last_loss_value,
    }


def state_from_dict(payload: dict[str, Any]) -> GameState:
    if payload.get("version") != STATE_VERSION:
        raise ValueError("Unsupported state version")

    raw_rules = payload["rules"]
    spread = raw_rules.get("city_price_spread", [0.7, 1.3])
    rules = Rules(
        travel_cost=raw_rules["travel_cost"],
        travel_time_days=raw_rules["travel_time_days"],
        inventory_capacity=raw_rules.get("inventory_capacity"),
        win_net_worth=raw_rules["win_net_worth"],
        max_days=raw_rules.get("max_days"),
        trade_spread=raw_rules.get("trade_spread", 0.0),
        price_reversion=raw_rules.get("price_reversion", 0.15),
        price_volatility=raw_rules.get("price_volatility", 0.08),
        city_price_spread=(float(spread[0]), float(spread[1])),
        daily_event_chance=raw_rules.get("daily_event_chance", 0.0),
        travel_event_chance=raw_rules.get("travel_event_chance", 0.0),
        event_log_limit=raw_rules.get("event_log_limit"),
        daily_event_weights=dict(raw_rules.get("daily_event_weights", {})),
        travel_event_weights=dict(raw_rules.get("travel_event_weights", {})),
        city_event_multipliers=dict(raw_rules.get("city_event_multipliers", {})),
        spoilage_item_multipliers=dict(raw_rules.get("spoilage_item_multipliers", {})),
    )

    seed = payload.get("seed")
    rng = random.Random()
    if payload.get("rng_state") is not None:
        rng.setstate(_decode_rng_state(payload["rng_state"]))
    elif seed is not None:
        rng.seed(seed)

    market = Market(
        goods=[
            Good(
                name=good["name"],
                base_value=good["base_value"],
                min_value=good["min_value"],
                max_value=good["max_value"],
            )
            for good in payload["market"]["goods"]
        ],
        boards=[
            [
                Quote(
                    good=quote["good"],
                    value=quote["value"],
                    base_value=quote["base_value"],
                    min_value=quote["min_value"],
                    max_value=quote["max_value"],
                    last_value=quote["last_value"],
                )
                for quote in board
            ]
            for board in payload["market"]["boards"]
        ],
    )

    state = GameState(
        day=payload["day"],
        city_index=payload["city_index"],
        cash=payload["cash"],
        loan=LoanAccount(
            balance=payload["loan"]["balance"],
            rate=payload["loan"]["rate"],
            max_balance=payload["loan"]["max_balance"],
        ),
        inventory=Inventory(
            holdings=dict(payload["inventory"]["holdings"]),
            capacity=payload["inventory"].get("capacity"),
        ),
        market=market,
        cities=tuple(payload["cities"]),
        rng=rng,
        rules=rules,
        status=GameOutcome(payload.get("status", GameOutcome.ONGOING.value)),
        seed=seed,
        event_log=list(payload.get("event_log", [])),
        last_loss_value=payload.get("last_loss_value", 0.0),
    )

    return state
