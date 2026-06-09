import json

from rich.console import Console
from typer.testing import CliRunner

from open_arbitrage import cli
from open_arbitrage.engine import GameOutcome, create_default_state

runner = CliRunner()


def test_dump_state_outputs_json():
    result = runner.invoke(cli.app, ["dump-state", "--seed", "5"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["seed"] == 5
    assert payload["day"] == 0
    assert payload["version"] == 2
    assert "market" in payload and "boards" in payload["market"]
    assert "rng_state" in payload


def test_render_state_renders_tables_with_arbitrage_hint():
    state = create_default_state(seed=1)
    state.inventory.holdings = {"coffee": 2}
    state.event_log = [
        {"day": 1, "kind": "note", "city": state.current_city(), "details": {"amount": 12.5}}
    ]
    console = Console(record=True, width=200)

    cli.render_state(state, console)

    output = console.export_text()
    assert "Position" in output
    assert "Net Worth" in output
    assert "Best elsewhere" in output
    assert "Recent Events" in output


def test_best_alternative_market_picks_highest_other_city():
    state = create_default_state(seed=1)
    alt = cli._best_alternative_market(state, "coffee")
    assert alt is not None
    city, bid = alt
    assert city != state.current_city()
    assert bid > 0


def test_format_event_details_formats_floats():
    formatted = cli._format_event_details({"amount": 1234.5, "good": "coffee"})
    assert "amount=1,234.50" in formatted
    assert "good=coffee" in formatted


def test_play_quits_immediately(monkeypatch):
    prompts = iter(["q"])
    monkeypatch.setattr(cli.typer, "prompt", lambda *_, **__: next(prompts))
    result = runner.invoke(cli.app, ["play", "--seed", "2", "--max-days", "1"])
    assert result.exit_code == 0
    assert "Goodbye" in result.stdout


def test_play_walks_actions(monkeypatch):
    prompts = iter(
        [
            "b",
            "coffee",
            "0",  # invalid quantity -> error path
            "b",
            "coffee",
            "1",  # valid buy
            "s",
            "coffee",
            "1",  # sell
            "t",
            "1",  # travel
            "r",
            "5",  # repay
            "d",
            "1",  # advance day
            "x",  # unknown
            "q",
        ]
    )
    monkeypatch.setattr(cli.typer, "prompt", lambda *_, **__: next(prompts, "q"))

    result = runner.invoke(
        cli.app,
        ["play", "--seed", "3", "--travel-cost", "1", "--spread", "0.01", "--max-days", "5"],
    )

    assert result.exit_code == 0
    assert "Unknown command" in result.stdout
    assert "Quantity must be positive" in result.stdout


def test_play_handles_finished_game(monkeypatch):
    finished = create_default_state(seed=4)
    finished.status = GameOutcome.WON
    monkeypatch.setattr(cli, "create_default_state", lambda **_: finished)
    monkeypatch.setattr(cli.typer, "prompt", lambda *_, **__: "q")

    result = runner.invoke(cli.app, ["play"])
    assert result.exit_code == 0
    assert "Game finished" in result.stdout


def test_cli_main_entrypoint_runs(monkeypatch):
    invoked: dict[str, bool] = {}

    def fake_app() -> None:  # pragma: no cover - simple stub
        invoked["ran"] = True

    monkeypatch.setattr(cli, "app", fake_app)
    cli.main()
    assert invoked.get("ran") is True
