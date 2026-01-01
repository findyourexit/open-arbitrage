from pathlib import Path

from fastapi.testclient import TestClient

from open_arbitrage import api
from open_arbitrage.api import app

client = TestClient(app)


def test_reset_and_get_state():
    resp = client.post("/reset", json={"seed": 42})
    assert resp.status_code == 200
    data = resp.json()
    assert data["seed"] == 42
    assert data["day"] == 0

    resp = client.get("/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["seed"] == 42
    assert data["day"] == 0


def test_buy_command_via_api():
    client.post("/reset", json={"seed": 1})
    resp = client.post(
        "/command",
        json={
            "type": "buy",
            "args": {"item_name": "a", "quantity": 1},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["inventory"]["holdings"]["a"] == 1


def test_reset_overrides_rules():
    resp = client.post(
        "/reset",
        json={
            "seed": 123,
            "travel_cost": 10.0,
            "win_net_worth": 5_000.0,
            "max_days": 5,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["rules"]["travel_cost"] == 10.0
    assert data["rules"]["win_net_worth"] == 5_000.0
    assert data["rules"]["max_days"] == 5


def test_command_validation_errors():
    resp = client.post("/command", json={"type": "buy", "args": {}})
    assert resp.status_code == 400
    assert "item_name" in resp.json()["detail"]

    resp = client.post("/command", json={"type": "sell", "args": {}})
    assert resp.status_code == 400
    assert "item_name" in resp.json()["detail"]

    resp = client.post("/command", json={"type": "unknown", "args": {}})
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]

    client.post("/reset", json={"seed": 2})
    resp = client.post("/command", json={"type": "buy", "args": {"item_name": "a", "quantity": 0}})
    assert resp.status_code == 400
    assert "positive" in resp.json()["detail"].lower()


def test_all_command_types_execute():
    client.post("/reset", json={"seed": 3})
    buy_resp = client.post(
        "/command",
        json={"type": "buy", "args": {"item_name": "a", "quantity": 1}},
    )
    assert buy_resp.status_code == 200

    repay_resp = client.post(
        "/command",
        json={"type": "repay", "args": {"amount": 1}},
    )
    assert repay_resp.status_code == 200

    sell_resp = client.post(
        "/command",
        json={"type": "sell", "args": {"item_name": "a", "quantity": 1}},
    )
    assert sell_resp.status_code == 200

    travel_resp = client.post(
        "/command",
        json={"type": "travel", "args": {"destination_index": 0}},
    )
    assert travel_resp.status_code == 200

    advance_resp = client.post(
        "/command",
        json={"type": "advance_day", "args": {"days": 1}},
    )
    assert advance_resp.status_code == 200


def test_event_log_persistence(tmp_path: Path):
    log_path = tmp_path / "events.log"
    api._event_log_path = log_path
    api._state.event_log = [{"kind": "demo", "day": 0, "city": "X", "details": {}}]

    api._persist_new_events(previous_len=0)

    assert log_path.exists()
    contents = log_path.read_text(encoding="utf-8").strip()
    assert '"kind": "demo"' in contents

    api._event_log_path = None


def test_event_log_persistence_no_new_events(tmp_path: Path):
    log_path = tmp_path / "noop.log"
    api._event_log_path = log_path
    api._state.event_log = []

    api._persist_new_events(previous_len=0)

    assert not log_path.exists()
    api._event_log_path = None
