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
    assert "market" in payload
    assert "event_log" in payload


def test_render_state_renders_tables():
    state = create_default_state(seed=1)
    state.inventory.holdings = {"a": 2}
    state.event_log = [
        {"day": 1, "kind": "note", "city": state.current_city(), "details": {"k": "v"}}
    ]
    console = Console(record=True)

    cli.render_state(state, console)

    output = console.export_text()
    assert "Position" in output
    assert "Recent Events" in output


def test_format_event_details_round_trips_dict():
    details = {"foo": 1, "bar": "baz"}
    formatted = cli._format_event_details(details)
    assert "foo=1" in formatted and "bar=baz" in formatted


def test_play_quits_immediately(monkeypatch):
    prompts = iter(["q"])

    def fake_prompt(*_: object, **__: object) -> str:  # pragma: no cover - trivial shim
        return next(prompts)

    monkeypatch.setattr(cli.typer, "prompt", fake_prompt)

    result = runner.invoke(cli.app, ["play", "--seed", "2", "--max-days", "1"])

    assert result.exit_code == 0
    assert "Goodbye" in result.stdout


def test_play_walks_actions(monkeypatch):
    prompts = iter(
        [
            "b",
            "a",
            "0",  # invalid quantity -> error path
            "b",
            "a",
            "1",  # valid buy
            "s",
            "a",
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

    def fake_prompt(*_: object, **__: object) -> str:  # pragma: no cover - deterministic
        return next(prompts, "q")

    monkeypatch.setattr(cli.typer, "prompt", fake_prompt)

    result = runner.invoke(
        cli.app, ["play", "--seed", "3", "--travel-cost", "1", "--max-days", "5"]
    )

    assert result.exit_code == 0
    assert "Unknown command" in result.stdout
    assert "Quantity must be positive" in result.stdout


def test_play_handles_finished_game(monkeypatch):
    finished_state = create_default_state(seed=4)
    finished_state.status = GameOutcome.WON

    monkeypatch.setattr(cli, "create_default_state", lambda **_: finished_state)
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
