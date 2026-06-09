from pathlib import Path

from fastapi.testclient import TestClient

from open_arbitrage import api
from open_arbitrage.api import GameStore, app

client = TestClient(app)


def _create(**overrides) -> str:
    resp = client.post("/games", json=overrides)
    assert resp.status_code == 201
    return resp.json()["game_id"]


def test_create_and_get_game():
    resp = client.post("/games", json={"seed": 42})
    assert resp.status_code == 201
    body = resp.json()
    game_id = body["game_id"]
    assert body["state"]["seed"] == 42
    assert body["state"]["day"] == 0

    resp = client.get(f"/games/{game_id}")
    assert resp.status_code == 200
    assert resp.json()["seed"] == 42


def test_games_are_isolated():
    a = _create(seed=1)
    b = _create(seed=2)
    assert a != b

    client.post("/games/" + a + "/commands", json={"type": "advance_day", "args": {"days": 3}})
    state_a = client.get(f"/games/{a}").json()
    state_b = client.get(f"/games/{b}").json()
    assert state_a["day"] == 3
    assert state_b["day"] == 0

    listing = client.get("/games").json()["games"]
    assert a in listing and b in listing


def test_create_overrides_rules():
    resp = client.post(
        "/games",
        json={
            "seed": 123,
            "travel_cost": 10.0,
            "trade_spread": 0.05,
            "inventory_capacity": 7,
            "win_net_worth": 5_000.0,
            "max_days": 5,
        },
    )
    assert resp.status_code == 201
    rules = resp.json()["state"]["rules"]
    assert rules["travel_cost"] == 10.0
    assert rules["trade_spread"] == 0.05
    assert rules["inventory_capacity"] == 7
    assert rules["win_net_worth"] == 5_000.0
    assert rules["max_days"] == 5


def test_buy_command_via_api():
    game_id = _create(seed=1)
    resp = client.post(
        f"/games/{game_id}/commands",
        json={"type": "buy", "args": {"good_name": "coffee", "quantity": 1}},
    )
    assert resp.status_code == 200
    assert resp.json()["inventory"]["holdings"]["coffee"] == 1


def test_all_command_types_execute():
    game_id = _create(seed=3)
    for payload in (
        {"type": "buy", "args": {"good_name": "coffee", "quantity": 1}},
        {"type": "repay", "args": {"amount": 1}},
        {"type": "sell", "args": {"good_name": "coffee", "quantity": 1}},
        {"type": "travel", "args": {"destination_index": 0}},
        {"type": "advance_day", "args": {"days": 1}},
    ):
        resp = client.post(f"/games/{game_id}/commands", json=payload)
        assert resp.status_code == 200, payload


def test_command_validation_errors():
    game_id = _create(seed=2)
    resp = client.post(f"/games/{game_id}/commands", json={"type": "buy", "args": {}})
    assert resp.status_code == 400 and "good_name" in resp.json()["detail"]

    resp = client.post(f"/games/{game_id}/commands", json={"type": "sell", "args": {}})
    assert resp.status_code == 400 and "good_name" in resp.json()["detail"]

    resp = client.post(f"/games/{game_id}/commands", json={"type": "unknown", "args": {}})
    assert resp.status_code == 400 and "Unsupported" in resp.json()["detail"]

    resp = client.post(
        f"/games/{game_id}/commands",
        json={"type": "buy", "args": {"good_name": "coffee", "quantity": 0}},
    )
    assert resp.status_code == 400 and "positive" in resp.json()["detail"].lower()


def test_unknown_game_returns_404():
    assert client.get("/games/does-not-exist").status_code == 404
    assert client.delete("/games/does-not-exist").status_code == 404
    resp = client.post("/games/does-not-exist/commands", json={"type": "advance_day", "args": {}})
    assert resp.status_code == 404


def test_delete_game():
    game_id = _create(seed=9)
    assert client.delete(f"/games/{game_id}").status_code == 204
    assert client.get(f"/games/{game_id}").status_code == 404


def test_event_log_persistence(tmp_path: Path):
    log_path = tmp_path / "events.jsonl"
    store = GameStore(event_log_path=log_path)
    game_id, state = store.create(api.CreateGamePayload(seed=1))
    state.event_log = [{"kind": "demo", "day": 0, "city": "X", "details": {}}]

    store._persist_new_events(game_id, state, previous_len=0)

    contents = log_path.read_text(encoding="utf-8").strip()
    assert '"kind": "demo"' in contents
    assert f'"game_id": "{game_id}"' in contents


def test_event_log_persistence_no_path_or_no_events(tmp_path: Path):
    # No path configured -> nothing written, no error.
    store = GameStore(event_log_path=None)
    game_id, state = store.create(api.CreateGamePayload(seed=1))
    state.event_log = [{"kind": "demo", "day": 0, "city": "X", "details": {}}]
    store._persist_new_events(game_id, state, previous_len=0)

    # Path configured but no new events -> file not created.
    log_path = tmp_path / "noop.jsonl"
    store2 = GameStore(event_log_path=log_path)
    game_id2, state2 = store2.create(api.CreateGamePayload(seed=1))
    store2._persist_new_events(game_id2, state2, previous_len=0)
    assert not log_path.exists()
