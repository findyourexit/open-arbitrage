"""Command-line entrypoint for Open Arbitrage (engine-driven)."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from .engine import (
    AdvanceDay,
    Buy,
    GameOutcome,
    GameState,
    RepayLoan,
    Rules,
    Sell,
    Travel,
    apply_command,
    ask_price,
    bid_price,
    create_default_state,
    net_worth,
    state_to_dict,
)

app = typer.Typer(add_completion=False, help="Open Arbitrage game CLI (engine-based loop)")

_DEFAULTS = Rules()


def _best_alternative_market(state: GameState, good_name: str) -> tuple[str, float] | None:
    """Return the (city, bid) with the highest sell price excluding the current city."""
    best: tuple[str, float] | None = None
    for index, city in enumerate(state.cities):
        if index == state.city_index:
            continue
        quote = state.market.quote(index, good_name)
        bid = quote.value * (1.0 - state.rules.trade_spread)
        if best is None or bid > best[1]:
            best = (city, bid)
    return best


def render_state(state: GameState, console: Console) -> None:
    summary = Table(title="Position", box=box.SIMPLE)
    summary.add_column("Day", justify="right")
    summary.add_column("City")
    summary.add_column("Cash", justify="right")
    summary.add_column("Loan", justify="right")
    summary.add_column("Net Worth", justify="right")
    summary.add_column("Status")
    summary.add_row(
        str(state.day),
        state.current_city(),
        f"${state.cash:,.2f}",
        f"${state.loan.balance:,.2f}",
        f"${net_worth(state):,.2f}",
        state.status.value,
    )

    market = Table(title=f"Market — {state.current_city()}", box=box.SIMPLE)
    market.add_column("Good")
    market.add_column("Buy (ask)", justify="right")
    market.add_column("Sell (bid)", justify="right")
    for good_name in state.market.good_names():
        market.add_row(
            good_name,
            f"${ask_price(state, good_name):,.2f}",
            f"${bid_price(state, good_name):,.2f}",
        )

    inv = Table(title="Inventory", box=box.SIMPLE)
    inv.add_column("Good")
    inv.add_column("Qty", justify="right")
    inv.add_column("Sell here", justify="right")
    inv.add_column("Best elsewhere")
    if not state.inventory.holdings:
        inv.add_row("-", "0", "-", "-")
    else:
        for name, qty in state.inventory.holdings.items():
            alt = _best_alternative_market(state, name)
            alt_text = f"{alt[0]} ${alt[1]:,.2f}" if alt else "-"
            inv.add_row(name, str(qty), f"${bid_price(state, name) * qty:,.2f}", alt_text)

    console.print(summary)
    console.print(market)
    console.print(inv)

    if state.event_log:
        events = Table(title="Recent Events", box=box.SIMPLE)
        events.add_column("Day", justify="right")
        events.add_column("Kind")
        events.add_column("City")
        events.add_column("Details")
        for event in state.event_log[-5:]:
            events.add_row(
                str(event["day"]),
                event["kind"],
                event.get("city", state.current_city()),
                _format_event_details(event.get("details", {})),
            )
        console.print(events)


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _format_event_details(details: dict[str, Any]) -> str:
    return ", ".join(f"{key}={_format_value(value)}" for key, value in details.items())


@app.command()
def play(
    seed: int | None = typer.Option(None, "--seed", "-s", help="Random seed"),
    travel_cost: float = typer.Option(
        _DEFAULTS.travel_cost, "--travel-cost", help="Travel cost per trip"
    ),
    spread: float = typer.Option(
        _DEFAULTS.trade_spread, "--spread", help="Half-spread applied to buys/sells"
    ),
    inventory_capacity: int = typer.Option(
        _DEFAULTS.inventory_capacity or 100, "--capacity", help="Inventory capacity"
    ),
    win_net_worth: float = typer.Option(
        _DEFAULTS.win_net_worth, "--win-net-worth", help="Net worth needed to win"
    ),
    max_days: int | None = typer.Option(
        _DEFAULTS.max_days, "--max-days", help="Max days before auto-outcome"
    ),
) -> None:
    """Play an interactive loop against the engine."""

    console = Console()
    rules = Rules(
        travel_cost=travel_cost,
        trade_spread=spread,
        inventory_capacity=inventory_capacity,
        win_net_worth=win_net_worth,
        max_days=max_days,
    )
    state = create_default_state(seed=seed, rules=rules)

    console.print("[bold cyan]Welcome to Open Arbitrage![/bold cyan]")
    console.print("Buy low in one city, sell high in another, beat the loan clock.\n")

    actions = "[b]uy, [s]ell, [t]ravel, [r]epay, a[d]vance day, [q]uit"

    while True:
        render_state(state, console)
        if state.status is not GameOutcome.ONGOING:
            console.print(f"[green]Game finished: {state.status.value}[/green]")
            break

        choice = typer.prompt(f"Choose action ({actions})", default="d").strip().lower()

        try:
            if choice == "b":
                good_name = typer.prompt("Good name")
                qty = int(typer.prompt("Quantity", default="1"))
                apply_command(state, Buy(good_name=good_name, quantity=qty))
            elif choice == "s":
                good_name = typer.prompt("Good name")
                qty = int(typer.prompt("Quantity", default="1"))
                apply_command(state, Sell(good_name=good_name, quantity=qty))
            elif choice == "t":
                console.print("Cities:")
                for idx, city in enumerate(state.cities):
                    marker = " (here)" if idx == state.city_index else ""
                    console.print(f"  [{idx}] {city}{marker}")
                dest = int(typer.prompt("Destination index"))
                apply_command(state, Travel(destination_index=dest))
            elif choice == "r":
                amount = float(typer.prompt("Repay amount"))
                apply_command(state, RepayLoan(amount=amount))
            elif choice == "d":
                days = int(typer.prompt("Days to advance", default="1"))
                apply_command(state, AdvanceDay(days=days))
            elif choice == "q":
                console.print("Goodbye!")
                break
            else:
                console.print("[yellow]Unknown command[/yellow]")
        except ValueError as exc:  # noqa: PERF203 - user-driven errors
            console.print(f"[red]{exc}[/red]")


@app.command()
def dump_state(
    seed: int | None = typer.Option(None, "--seed", "-s", help="Random seed"),
) -> None:
    """Print a fresh game state as JSON for tooling or integration demos."""
    state = create_default_state(seed=seed)
    console = Console()
    console.print_json(json.dumps(state_to_dict(state)))


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover - exercised via CLI entrypoint
    main()
