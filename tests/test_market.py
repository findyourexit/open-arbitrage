from open_arbitrage.market import (
    Item,
    clone_items,
    fluctuate_market,
    fluctuate_market_experimental,
    simulate_market,
)


def test_fluctuate_market_bounds():
    base_items = [Item("x", 10.0), Item("y", 50.0)]
    market = clone_items(base_items)

    fluctuate_market(market)

    for item, base in zip(market, base_items, strict=True):
        assert item.min_value <= item.value <= item.max_value
        assert item.base_value == base.base_value


def test_fluctuate_market_clamps_to_min_and_max():
    low_item = Item("low", value=1.0, base_value=10.0, min_value=9.0, max_value=12.0)
    high_item = Item("high", value=20.0, base_value=10.0, min_value=5.0, max_value=12.0)

    class FallingRng:
        def gauss(self, mu: float, sigma: float) -> float:  # pragma: no cover - trivial
            return 10.0  # Big drop to force min clamp

    class RisingRng:
        def gauss(self, mu: float, sigma: float) -> float:  # pragma: no cover - trivial
            return 0.0  # Mild rise to force max clamp because value already above max

    fluctuate_market([low_item], rng=FallingRng())
    fluctuate_market([high_item], rng=RisingRng())

    assert low_item.value == low_item.min_value
    assert high_item.value == high_item.max_value


def test_fluctuate_market_experimental_tracks_last_value():
    item = Item("exp", value=10.0)

    class FlatRng:
        def gauss(self, mu: float, sigma: float) -> float:  # pragma: no cover - deterministic
            return 0.0

    fluctuate_market_experimental([item], rng=FlatRng())

    assert item.last_value == 10.0
    assert item.value != item.last_value


def test_simulate_market_produces_history_length():
    items = [Item("a", 10.0), Item("b", 20.0)]
    history = simulate_market(iterations=3, market=items)

    assert len(history) == 2
    assert all(len(series) == 3 for series in history)


def test_clone_items_resets_dynamic_fields():
    original = [Item("x", value=5.0, base_value=5.0, min_value=1.0, max_value=6.0)]
    original[0].value = 2.5

    cloned = clone_items(original)

    assert cloned[0].value == original[0].base_value
    assert cloned[0].min_value == original[0].min_value
    assert cloned[0].max_value == original[0].max_value
