import pytest
import sys
from unittest.mock import patch
from src.cli import parse_args
from src.tools.config_assistant.server import create_app

def test_cli_config_assistant_args():
    """Test that the config-assistant subcommand is correctly parsed."""
    test_args = ["main.py", "config-assistant", "--port", "9090", "--debug"]
    with patch.object(sys, 'argv', test_args):
        args = parse_args()
        assert args.command == "config-assistant"
        assert args.port == 9090
        assert args.debug is True

def test_cli_default_run_args():
    """Test that the run command (implicit) is correctly parsed."""
    test_args = ["main.py", "--video", "test.mp4", "--game", "bf6", "--debug"]
    with patch.object(sys, 'argv', test_args):
        args = parse_args()
        assert args.command == "run"
        assert args.video == "test.mp4"
        assert args.game == "bf6"
        assert args.debug is True

def test_flask_app_creation():
    """Test that the Flask app can be created without errors."""
    app = create_app()
    assert app is not None
    assert app.name == "src.tools.config_assistant.server"

def test_flask_api_routes():
    """Test that basic API routes are registered."""
    app = create_app()
    client = app.test_client()
    
    # Test index
    response = client.get('/')
    assert response.status_code == 200
    
    # Test games list
    response = client.get('/api/games')
    assert response.status_code == 200
    assert isinstance(response.json, list)
