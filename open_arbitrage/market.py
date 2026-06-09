"""Market model: a goods catalog plus independent per-city price dynamics.

The market is what makes *arbitrage* possible: every city quotes its own price
for every good, so a trader can buy where a good is cheap and sell where it is
dear. Prices follow a bounded, mean-reverting random walk in log space, which
keeps them strictly positive, anchored to a city-specific long-run mean, and
deterministic for a given seeded RNG.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp, log
from random import Random


@dataclass
class Good:
    """A tradeable commodity in the global catalog."""

    name: str
    base_value: float
    min_value: float = 0.0
    max_value: float = 0.0

    def __post_init__(self) -> None:
        if self.base_value <= 0:
            raise ValueError("Good base_value must be positive")
        if self.min_value <= 0:
            self.min_value = self.base_value * 0.1
        if self.max_value <= 0:
            self.max_value = self.base_value * 4.0
        if not (self.min_value < self.base_value < self.max_value):
            raise ValueError("Good requires min_value < base_value < max_value")


@dataclass
class Quote:
    """A single city's live price for a single good.

    ``base_value`` is the city-specific long-run mean the price reverts toward;
    ``value`` is the current mid price; ``min_value``/``max_value`` are hard
    bounds; ``last_value`` is the previous mid price (for display/deltas).
    """

    good: str
    value: float
    base_value: float
    min_value: float
    max_value: float
    last_value: float = 0.0

    def __post_init__(self) -> None:
        if self.last_value <= 0:
            self.last_value = self.value


@dataclass
class Market:
    """The full market: a goods catalog and one quote board per city.

    ``boards[city_index][good_index]`` aligns with the engine's ``cities`` tuple
    and ``goods`` catalog.
    """

    goods: list[Good]
    boards: list[list[Quote]]

    def good_names(self) -> list[str]:
        return [good.name for good in self.goods]

    def board(self, city_index: int) -> list[Quote]:
        if city_index < 0 or city_index >= len(self.boards):
            raise ValueError("Invalid city index")
        return self.boards[city_index]

    def quote(self, city_index: int, good_name: str) -> Quote:
        for quote in self.board(city_index):
            if quote.good == good_name:
                return quote
        raise ValueError(f"Unknown good: {good_name}")

    def fluctuate(self, rng: Random, *, reversion: float, volatility: float) -> None:
        """Advance every city's prices by one step (the whole world moves)."""
        for board in self.boards:
            for quote in board:
                _step_quote(quote, rng, reversion=reversion, volatility=volatility)


def _step_quote(quote: Quote, rng: Random, *, reversion: float, volatility: float) -> None:
    """Bounded, mean-reverting geometric step.

    ``log(next) = log(value) + reversion * (log(base) - log(value)) + N(0, vol)``

    The drift term pulls the price back toward its city base; the Gaussian shock
    injects noise. The result is clamped to ``[min_value, max_value]``.
    """
    quote.last_value = quote.value
    drift = reversion * (log(quote.base_value) - log(quote.value))
    shock = rng.gauss(0.0, volatility)
    candidate = exp(log(quote.value) + drift + shock)
    quote.value = min(max(candidate, quote.min_value), quote.max_value)


def build_market(
    goods: Sequence[Good],
    cities: Sequence[str],
    rng: Random,
    *,
    city_price_spread: tuple[float, float] = (0.7, 1.3),
) -> Market:
    """Construct a market with a distinct, seed-derived price profile per city.

    Each (city, good) pair gets a base price equal to the good's global base
    scaled by a per-pair factor drawn from ``city_price_spread``. These
    persistent differences are what create durable arbitrage opportunities;
    daily fluctuation then layers noise on top.
    """
    low, high = city_price_spread
    if not (0 < low <= high):
        raise ValueError("city_price_spread must satisfy 0 < low <= high")

    boards: list[list[Quote]] = []
    for _ in cities:
        board: list[Quote] = []
        for good in goods:
            factor = rng.uniform(low, high)
            base = good.base_value * factor
            board.append(
                Quote(
                    good=good.name,
                    value=base,
                    base_value=base,
                    min_value=good.min_value * factor,
                    max_value=good.max_value * factor,
                )
            )
        boards.append(board)
    return Market(goods=list(goods), boards=boards)
