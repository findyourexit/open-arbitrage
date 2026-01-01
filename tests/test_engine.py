import random

import pytest

from open_arbitrage.engine import (
    AdvanceDay,
    Buy,
    GameOutcome,
    RepayLoan,
    Rules,
    Sell,
    SetSeed,
    Travel,
    apply_command,
    create_default_state,
    state_from_dict,
    state_to_dict,
)
from open_arbitrage.engine.core import (
    Inventory,
    LoanAccount,
    _apply_daily_event,
    _apply_travel_event,
    _ensure_ongoing,
    _evaluate_outcome,
    _event_creditor_call,
    _event_customs_fine,
    _event_spoilage,
    _event_theft,
    _weighted_choice,
)


def test_buy_and_sell_flow():
    state = create_default_state(seed=1)
    starting_cash = state.cash

    apply_command(state, Buy(item_name="a", quantity=2))
    assert state.cash == starting_cash - state.market[0].value * 2
    assert state.inventory.quantity("a") == 2

    apply_command(state, Sell(item_name="a", quantity=1))
    assert state.inventory.quantity("a") == 1
    assert state.cash == starting_cash - state.market[0].value * 2 + state.market[0].value


def test_travel_advances_day_and_changes_city():
    state = create_default_state(seed=2)
    starting_cash = state.cash
    apply_command(state, Travel(destination_index=1))
    assert state.city_index == 1
    assert state.day == state.rules.travel_time_days
    assert state.cash == starting_cash - state.rules.travel_cost


def test_advance_day_compounds_loan_and_updates_prices():
    rules = Rules(daily_event_chance=0.0)
    state = create_default_state(seed=3, rules=rules)
    starting_loan = state.loan.balance
    starting_values = [item.value for item in state.market]

    apply_command(state, AdvanceDay(days=2))

    assert state.day == 2
    assert state.loan.balance > starting_loan
    assert any(
        item.value != before for item, before in zip(state.market, starting_values, strict=True)
    )


def test_repay_loan_reduces_balance_and_cash():
    state = create_default_state(seed=4)
    starting_cash = state.cash
    apply_command(state, RepayLoan(amount=50))
    assert state.loan.balance == 10_000.0 - 50
    assert state.cash == starting_cash - 50


def test_buy_validation_insufficient_cash():
    state = create_default_state(seed=5)
    try:
        apply_command(state, Buy(item_name="b", quantity=10_000))
    except ValueError as exc:  # noqa: PERF203 - test expectation
        assert "Insufficient cash" in str(exc)
    else:  # pragma: no cover - test should fail if no exception
        raise AssertionError("Expected ValueError for insufficient cash")


def test_inventory_capacity_limit():
    small_rules = Rules(inventory_capacity=1)
    state = create_default_state(seed=6, rules=small_rules)
    try:
        apply_command(state, Buy(item_name="a", quantity=2))
    except ValueError as exc:  # noqa: PERF203 - test expectation
        assert "capacity" in str(exc).lower()
    else:  # pragma: no cover - test should fail if no exception
        raise AssertionError("Expected ValueError for capacity exceeded")


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


def test_state_serialization_round_trip():
    state = create_default_state(seed=9)
    apply_command(state, Buy(item_name="a", quantity=1))
    apply_command(state, Travel(destination_index=1))

    payload = state_to_dict(state)
    restored = state_from_dict(payload)

    assert restored.day == state.day
    assert restored.city_index == state.city_index
    assert restored.inventory.holdings == state.inventory.holdings
    assert restored.rules.travel_cost == state.rules.travel_cost
    assert restored.event_log == state.event_log


def test_daily_event_demand_spike_is_deterministic():
    rules = Rules(
        daily_event_chance=1.0,
        daily_event_weights={"demand_spike": 1.0, "theft": 0.0},
    )
    state = create_default_state(seed=10, rules=rules)

    apply_command(state, AdvanceDay(days=1))

    assert state.event_log[-1]["kind"] == "demand_spike"
    details = state.event_log[-1]["details"]
    assert details["after_value"] > details["before_value"]
    spiked_item = details["item"]
    new_price = next(item.value for item in state.market if item.name == spiked_item)
    assert new_price == details["after_value"]


def test_travel_weather_delay_increases_days():
    rules = Rules(
        travel_time_days=1,
        travel_event_chance=1.0,
        travel_event_weights={"weather_delay": 1.0},
    )
    state = create_default_state(seed=11, rules=rules)

    apply_command(state, Travel(destination_index=1))

    assert state.event_log[-1]["kind"] == "weather_delay"
    delay = state.event_log[-1]["details"]["delay_days"]
    assert state.day == rules.travel_time_days + delay


def test_cash_windfall_event_increases_cash():
    rules = Rules(
        daily_event_chance=1.0,
        daily_event_weights={
            "cash_windfall": 1.0,
            "demand_spike": 0.0,
            "theft": 0.0,
            "creditor_call": 0.0,
            "spoilage": 0.0,
            "market_shock": 0.0,
            "insurance_payout": 0.0,
        },
    )
    state = create_default_state(seed=12, rules=rules)
    starting_cash = state.cash

    apply_command(state, AdvanceDay(days=1))

    event = state.event_log[-1]
    assert event["kind"] == "cash_windfall"
    amount = event["details"]["amount"]
    assert state.cash == starting_cash + amount
    assert amount > 0


def test_creditor_call_pays_down_loan():
    rules = Rules(
        daily_event_chance=1.0,
        daily_event_weights={
            "creditor_call": 1.0,
            "cash_windfall": 0.0,
            "demand_spike": 0.0,
            "theft": 0.0,
            "spoilage": 0.0,
            "market_shock": 0.0,
            "insurance_payout": 0.0,
        },
    )
    state = create_default_state(seed=13, rules=rules)
    starting_loan = state.loan.balance
    starting_cash = state.cash

    apply_command(state, AdvanceDay(days=1))

    event = state.event_log[-1]
    assert event["kind"] == "creditor_call"
    paid = event["details"]["paid"]
    assert paid <= starting_cash
    expected_loan = (starting_loan - paid) * (1 + state.loan.rate)
    assert state.loan.balance == expected_loan
    assert state.cash == starting_cash - paid


def test_spoilage_reduces_inventory():
    rules = Rules(
        daily_event_chance=1.0,
        daily_event_weights={
            "spoilage": 1.0,
            "cash_windfall": 0.0,
            "demand_spike": 0.0,
            "theft": 0.0,
            "creditor_call": 0.0,
            "market_shock": 0.0,
            "insurance_payout": 0.0,
        },
    )
    state = create_default_state(seed=14, rules=rules)
    state.inventory.holdings = {"a": 5}

    apply_command(state, AdvanceDay(days=1))

    event = state.event_log[-1]
    assert event["kind"] == "spoilage"
    removed = event["details"]["removed"]
    assert state.inventory.quantity("a") == 5 - removed


def test_market_shock_multiplies_prices():
    rules = Rules(
        daily_event_chance=1.0,
        daily_event_weights={
            "market_shock": 1.0,
            "cash_windfall": 0.0,
            "demand_spike": 0.0,
            "theft": 0.0,
            "creditor_call": 0.0,
            "spoilage": 0.0,
            "insurance_payout": 0.0,
        },
    )
    state = create_default_state(seed=15, rules=rules)

    apply_command(state, AdvanceDay(days=1))

    event = state.event_log[-1]
    assert event["kind"] == "market_shock"
    multiplier = event["details"]["multiplier"]
    before_logged = event["details"]["before"]
    after_logged = event["details"]["after"]
    for item in state.market:
        assert after_logged[item.name] == before_logged[item.name] * multiplier


def test_insurance_payout_uses_last_loss():
    rules = Rules(
        daily_event_chance=1.0,
        daily_event_weights={
            "insurance_payout": 1.0,
            "market_shock": 0.0,
            "cash_windfall": 0.0,
            "demand_spike": 0.0,
            "theft": 0.0,
            "creditor_call": 0.0,
            "spoilage": 0.0,
        },
    )
    state = create_default_state(seed=16, rules=rules)
    state.last_loss_value = 500.0
    starting_cash = state.cash

    apply_command(state, AdvanceDay(days=1))

    event = state.event_log[-1]
    assert event["kind"] == "insurance_payout"
    payout = event["details"]["payout"]
    assert state.cash == starting_cash + payout
    assert state.last_loss_value == 0.0


def test_customs_fine_applied_on_travel():
    rules = Rules(
        travel_event_chance=1.0,
        travel_event_weights={
            "customs_fine": 1.0,
            "weather_delay": 0.0,
        },
    )
    state = create_default_state(seed=17, rules=rules)
    starting_cash = state.cash

    apply_command(state, Travel(destination_index=1))

    event = state.event_log[-1]
    assert event["kind"] == "customs_fine"
    fine = event["details"]["fine"]
    added_to_loan = event["details"].get("added_to_loan", 0.0)
    assert state.cash >= 0
    assert state.cash == starting_cash - state.rules.travel_cost - fine + added_to_loan
    assert state.loan.balance >= 10_000.0


def test_event_invariants_over_simulation():
    rules = Rules(daily_event_chance=1.0, travel_event_chance=1.0)
    seeds = [21, 22, 23]

    for seed in seeds:
        state = create_default_state(seed=seed, rules=rules)
        for _ in range(5):
            apply_command(state, AdvanceDay(days=1))
            # invariants
            assert state.cash >= 0
            assert state.loan.balance >= 0
            for qty in state.inventory.holdings.values():
                assert qty >= 0
            assert state.status in (GameOutcome.ONGOING, GameOutcome.WON, GameOutcome.LOST)
            if state.status is not GameOutcome.ONGOING:
                break


def test_golden_state_sequence_is_stable_with_seed():
    rules = Rules(daily_event_chance=0.0, travel_event_chance=0.0)
    state = create_default_state(seed=99, rules=rules)

    apply_command(state, AdvanceDay(days=1))
    apply_command(state, Buy(item_name="a", quantity=1))
    apply_command(state, Travel(destination_index=1))
    apply_command(state, AdvanceDay(days=2))

    payload = state_to_dict(state)
    assert payload["day"] == 1 + state.rules.travel_time_days + 2
    assert payload["city_index"] == 1
    assert payload["inventory"]["holdings"].get("a") == 1
    assert payload["status"] == GameOutcome.ONGOING.value


def test_inventory_validation_branches():
    inventory = Inventory(capacity=1)

    try:
        inventory.add("x", 0)
    except ValueError as exc:  # pragma: no cover - guard
        raise AssertionError(f"Zero add should be a no-op: {exc}") from exc

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


def test_apply_command_set_seed_and_invalid_item():
    state = create_default_state(seed=1)
    apply_command(state, SetSeed(seed=123))
    assert state.seed == 123
    assert state.rng.random() == pytest.approx(random.Random(123).random())

    with pytest.raises(ValueError):
        apply_command(state, Buy(item_name="z", quantity=1))


def test_apply_command_travel_validations():
    state = create_default_state(seed=2)

    with pytest.raises(ValueError):
        apply_command(state, Travel(destination_index=-1))

    start_city = state.city_index
    apply_command(state, Travel(destination_index=start_city))
    assert state.city_index == start_city

    state.cash = state.rules.travel_cost - 1
    with pytest.raises(ValueError):
        apply_command(state, Travel(destination_index=1))


def test_buy_sell_repay_validations():
    state = create_default_state(seed=3)

    with pytest.raises(ValueError):
        apply_command(state, Buy(item_name="a", quantity=0))

    with pytest.raises(ValueError):
        apply_command(state, Sell(item_name="a", quantity=0))

    with pytest.raises(ValueError):
        apply_command(state, Sell(item_name="a", quantity=1))

    with pytest.raises(ValueError):
        apply_command(state, RepayLoan(amount=0))

    with pytest.raises(ValueError):
        apply_command(state, RepayLoan(amount=state.cash + 1))

    with pytest.raises(ValueError):
        apply_command(state, "noop")


def test_weighted_choice_branches():
    rng = random.Random(0)
    assert _weighted_choice({}, rng) is None

    class OutOfRangeRng:
        def uniform(self, a: float, b: float) -> float:  # pragma: no cover - trivial
            return b + 1.0

    assert _weighted_choice({"a": 1.0}, OutOfRangeRng()) is None


def test_apply_daily_and_travel_events_guard_paths():
    state = create_default_state(seed=4, rules=Rules(daily_event_chance=1.0))
    state.rules.city_event_multipliers = {state.current_city(): 0.0}
    _apply_daily_event(state)
    assert state.event_log == []

    state.rules.city_event_multipliers = {state.current_city(): 1.0}
    state.rules.daily_event_weights = {}
    _apply_daily_event(state)
    assert state.event_log == []

    travel_state = create_default_state(
        seed=5, rules=Rules(travel_event_chance=1.0, travel_event_weights={})
    )
    assert _apply_travel_event(travel_state) == 0

    other_travel_state = create_default_state(
        seed=6, rules=Rules(travel_event_chance=1.0, travel_event_weights={"other": 1.0})
    )
    assert _apply_travel_event(other_travel_state) == 0


def test_event_theft_and_spoilage_paths():
    state = create_default_state(seed=7)
    state.inventory.holdings = {"a": 3}
    _event_theft(state)
    assert state.event_log[-1]["kind"] == "theft"
    assert state.last_loss_value > 0

    empty_inventory_state = create_default_state(seed=8)
    _event_spoilage(empty_inventory_state)
    assert empty_inventory_state.event_log == []

    zero_qty_state = create_default_state(seed=9)
    zero_qty_state.inventory.holdings = {"a": 1, "b": 0}
    zero_qty_state.rules.spoilage_item_multipliers = {"a": 0.0, "b": 10.0}
    _event_spoilage(zero_qty_state)
    assert zero_qty_state.event_log == []

    multipliersless_state = create_default_state(seed=10)
    multipliersless_state.rules.spoilage_item_multipliers = {}
    multipliersless_state.inventory.holdings = {"a": 2}
    _event_spoilage(multipliersless_state)
    assert multipliersless_state.event_log[-1]["kind"] == "spoilage"


def test_event_creditor_call_with_zero_cash():
    state = create_default_state(seed=10, rules=Rules(daily_event_chance=1.0))
    state.cash = 0.0
    _event_customs_fine(state)  # prime loss value for insurance payout later
    _event_creditor_call(state)
    assert state.event_log[-1]["kind"] == "creditor_call"
    assert state.event_log[-1]["details"]["paid"] == 0.0


def test_customs_fine_with_sufficient_cash():
    state = create_default_state(seed=11)
    state.cash = 1_000.0

    class FixedUniform:
        def uniform(self, a: float, b: float) -> float:  # pragma: no cover - deterministic
            return 150.0

    state.rng = FixedUniform()
    _event_customs_fine(state)
    assert state.cash == 850.0
    assert state.loan.balance == 10_000.0
    assert state.event_log[-1]["details"]["added_to_loan"] == 0.0


def test_evaluate_outcome_branches():
    finished_state = create_default_state(seed=12)
    finished_state.status = GameOutcome.WON
    _evaluate_outcome(finished_state)
    assert finished_state.status is GameOutcome.WON

    win_state = create_default_state(seed=13, rules=Rules(max_days=0))
    win_state.cash = win_state.rules.win_net_worth + win_state.loan.balance
    _evaluate_outcome(win_state)
    assert win_state.status is GameOutcome.WON

    lose_state = create_default_state(seed=14, rules=Rules(max_days=0))
    lose_state.cash = 0.0
    _evaluate_outcome(lose_state)
    assert lose_state.status is GameOutcome.LOST

    with pytest.raises(ValueError):
        _ensure_ongoing(lose_state)


def test_state_from_dict_version_guard():
    state = create_default_state(seed=15)
    payload = state_to_dict(state)
    payload["version"] = 999
    with pytest.raises(ValueError):
        state_from_dict(payload)
