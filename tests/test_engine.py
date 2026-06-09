import random

import pytest

from open_arbitrage.engine import (
    AdvanceDay,
    Buy,
    GameOutcome,
    Inventory,
    LoanAccount,
    RepayLoan,
    Rules,
    Sell,
    SetSeed,
    Travel,
    apply_command,
    ask_price,
    bid_price,
    create_default_state,
    net_worth,
    state_from_dict,
    state_to_dict,
)
from open_arbitrage.engine.core import (
    _apply_daily_event,
    _apply_travel_event,
    _ensure_ongoing,
    _evaluate_outcome,
    _event_creditor_call,
    _event_customs_fine,
    _event_spoilage,
    _event_theft,
    _mid_price,
    _weighted_choice,
)

DAILY_EVENTS = [
    "demand_spike",
    "cash_windfall",
    "market_shock",
    "theft",
    "spoilage",
    "creditor_call",
    "insurance_payout",
]


def only_daily(event: str) -> dict[str, float]:
    weights = dict.fromkeys(DAILY_EVENTS, 0.0)
    weights[event] = 1.0
    return weights


# --- Core trading ---------------------------------------------------------


def test_buy_uses_ask_and_sell_uses_bid():
    rules = Rules(daily_event_chance=0.0, trade_spread=0.1)
    state = create_default_state(seed=1, rules=rules)
    mid = _mid_price(state, "coffee")

    assert ask_price(state, "coffee") == pytest.approx(mid * 1.1)
    assert bid_price(state, "coffee") == pytest.approx(mid * 0.9)

    cash0 = state.cash
    apply_command(state, Buy(good_name="coffee", quantity=2))
    assert state.inventory.quantity("coffee") == 2
    assert state.cash == pytest.approx(cash0 - mid * 1.1 * 2)

    apply_command(state, Sell(good_name="coffee", quantity=1))
    assert state.inventory.quantity("coffee") == 1
    assert state.cash == pytest.approx(cash0 - mid * 1.1 * 2 + mid * 0.9)


def test_cities_have_distinct_prices_enabling_arbitrage():
    state = create_default_state(seed=3)
    prices = [state.market.quote(i, "coffee").value for i in range(len(state.cities))]
    assert max(prices) > min(prices)


def test_travel_advances_day_changes_city_and_costs_cash():
    state = create_default_state(seed=2)
    cash0 = state.cash
    apply_command(state, Travel(destination_index=1))
    assert state.city_index == 1
    assert state.day == state.rules.travel_time_days
    assert state.cash == pytest.approx(cash0 - state.rules.travel_cost)


def test_advance_day_compounds_loan_and_moves_prices():
    rules = Rules(daily_event_chance=0.0)
    state = create_default_state(seed=3, rules=rules)
    starting_loan = state.loan.balance
    before = [q.value for q in state.market.board(state.city_index)]

    apply_command(state, AdvanceDay(days=2))

    assert state.day == 2
    assert state.loan.balance > starting_loan
    after = [q.value for q in state.market.board(state.city_index)]
    assert any(a != b for a, b in zip(after, before, strict=True))


def test_advance_day_rejects_non_positive():
    state = create_default_state(seed=3)
    with pytest.raises(ValueError):
        apply_command(state, AdvanceDay(days=0))
    with pytest.raises(ValueError):
        apply_command(state, AdvanceDay(days=-2))


def test_repay_loan_reduces_balance_and_cash():
    state = create_default_state(seed=4)
    cash0 = state.cash
    apply_command(state, RepayLoan(amount=50))
    assert state.loan.balance == 10_000.0 - 50
    assert state.cash == cash0 - 50


def test_buy_validation_insufficient_cash():
    state = create_default_state(seed=5)
    with pytest.raises(ValueError, match="Insufficient cash"):
        apply_command(state, Buy(good_name="watches", quantity=10_000))


def test_inventory_capacity_limit():
    state = create_default_state(seed=6, rules=Rules(inventory_capacity=1))
    with pytest.raises(ValueError, match="capacity"):
        apply_command(state, Buy(good_name="coffee", quantity=2))


def test_win_condition_on_net_worth():
    state = create_default_state(seed=7)
    state.cash = 30_000.0
    apply_command(state, RepayLoan(amount=10_000.0))
    assert state.status is GameOutcome.WON


def test_loss_when_loan_exceeds_max():
    state = create_default_state(seed=8)
    state.loan.balance = state.loan.max_balance + 1
    apply_command(state, AdvanceDay(days=1))
    assert state.status is GameOutcome.LOST


def test_net_worth_uses_bid_value_of_inventory():
    rules = Rules(daily_event_chance=0.0, trade_spread=0.05)
    state = create_default_state(seed=2, rules=rules)
    state.cash = 0.0
    state.loan.balance = 0.0
    state.inventory.holdings = {"coffee": 4}
    assert net_worth(state) == pytest.approx(bid_price(state, "coffee") * 4)


# --- Serialization & determinism -----------------------------------------


def test_state_serialization_is_fully_deterministic():
    s1 = create_default_state(seed=9)
    apply_command(s1, Buy(good_name="coffee", quantity=1))
    apply_command(s1, Travel(destination_index=1))
    apply_command(s1, AdvanceDay(days=2))

    s2 = state_from_dict(state_to_dict(s1))
    assert state_to_dict(s1) == state_to_dict(s2)

    # Continuing play after a round-trip must match continuing without one.
    apply_command(s1, AdvanceDay(days=3))
    apply_command(s2, AdvanceDay(days=3))
    assert state_to_dict(s1) == state_to_dict(s2)


def test_state_from_dict_falls_back_to_seed_when_no_rng_state():
    state = create_default_state(seed=15)
    payload = state_to_dict(state)
    payload["rng_state"] = None
    restored = state_from_dict(payload)
    assert restored.rng.random() == pytest.approx(random.Random(15).random())


def test_state_from_dict_handles_missing_seed_and_rng_state():
    state = create_default_state(seed=None)
    payload = state_to_dict(state)
    payload["rng_state"] = None
    restored = state_from_dict(payload)  # should not raise
    assert restored.seed is None


def test_state_from_dict_version_guard():
    payload = state_to_dict(create_default_state(seed=15))
    payload["version"] = 999
    with pytest.raises(ValueError):
        state_from_dict(payload)


# --- Events ---------------------------------------------------------------


def test_daily_event_demand_spike_modifies_current_city():
    rules = Rules(daily_event_chance=1.0, daily_event_weights=only_daily("demand_spike"))
    state = create_default_state(seed=10, rules=rules)
    apply_command(state, AdvanceDay(days=1))

    event = state.event_log[-1]
    assert event["kind"] == "demand_spike"
    good = event["details"]["good"]
    assert event["details"]["after_value"] >= event["details"]["before_value"]
    assert state.market.quote(state.city_index, good).value == event["details"]["after_value"]


def test_travel_weather_delay_increases_days():
    rules = Rules(
        travel_event_chance=1.0,
        travel_event_weights={"weather_delay": 1.0, "customs_fine": 0.0},
    )
    state = create_default_state(seed=11, rules=rules)
    apply_command(state, Travel(destination_index=1))

    event = state.event_log[-1]
    assert event["kind"] == "weather_delay"
    assert state.day == rules.travel_time_days + event["details"]["delay_days"]


def test_cash_windfall_event_increases_cash():
    rules = Rules(daily_event_chance=1.0, daily_event_weights=only_daily("cash_windfall"))
    state = create_default_state(seed=12, rules=rules)
    cash0 = state.cash
    apply_command(state, AdvanceDay(days=1))
    event = state.event_log[-1]
    assert event["kind"] == "cash_windfall"
    assert state.cash == cash0 + event["details"]["amount"]


def test_creditor_call_pays_down_loan():
    rules = Rules(daily_event_chance=1.0, daily_event_weights=only_daily("creditor_call"))
    state = create_default_state(seed=13, rules=rules)
    loan0, cash0 = state.loan.balance, state.cash
    apply_command(state, AdvanceDay(days=1))
    event = state.event_log[-1]
    assert event["kind"] == "creditor_call"
    paid = event["details"]["paid"]
    assert state.loan.balance == pytest.approx((loan0 - paid) * (1 + state.loan.rate))
    assert state.cash == cash0 - paid


def test_spoilage_reduces_inventory():
    rules = Rules(daily_event_chance=1.0, daily_event_weights=only_daily("spoilage"))
    state = create_default_state(seed=14, rules=rules)
    state.inventory.holdings = {"coffee": 5}
    apply_command(state, AdvanceDay(days=1))
    event = state.event_log[-1]
    assert event["kind"] == "spoilage"
    assert state.inventory.quantity("coffee") == 5 - event["details"]["removed"]


def test_market_shock_multiplies_all_city_prices():
    # Freeze the daily walk so the shock multiplier is the only price change.
    rules = Rules(
        daily_event_chance=1.0,
        daily_event_weights=only_daily("market_shock"),
        price_reversion=0.0,
        price_volatility=0.0,
    )
    state = create_default_state(seed=15, rules=rules)
    before = [[q.value for q in board] for board in state.market.boards]
    apply_command(state, AdvanceDay(days=1))

    event = state.event_log[-1]
    assert event["kind"] == "market_shock"
    assert event["details"]["scope"] == "global"
    multiplier = event["details"]["multiplier"]
    for board, before_board in zip(state.market.boards, before, strict=True):
        for quote, before_value in zip(board, before_board, strict=True):
            expected = min(max(before_value * multiplier, quote.min_value), quote.max_value)
            assert quote.value == pytest.approx(expected)


def test_insurance_payout_uses_last_loss():
    rules = Rules(daily_event_chance=1.0, daily_event_weights=only_daily("insurance_payout"))
    state = create_default_state(seed=16, rules=rules)
    state.last_loss_value = 500.0
    cash0 = state.cash
    apply_command(state, AdvanceDay(days=1))
    event = state.event_log[-1]
    assert event["kind"] == "insurance_payout"
    assert state.cash == cash0 + event["details"]["payout"]
    assert state.last_loss_value == 0.0


def test_customs_fine_applied_on_travel():
    rules = Rules(
        travel_event_chance=1.0,
        travel_event_weights={"customs_fine": 1.0, "weather_delay": 0.0},
    )
    state = create_default_state(seed=17, rules=rules)
    cash0 = state.cash
    apply_command(state, Travel(destination_index=1))
    event = state.event_log[-1]
    assert event["kind"] == "customs_fine"
    fine = event["details"]["fine"]
    added = event["details"]["added_to_loan"]
    assert state.cash >= 0
    assert state.cash == pytest.approx(cash0 - state.rules.travel_cost - fine + added)


def test_event_invariants_over_simulation():
    rules = Rules(daily_event_chance=1.0, travel_event_chance=1.0)
    for seed in (21, 22, 23):
        state = create_default_state(seed=seed, rules=rules)
        for _ in range(5):
            apply_command(state, AdvanceDay(days=1))
            assert state.cash >= 0
            assert state.loan.balance >= 0
            assert all(qty >= 0 for qty in state.inventory.holdings.values())
            assert state.status in tuple(GameOutcome)
            if state.status is not GameOutcome.ONGOING:
                break


def test_golden_state_sequence_is_stable_with_seed():
    rules = Rules(daily_event_chance=0.0, travel_event_chance=0.0)
    state = create_default_state(seed=99, rules=rules)
    apply_command(state, AdvanceDay(days=1))
    apply_command(state, Buy(good_name="coffee", quantity=1))
    apply_command(state, Travel(destination_index=1))
    apply_command(state, AdvanceDay(days=2))

    payload = state_to_dict(state)
    assert payload["day"] == 1 + state.rules.travel_time_days + 2
    assert payload["city_index"] == 1
    assert payload["inventory"]["holdings"].get("coffee") == 1
    assert payload["status"] == GameOutcome.ONGOING.value


# --- Component / branch coverage ------------------------------------------


def test_inventory_validation_branches():
    inventory = Inventory(capacity=1)
    inventory.add("x", 0)  # no-op
    inventory.add("x", 1)
    inventory.remove("x", 1)
    assert inventory.holdings == {}

    with pytest.raises(ValueError):
        inventory.add("x", -1)
    with pytest.raises(ValueError):
        inventory.remove("x", -1)
    with pytest.raises(ValueError):
        inventory.remove("x", 1)


def test_loan_repay_requires_positive_amount():
    loan = LoanAccount(balance=100.0, rate=0.01, max_balance=200.0)
    with pytest.raises(ValueError):
        loan.repay(0)


def test_set_seed_and_invalid_good():
    state = create_default_state(seed=1)
    apply_command(state, SetSeed(seed=123))
    assert state.seed == 123
    assert state.rng.random() == pytest.approx(random.Random(123).random())

    with pytest.raises(ValueError):
        apply_command(state, Buy(good_name="unobtainium", quantity=1))


def test_travel_validations():
    state = create_default_state(seed=2)
    with pytest.raises(ValueError):
        apply_command(state, Travel(destination_index=-1))

    start = state.city_index
    apply_command(state, Travel(destination_index=start))  # no-op
    assert state.city_index == start

    state.cash = state.rules.travel_cost - 1
    with pytest.raises(ValueError):
        apply_command(state, Travel(destination_index=1))


def test_buy_sell_repay_validations_and_unsupported_command():
    state = create_default_state(seed=3)
    with pytest.raises(ValueError):
        apply_command(state, Buy(good_name="coffee", quantity=0))
    with pytest.raises(ValueError):
        apply_command(state, Sell(good_name="coffee", quantity=0))
    with pytest.raises(ValueError):
        apply_command(state, Sell(good_name="coffee", quantity=1))
    with pytest.raises(ValueError):
        apply_command(state, RepayLoan(amount=0))
    with pytest.raises(ValueError):
        apply_command(state, RepayLoan(amount=state.cash + 1))
    with pytest.raises(ValueError):
        apply_command(state, "noop")  # type: ignore[arg-type]


def test_weighted_choice_branches():
    assert _weighted_choice({}, random.Random(0)) is None

    class OutOfRangeRng:
        def uniform(self, a: float, b: float) -> float:  # pragma: no cover - trivial
            return b + 1.0

    assert _weighted_choice({"a": 1.0}, OutOfRangeRng()) is None


def test_apply_daily_and_travel_event_guard_paths():
    state = create_default_state(seed=4, rules=Rules(daily_event_chance=1.0))
    state.rules.city_event_multipliers = {state.current_city(): 0.0}
    _apply_daily_event(state)
    assert state.event_log == []

    state.rules.city_event_multipliers = {state.current_city(): 1.0}
    state.rules.daily_event_weights = {}
    _apply_daily_event(state)
    assert state.event_log == []

    no_weights = create_default_state(
        seed=5, rules=Rules(travel_event_chance=1.0, travel_event_weights={})
    )
    assert _apply_travel_event(no_weights) == 0

    unknown_weight = create_default_state(
        seed=6, rules=Rules(travel_event_chance=1.0, travel_event_weights={"other": 1.0})
    )
    assert _apply_travel_event(unknown_weight) == 0

    disabled = create_default_state(seed=6, rules=Rules(travel_event_chance=0.0))
    assert _apply_travel_event(disabled) == 0


def test_event_theft_and_spoilage_paths():
    state = create_default_state(seed=7)
    state.inventory.holdings = {"coffee": 3}
    _event_theft(state)
    assert state.event_log[-1]["kind"] == "theft"
    assert state.last_loss_value > 0

    empty = create_default_state(seed=8)
    _event_spoilage(empty)
    _event_theft(empty)
    assert empty.event_log == []

    zero_qty = create_default_state(seed=9)
    zero_qty.inventory.holdings = {"coffee": 1, "wine": 0}
    zero_qty.rules.spoilage_item_multipliers = {"coffee": 0.0, "wine": 10.0}
    _event_spoilage(zero_qty)
    assert zero_qty.event_log == []

    no_multipliers = create_default_state(seed=10)
    no_multipliers.rules.spoilage_item_multipliers = {}
    no_multipliers.inventory.holdings = {"coffee": 2}
    _event_spoilage(no_multipliers)
    assert no_multipliers.event_log[-1]["kind"] == "spoilage"


def test_event_creditor_call_with_zero_cash():
    state = create_default_state(seed=10, rules=Rules(daily_event_chance=1.0))
    state.cash = 0.0
    _event_creditor_call(state)
    assert state.event_log[-1]["kind"] == "creditor_call"
    assert state.event_log[-1]["details"]["paid"] == 0.0


def test_customs_fine_with_sufficient_cash():
    state = create_default_state(seed=11)
    state.cash = 1_000.0

    class FixedUniform:
        def uniform(self, a: float, b: float) -> float:  # pragma: no cover - deterministic
            return 150.0

    state.rng = FixedUniform()  # type: ignore[assignment]
    _event_customs_fine(state)
    assert state.cash == 850.0
    assert state.loan.balance == 10_000.0
    assert state.event_log[-1]["details"]["added_to_loan"] == 0.0


def test_customs_fine_with_insufficient_cash_adds_to_loan():
    state = create_default_state(seed=11)
    state.cash = 100.0
    loan0 = state.loan.balance

    class FixedUniform:
        def uniform(self, a: float, b: float) -> float:  # pragma: no cover - deterministic
            return 250.0

    state.rng = FixedUniform()  # type: ignore[assignment]
    _event_customs_fine(state)
    assert state.cash == 0.0
    assert state.loan.balance == loan0 + 150.0
    assert state.event_log[-1]["details"]["added_to_loan"] == 150.0


def test_evaluate_outcome_branches():
    finished = create_default_state(seed=12)
    finished.status = GameOutcome.WON
    _evaluate_outcome(finished)
    assert finished.status is GameOutcome.WON

    win = create_default_state(seed=13, rules=Rules(max_days=0))
    win.cash = win.rules.win_net_worth + win.loan.balance
    _evaluate_outcome(win)
    assert win.status is GameOutcome.WON

    lose = create_default_state(seed=14, rules=Rules(max_days=0))
    lose.cash = 0.0
    _evaluate_outcome(lose)
    assert lose.status is GameOutcome.LOST

    with pytest.raises(ValueError):
        _ensure_ongoing(lose)
