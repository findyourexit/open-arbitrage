"""Pure game engine models and commands."""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..market import Item, clone_items, fluctuate_market

DEFAULT_ITEMS: list[Item] = [
    Item("a", 10.00),
    Item("b", 50.00),
    Item("c", 25.00),
    Item("d", 30.00),
    Item("e", 5.00),
    Item("f", 1.00),
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

    def add(self, item_name: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("Quantity must be non-negative")
        if quantity == 0:
            return
        new_total = self.total_quantity() + quantity
        if self.capacity is not None and new_total > self.capacity:
            raise ValueError("Inventory capacity exceeded")
        self.holdings[item_name] = self.holdings.get(item_name, 0) + quantity

    def remove(self, item_name: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("Quantity must be non-negative")
        current = self.holdings.get(item_name, 0)
        if quantity > current:
            raise ValueError("Not enough inventory to remove")
        remaining = current - quantity
        if remaining == 0:
            self.holdings.pop(item_name, None)
        else:
            self.holdings[item_name] = remaining

    def total_quantity(self) -> int:
        return sum(self.holdings.values())

    def quantity(self, item_name: str) -> int:
        return self.holdings.get(item_name, 0)


class GameOutcome(str, Enum):
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
            "e": 1.2,
            "f": 1.4,
        }
    )


@dataclass
class GameState:
    day: int
    city_index: int
    cash: float
    loan: LoanAccount
    inventory: Inventory
    market: list[Item]
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
    item_name: str
    quantity: int


@dataclass
class Sell:
    item_name: str
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
    return GameState(
        day=0,
        city_index=0,
        cash=250.0,
        loan=LoanAccount(balance=10_000.0, rate=0.01, max_balance=200_000.0),
        inventory=Inventory(capacity=game_rules.inventory_capacity),
        market=clone_items(DEFAULT_ITEMS),
        cities=DEFAULT_CITIES,
        rng=rng,
        rules=game_rules,
        status=GameOutcome.ONGOING,
        seed=seed,
    )


def _find_item(market: Iterable[Item], item_name: str) -> Item:
    for item in market:
        if item.name == item_name:
            return item
    raise ValueError(f"Unknown item: {item_name}")


def apply_command(state: GameState, command: Command) -> None:
    _ensure_ongoing(state)

    if isinstance(command, SetSeed):
        state.rng.seed(command.seed)
        state.seed = command.seed
        return

    if isinstance(command, AdvanceDay):
        for _ in range(command.days):
            fluctuate_market(state.market, rng=state.rng)
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
            fluctuate_market(state.market, rng=state.rng)
            state.loan.compound(1)
            state.day += 1
        _evaluate_outcome(state)
        return

    if isinstance(command, Buy):
        item = _find_item(state.market, command.item_name)
        if command.quantity <= 0:
            raise ValueError("Quantity must be positive")
        cost = item.value * command.quantity
        if cost > state.cash:
            raise ValueError("Insufficient cash")
        state.cash -= cost
        state.inventory.add(item.name, command.quantity)
        _evaluate_outcome(state)
        return

    if isinstance(command, Sell):
        item = _find_item(state.market, command.item_name)
        if command.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if state.inventory.quantity(item.name) < command.quantity:
            raise ValueError("Insufficient inventory")
        state.inventory.remove(item.name, command.quantity)
        state.cash += item.value * command.quantity
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
    value = 0.0
    for name, qty in state.inventory.holdings.items():
        item = _find_item(state.market, name)
        value += item.value * qty
    return value


def _net_worth(state: GameState) -> float:
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


def _event_demand_spike(state: GameState) -> None:
    item = state.rng.choice(state.market)
    before_value = item.value
    multiplier = state.rng.uniform(1.25, 1.6)
    item.value *= multiplier
    _append_event(
        state,
        "demand_spike",
        {
            "item": item.name,
            "multiplier": multiplier,
            "before_value": before_value,
            "after_value": item.value,
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
        item = _find_item(state.market, name)
        loss_value += item.value * qty
    state.last_loss_value += loss_value

    _append_event(
        state,
        "theft",
        {
            "removed": removed,
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
        item_name = state.rng.choices(items, weights=weights, k=1)[0]
    else:
        item_name = state.rng.choice(items)
    current_qty = state.inventory.quantity(item_name)
    if current_qty == 0:
        return
    fraction = state.rng.uniform(0.1, 0.3)
    to_remove = max(1, int(current_qty * fraction))
    to_remove = min(to_remove, current_qty)
    state.inventory.remove(item_name, to_remove)
    item = _find_item(state.market, item_name)
    loss_value = item.value * to_remove
    state.last_loss_value += loss_value
    _append_event(
        state,
        "spoilage",
        {
            "item": item_name,
            "removed": to_remove,
            "loss_value": loss_value,
        },
    )


def _event_market_shock(state: GameState) -> None:
    multiplier = state.rng.uniform(0.85, 1.15)
    before = {item.name: item.value for item in state.market}
    for item in state.market:
        item.value *= multiplier
    _append_event(
        state,
        "market_shock",
        {
            "multiplier": multiplier,
            "before": before,
            "after": {item.name: item.value for item in state.market},
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
        if _net_worth(state) >= state.rules.win_net_worth:
            state.status = GameOutcome.WON
        else:
            state.status = GameOutcome.LOST
        return

    if _net_worth(state) >= state.rules.win_net_worth:
        state.status = GameOutcome.WON


def _ensure_ongoing(state: GameState) -> None:
    if state.status is not GameOutcome.ONGOING:
        raise ValueError("Game is finished")


STATE_VERSION = 1


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
        "market": [
            {
                "name": item.name,
                "value": item.value,
                "base_value": item.base_value,
                "min_value": item.min_value,
                "max_value": item.max_value,
                "last_value": item.last_value,
            }
            for item in state.market
        ],
        "cities": list(state.cities),
        "rules": {
            "travel_cost": state.rules.travel_cost,
            "travel_time_days": state.rules.travel_time_days,
            "inventory_capacity": state.rules.inventory_capacity,
            "win_net_worth": state.rules.win_net_worth,
            "max_days": state.rules.max_days,
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
        "event_log": list(state.event_log),
        "last_loss_value": state.last_loss_value,
    }


def state_from_dict(payload: dict[str, Any]) -> GameState:
    if payload.get("version") != STATE_VERSION:
        raise ValueError("Unsupported state version")

    rules = Rules(
        travel_cost=payload["rules"]["travel_cost"],
        travel_time_days=payload["rules"]["travel_time_days"],
        inventory_capacity=payload["rules"].get("inventory_capacity"),
        win_net_worth=payload["rules"]["win_net_worth"],
        max_days=payload["rules"].get("max_days"),
        daily_event_chance=payload["rules"].get("daily_event_chance", 0.0),
        travel_event_chance=payload["rules"].get("travel_event_chance", 0.0),
        event_log_limit=payload["rules"].get("event_log_limit"),
        daily_event_weights=dict(payload["rules"].get("daily_event_weights", {})),
        travel_event_weights=dict(payload["rules"].get("travel_event_weights", {})),
        city_event_multipliers=dict(payload["rules"].get("city_event_multipliers", {})),
        spoilage_item_multipliers=dict(payload["rules"].get("spoilage_item_multipliers", {})),
    )

    seed = payload.get("seed")
    rng = random.Random(seed)

    market = [
        Item(
            name=item["name"],
            value=item["value"],
            base_value=item["base_value"],
            min_value=item["min_value"],
            max_value=item["max_value"],
            last_value=item["last_value"],
        )
        for item in payload["market"]
    ]

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
