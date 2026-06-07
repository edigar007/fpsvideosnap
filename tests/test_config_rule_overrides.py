import os
import pytest
import yaml
import json
from src.tools.config_assistant.config_manager import ConfigManager
from src.tools.config_assistant.api import api_bp
from flask import Flask

@pytest.fixture
def temp_project(tmp_path):
    project_root = tmp_path
    config_dir = project_root / "config"
    games_dir = config_dir / "games"
    games_dir.mkdir(parents=True)
    
    # Create a dummy template
    template_path = config_dir / "default_game_template.yaml"
    template_content = {
        "game_name": "{game_name}",
        "detection": {
            "killfeed_roi": [0.1, 0.1, 0.2, 0.2],
            "ocr": {"enabled": True, "keywords": ["kill"], "similarity_threshold": 0.8},
            "templates": {},
            "colors": {},
            "rules": [
                {"name": "rule1", "enabled": True, "require": ["ocr"]}
            ]
        }
    }
    with open(template_path, "w") as f:
        yaml.dump(template_content, f)
        
    return project_root

@pytest.fixture
def config_manager(temp_project):
    return ConfigManager(str(temp_project))

@pytest.fixture
def app(config_manager, temp_project):
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.config['UPLOAD_FOLDER'] = str(temp_project / "uploads")
    
    # We need to monkeypatch the global config_manager in api.py
    # or ensure it uses our instance. 
    # In api.py it's imported as: from src.tools.config_assistant.config_manager import config_manager
    import src.tools.config_assistant.api as api_mod
    api_mod.config_manager = config_manager
    
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_update_rule_override_success(config_manager):
    config_manager.create_game("test_game")
    
    # Test ROI override
    roi = [0.5, 0.5, 0.1, 0.1]
    success = config_manager.update_rule_override("test_game", "rule1", "killfeed_roi", roi)
    assert success is True
    
    config = config_manager.get_config("test_game")
    rule = config["detection"]["rules"][0]
    assert rule["detection_overrides"]["killfeed_roi"] == roi
    
    # Test nested override
    keywords = ["HEADSHOT"]
    success = config_manager.update_rule_override("test_game", "rule1", "ocr.keywords", keywords)
    assert success is True
    
    config = config_manager.get_config("test_game")
    assert config["detection"]["rules"][0]["detection_overrides"]["ocr"]["keywords"] == keywords

def test_update_rule_override_auto_creates_rule(config_manager):
    config_manager.create_game("test_game")
    success = config_manager.update_rule_override("test_game", "nonexistent", "killfeed_roi", [0, 0, 0, 0])
    assert success is True

    config = config_manager.get_config("test_game")
    rule = next((r for r in config["detection"]["rules"] if r["name"] == "nonexistent"), None)
    assert rule is not None
    assert rule["enabled"] is True
    assert rule["require"] == ["color"]
    assert rule["detection_overrides"]["killfeed_roi"] == [0, 0, 0, 0]

def test_api_roi_override(client, config_manager):
    config_manager.create_game("test_game")
    
    roi = [0.2, 0.2, 0.2, 0.2]
    response = client.put("/api/config/test_game/roi", json={
        "roi": roi,
        "rule_name": "rule1"
    })
    assert response.status_code == 200
    
    config = config_manager.get_config("test_game")
    assert config["detection"]["rules"][0]["detection_overrides"]["killfeed_roi"] == roi
    # Global ROI should remain unchanged
    assert config["detection"]["killfeed_roi"] == [0.1, 0.1, 0.2, 0.2]

def test_api_ocr_override(client, config_manager):
    config_manager.create_game("test_game")
    
    response = client.put("/api/config/test_game/ocr", json={
        "enabled": False,
        "keywords": ["TEST"],
        "similarity_threshold": 0.5,
        "rule_name": "rule1"
    })
    assert response.status_code == 200
    
    config = config_manager.get_config("test_game")
    overrides = config["detection"]["rules"][0]["detection_overrides"]["ocr"]
    assert overrides["enabled"] is False
    assert overrides["keywords"] == ["TEST"]
    assert overrides["similarity_threshold"] == 0.5

def test_api_templates_override(client, config_manager):
    config_manager.create_game("test_game")
    
    # Test POST (add single)
    response = client.post("/api/config/test_game/templates", json={
        "name": "t1",
        "roi": [0,0,1,1],
        "rule_name": "rule1"
    })
    assert response.status_code == 200
    
    config = config_manager.get_config("test_game")
    assert "t1" in config["detection"]["rules"][0]["detection_overrides"]["templates"]
    
    # Test PUT (replace all)
    new_templates = {"t2": {"roi": [0.1, 0.1, 0.1, 0.1], "threshold": 0.9}}
    response = client.put("/api/config/test_game/templates", json={
        "templates": new_templates,
        "rule_name": "rule1"
    })
    assert response.status_code == 200
    config = config_manager.get_config("test_game")
    assert config["detection"]["rules"][0]["detection_overrides"]["templates"] == new_templates

def test_api_colors_override(client, config_manager):
    config_manager.create_game("test_game")
    
    # Test POST
    response = client.post("/api/config/test_game/colors", json={
        "name": "red",
        "hsv_lower": [0, 100, 100],
        "hsv_upper": [10, 255, 255],
        "rule_name": "rule1"
    })
    assert response.status_code == 200
    
    config = config_manager.get_config("test_game")
    assert "red" in config["detection"]["rules"][0]["detection_overrides"]["colors"]

def test_validation_invalid_override(client, config_manager):
    config_manager.create_game("test_game")
    
    # Test invalid ROI in rules update
    rules = [
        {
            "name": "rule1",
            "enabled": True,
            "require": ["ocr"],
            "detection_overrides": {
                "killfeed_roi": [0, 0, 1] # Invalid length
            }
        }
    ]
    response = client.put("/api/config/test_game/rules", json={"rules": rules})
    assert response.status_code == 400
    assert "killfeed_roi must be a list of 4 numbers" in response.get_json()["error"]

    # Test invalid OCR similarity
    rules[0]["detection_overrides"] = {
        "ocr": {"similarity_threshold": 1.5}
    }
    response = client.put("/api/config/test_game/rules", json={"rules": rules})
    assert response.status_code == 400
    assert "similarity_threshold must be 0-1" in response.get_json()["error"]
