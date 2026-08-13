import os

import pytest

from src.tools.config_assistant.config_manager import config_manager
from src.tools.config_assistant.server import create_app

CONFIG_GAMES_DIR = config_manager.games_dir


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

    config_path = os.path.join(CONFIG_GAMES_DIR, "test_rules_game.yaml")
    if os.path.exists(config_path):
        os.remove(config_path)


@pytest.fixture
def game_with_config(client):
    game_name = "test_rules_game"
    client.post("/api/game/create", json={"game_name": game_name})
    yield game_name


def test_get_rules_empty(client, game_with_config):
    rv = client.get(f"/api/config/{game_with_config}/rules")

    assert rv.status_code == 200
    data = rv.get_json()
    assert "rules" in data
    assert data["rules"] == []


def test_get_rules_not_found(client):
    rv = client.get("/api/config/nonexistent_game_xyz/rules")

    assert rv.status_code == 404


def test_put_rules_success(client, game_with_config):
    rules = [
        {"name": "yolo_and_color", "enabled": True, "require": ["yolo", "color"]},
        {"name": "ocr_only", "enabled": False, "require": ["ocr"]},
    ]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 200
    data = rv.get_json()
    assert data["message"] == "Rules updated"
    assert "config" in data
    assert data["config"]["detection"]["rules"] == rules


def test_put_rules_returns_full_config(client, game_with_config):
    rules = [{"name": "test_rule", "enabled": True, "require": ["template"]}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 200
    data = rv.get_json()
    config = data["config"]
    assert "detection" in config
    assert "rules" in config["detection"]


def test_put_rules_not_found(client):
    rules = [{"name": "test", "enabled": True, "require": ["yolo"]}]

    rv = client.put("/api/config/nonexistent_game_xyz/rules", json={"rules": rules})

    assert rv.status_code == 404


def test_put_rules_missing_rules_field(client, game_with_config):
    rv = client.put(f"/api/config/{game_with_config}/rules", json={"other": "data"})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "error" in data


def test_put_rules_validation_not_list(client, game_with_config):
    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": "not a list"})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "detection.rules must be a list" in data["error"]


def test_put_rules_validation_empty_require(client, game_with_config):
    rules = [{"name": "empty_rule", "enabled": True, "require": []}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "require cannot be empty" in data["error"]


def test_put_rules_validation_invalid_signal(client, game_with_config):
    rules = [{"name": "bad_signal", "enabled": True, "require": ["yolo", "invalid_signal"]}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "unknown signal 'invalid_signal'" in data["error"]


def test_put_rules_validation_duplicate_name(client, game_with_config):
    rules = [
        {"name": "same_name", "enabled": True, "require": ["yolo"]},
        {"name": "same_name", "enabled": False, "require": ["ocr"]},
    ]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "duplicate name 'same_name'" in data["error"]


def test_put_rules_validation_missing_name(client, game_with_config):
    rules = [{"enabled": True, "require": ["yolo"]}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "name is required" in data["error"]


def test_put_rules_validation_missing_enabled(client, game_with_config):
    rules = [{"name": "test", "require": ["yolo"]}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "enabled is required" in data["error"]


def test_put_rules_validation_enabled_must_be_real_bool(client, game_with_config):
    """The rules API keeps requiring real booleans even though the typed view is string-aware."""
    rules = [{"name": "str_false", "enabled": "false", "require": ["yolo"]}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "enabled must be a boolean" in data["error"]


def test_put_rules_validation_missing_require(client, game_with_config):
    rules = [{"name": "test", "enabled": True}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 400
    data = rv.get_json()
    assert "require is required" in data["error"]


def test_put_rules_all_valid_signals(client, game_with_config):
    rules = [{"name": "all_signals", "enabled": True, "require": ["ocr", "template", "color", "yolo"]}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})

    assert rv.status_code == 200
    data = rv.get_json()
    assert data["config"]["detection"]["rules"][0]["require"] == ["ocr", "template", "color", "yolo"]


def test_get_rules_after_put(client, game_with_config):
    rules = [{"name": "persisted_rule", "enabled": True, "require": ["color"]}]

    rv = client.put(f"/api/config/{game_with_config}/rules", json={"rules": rules})
    assert rv.status_code == 200

    rv = client.get(f"/api/config/{game_with_config}/rules")

    assert rv.status_code == 200
    data = rv.get_json()
    assert data["rules"] == rules
