"""Command-line entrypoint for Open Arbitrage (engine-driven)."""

import json

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
    create_default_state,
    state_to_dict,
)

app = typer.Typer(add_completion=False, help="Open Arbitrage game CLI (engine-based loop)")


def render_state(state: GameState, console: Console) -> None:
    summary = Table(title="Position", box=box.SIMPLE)
    summary.add_column("Day", justify="right")
    summary.add_column("City")
    summary.add_column("Cash", justify="right")
    summary.add_column("Loan", justify="right")
    summary.add_column("Status")
    summary.add_row(
        str(state.day),
        state.current_city(),
        f"${state.cash:,.2f}",
        f"${state.loan.balance:,.2f}",
        state.status.value,
    )

    market = Table(title="Market", box=box.SIMPLE)
    market.add_column("Item")
    market.add_column("Price", justify="right")
    for item in state.market:
        market.add_row(item.name, f"${item.value:,.2f}")

    inv = Table(title="Inventory", box=box.SIMPLE)
    inv.add_column("Item")
    inv.add_column("Qty", justify="right")
    if not state.inventory.holdings:
        inv.add_row("-", "0")
    else:
        for name, qty in state.inventory.holdings.items():
            inv.add_row(name, str(qty))

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


def _format_event_details(details: dict[str, object]) -> str:
    parts = []
    for key, value in details.items():
        parts.append(f"{key}={value}")
    return ", ".join(parts)


@app.command()
def play(
    seed: int | None = typer.Option(
        None,
        "--seed",
        "-s",
        help="Random seed",
    ),
    travel_cost: float = typer.Option(
        50.0,
        "--travel-cost",
        help="Travel cost per trip",
    ),
    win_net_worth: float = typer.Option(
        20_000.0,
        "--win-net-worth",
        help="Net worth needed to win",
    ),
    max_days: int | None = typer.Option(
        365,
        "--max-days",
        help="Max days before auto-outcome",
    ),
) -> None:
    """Play an interactive loop against the engine."""

    console = Console()
    rules = Rules(travel_cost=travel_cost, win_net_worth=win_net_worth, max_days=max_days)
    state = create_default_state(seed=seed, rules=rules)

    console.print("[bold cyan]Welcome to Open Arbitrage (engine mode)![/bold cyan]")

    actions = "[b]uy, [s]ell, [t]ravel, [r]epay, a[d]vance day, [q]uit"

    while True:
        render_state(state, console)
        if state.status is not GameOutcome.ONGOING:
            console.print(f"[green]Game finished: {state.status.value}[/green]")
            break

        choice = typer.prompt(f"Choose action ({actions})", default="d").strip().lower()

        try:
            if choice == "b":
                item_name = typer.prompt("Item name")
                qty = int(typer.prompt("Quantity", default="1"))
                apply_command(state, Buy(item_name=item_name, quantity=qty))
            elif choice == "s":
                item_name = typer.prompt("Item name")
                qty = int(typer.prompt("Quantity", default="1"))
                apply_command(state, Sell(item_name=item_name, quantity=qty))
            elif choice == "t":
                console.print("Cities:")
                for idx, city in enumerate(state.cities):
                    console.print(f"  [{idx}] {city}")
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
