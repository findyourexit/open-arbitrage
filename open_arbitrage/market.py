"""Market data structures and pricing dynamics."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import exp, sqrt
from random import Random


@dataclass
class Item:
    name: str
    value: float
    base_value: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    last_value: float = 0.0

    def __post_init__(self) -> None:
        self.base_value = self.base_value or self.value
        self.min_value = self.min_value or float(self.base_value * 0.1)
        self.max_value = self.max_value or float(self.base_value * 4.0)
        self.last_value = self.last_value or self.value


def fluctuate_market(market: Iterable[Item], rng: Random | None = None) -> None:
    """Bounded random walk around base value."""
    mu = 0.5
    sigma = mu / 2
    _rng: Random = rng if rng is not None else Random()

    for item in market:
        item.last_value = item.value
        step = _rng.gauss(mu, sigma)
        new_value = item.value

        if step <= 0.5:
            new_value += item.base_value * step
        else:
            new_value += item.base_value * -step

        new_value = (new_value + item.base_value) / 2

        if new_value < item.min_value:
            item.value = item.min_value
        elif new_value > item.max_value:
            item.value = item.max_value
        else:
            item.value = new_value


def fluctuate_market_experimental(market: Iterable[Item], rng: Random | None = None) -> None:
    """Log-normal style movement (geometric Brownian motion)."""
    mu = 0.5
    sigma = mu / 2
    _rng: Random = rng if rng is not None else Random()

    for item in market:
        item.last_value = item.value
        item.value *= exp(
            (mu - 0.5 * sigma**2) * (1.0 / 365.0)
            + sigma * sqrt(1.0 / 365.0) * _rng.gauss(mu=0, sigma=1)
        )


def simulate_market(iterations: int, market: list[Item]) -> list[list[float]]:
    """Return simulated price history for visualization/testing."""
    simulated_history: list[list[float]] = [[] for _ in market]

    for _ in range(iterations):
        fluctuate_market_experimental(market)
        for idx, item in enumerate(market):
            simulated_history[idx].append(item.value)

    return simulated_history


def clone_items(items: Sequence[Item]) -> list[Item]:
    """Return shallow copies with reset dynamic fields."""
    cloned: list[Item] = []
    for item in items:
        cloned.append(
            Item(
                name=item.name,
                value=item.base_value or item.value,
                base_value=item.base_value,
                min_value=item.min_value,
                max_value=item.max_value,
            )
        )
    return cloned
