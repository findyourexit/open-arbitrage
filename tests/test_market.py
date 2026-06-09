import random

import pytest

from open_arbitrage.market import Good, Market, Quote, _step_quote, build_market

CITIES = ("A", "B", "C")


def _default_goods() -> list[Good]:
    return [Good("coffee", 10.0), Good("watches", 50.0)]


def test_good_defaults_and_validation():
    good = Good("coffee", 10.0)
    assert good.min_value == pytest.approx(1.0)
    assert good.max_value == pytest.approx(40.0)

    with pytest.raises(ValueError):
        Good("bad", 0.0)

    with pytest.raises(ValueError):
        Good("bad", 10.0, min_value=20.0)  # min above base


def test_quote_last_value_defaults_to_value():
    quote = Quote("coffee", value=12.0, base_value=10.0, min_value=1.0, max_value=40.0)
    assert quote.last_value == 12.0


def test_build_market_dimensions_and_distinct_prices():
    rng = random.Random(1)
    market = build_market(_default_goods(), CITIES, rng)

    assert len(market.boards) == len(CITIES)
    assert all(len(board) == 2 for board in market.boards)
    assert market.good_names() == ["coffee", "watches"]

    coffee_prices = {market.quote(i, "coffee").value for i in range(len(CITIES))}
    assert len(coffee_prices) > 1  # cities have genuinely different prices


def test_build_market_is_deterministic_per_seed():
    a = build_market(_default_goods(), CITIES, random.Random(42))
    b = build_market(_default_goods(), CITIES, random.Random(42))
    assert [q.value for board in a.boards for q in board] == [
        q.value for board in b.boards for q in board
    ]


def test_build_market_bounds_scale_with_city_factor():
    market = build_market(_default_goods(), CITIES, random.Random(3))
    for board in market.boards:
        for quote in board:
            # value starts at the city base and bounds bracket it proportionally
            assert quote.value == pytest.approx(quote.base_value)
            assert quote.min_value < quote.base_value < quote.max_value
            assert quote.max_value / quote.min_value == pytest.approx(40.0)


def test_build_market_rejects_bad_spread():
    with pytest.raises(ValueError):
        build_market(_default_goods(), CITIES, random.Random(0), city_price_spread=(0.0, 1.0))


def test_market_quote_and_board_validation():
    market = build_market(_default_goods(), CITIES, random.Random(0))
    with pytest.raises(ValueError):
        market.board(-1)
    with pytest.raises(ValueError):
        market.quote(0, "unobtainium")


def test_fluctuate_keeps_prices_within_bounds():
    rng = random.Random(7)
    market = build_market(_default_goods(), CITIES, rng)
    for _ in range(500):
        market.fluctuate(rng, reversion=0.15, volatility=0.2)
        for board in market.boards:
            for quote in board:
                assert quote.min_value <= quote.value <= quote.max_value


def test_fluctuate_is_deterministic():
    market_a = build_market(_default_goods(), CITIES, random.Random(11))
    market_b = build_market(_default_goods(), CITIES, random.Random(11))
    rng_a, rng_b = random.Random(99), random.Random(99)
    for _ in range(5):
        market_a.fluctuate(rng_a, reversion=0.15, volatility=0.08)
        market_b.fluctuate(rng_b, reversion=0.15, volatility=0.08)
    assert [q.value for board in market_a.boards for q in board] == [
        q.value for board in market_b.boards for q in board
    ]


def test_step_quote_mean_reverts_without_noise():
    class ZeroShock:
        def gauss(self, mu: float, sigma: float) -> float:  # pragma: no cover - trivial
            return 0.0

    quote = Quote("coffee", value=20.0, base_value=10.0, min_value=1.0, max_value=40.0)
    _step_quote(quote, ZeroShock(), reversion=0.5, volatility=0.08)
    assert quote.last_value == 20.0
    assert 10.0 < quote.value < 20.0  # pulled toward base, not overshooting


def test_step_quote_clamps_to_bounds():
    class BigDrop:
        def gauss(self, mu: float, sigma: float) -> float:  # pragma: no cover - trivial
            return -100.0

    class BigRise:
        def gauss(self, mu: float, sigma: float) -> float:  # pragma: no cover - trivial
            return 100.0

    low = Quote("g", value=10.0, base_value=10.0, min_value=5.0, max_value=40.0)
    high = Quote("g", value=10.0, base_value=10.0, min_value=5.0, max_value=12.0)
    _step_quote(low, BigDrop(), reversion=0.1, volatility=0.1)
    _step_quote(high, BigRise(), reversion=0.1, volatility=0.1)
    assert low.value == low.min_value
    assert high.value == high.max_value


def test_market_is_plain_dataclass():
    market = Market(goods=_default_goods(), boards=[])
    assert market.good_names() == ["coffee", "watches"]
