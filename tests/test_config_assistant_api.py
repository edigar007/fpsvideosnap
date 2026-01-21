import os
import io
import json
import pytest
import yaml
from PIL import Image
from src.tools.config_assistant.server import create_app
from src.tools.config_assistant.config_manager import config_manager

CONFIG_GAMES_DIR = config_manager.games_dir
TEMPLATE_ROOT = os.path.join(config_manager.project_root, "models", "templates")

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    upload_dir = app.config['UPLOAD_FOLDER']
    with app.test_client() as client:
        yield client

    test_dirs = [
        os.path.join(TEMPLATE_ROOT, "test_game"),
        upload_dir,
    ]
    test_files = [
        os.path.join("temp", "test_pick.png"),
        os.path.join("temp", "test_template.png"),
        os.path.join(CONFIG_GAMES_DIR, "test_game_config.yaml"),
    ]
    for f in test_files:
        if os.path.exists(f):
            os.remove(f)
    for d in test_dirs:
        if os.path.exists(d):
            import shutil
            shutil.rmtree(d, ignore_errors=True)

def test_index(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'Config Assistant' in rv.data

def test_upload(client):
    # Create a dummy image
    img = Image.new('RGB', (100, 100), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    data = {
        'file': (img_byte_arr, 'test.png')
    }
    rv = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert rv.status_code == 200
    res = rv.get_json()
    assert res['width'] == 100
    assert res['height'] == 100
    assert 'url' in res
    assert 'path' in res

def test_pick_color(client):
    # Prepare image
    img = Image.new('RGB', (10, 10), color=(255, 0, 0)) # Red
    img_path = os.path.abspath(os.path.join("temp", "test_pick.png"))
    os.makedirs("temp", exist_ok=True)
    img.save(img_path)
    
    data = {
        "image_path": img_path,
        "x": 5,
        "y": 5
    }
    rv = client.post('/api/pick-color', json=data)
    assert rv.status_code == 200
    res = rv.get_json()
    assert res['rgb'] == [255, 0, 0]
    # Red in HSV (OpenCV): H=0, S=255, V=255
    assert res['hsv'][1] == 255
    assert res['hsv'][2] == 255
    assert 'hsv_range' in res

def test_save_template(client):
    img = Image.new('RGB', (10, 10), color='blue')
    img_path = os.path.abspath(os.path.join("temp", "test_template.png"))
    img.save(img_path)
    
    data = {
        "image_path": img_path,
        "game_name": "test_game",
        "template_name": "test_icon"
    }
    rv = client.post('/api/save-template', json=data)
    assert rv.status_code == 200
    
    target_path = os.path.abspath(os.path.join("models", "templates", "test_game", "test_icon.png"))
    assert os.path.exists(target_path)

def test_generate_config(client):
    data = {
        "game_name": "testgame",
        "rois": [
            {"name": "killfeed", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}
        ],
        "colors": [
            {"name": "enemy_red", "lower": [0, 100, 100], "upper": [10, 255, 255]}
        ]
    }
    rv = client.post('/api/generate-config', json=data)
    assert rv.status_code == 200
    res = rv.get_json()
    assert "yaml" in res
    config = yaml.safe_load(res['yaml'])
    assert config['game_name'] == 'testgame'
    assert config['detection']['killfeed_roi'] == [0.1, 0.2, 0.3, 0.4]
    assert 'enemy_red' in config['detection']['colors']
    assert config['detection']['template_dir'] == 'models/templates/testgame'

def test_load_config(client):
    # Create dummy config
    game_name = "test_game_config"
    os.makedirs(CONFIG_GAMES_DIR, exist_ok=True)
    config_path = os.path.join(CONFIG_GAMES_DIR, f"{game_name}.yaml")
    
    test_data = {"key": "value"}
    with open(config_path, 'w') as f:
        yaml.dump(test_data, f)
        
    rv = client.get(f'/api/load-config/{game_name}')
    assert rv.status_code == 200
    assert rv.get_json() == test_data

def test_app_creates_without_ocr(monkeypatch):
    """Test that create_app() succeeds even when OCR initialization would fail."""
    # Mock OCRDetector to always raise an exception
    def mock_ocr_init(self, *args, **kwargs):
        raise OSError("[WinError 127] cudnn_cnn64_9.dll not found")
    
    monkeypatch.setattr('src.ai.ocr_detector.OCRDetector.__init__', mock_ocr_init)
    
    # Reset singleton state
    import src.tools.config_assistant.ocr_service as ocr_module
    ocr_module._ocr_service_instance = None
    
    # App should still create successfully
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Basic routes should work
        rv = client.get('/')
        assert rv.status_code == 200


def test_ocr_detect_returns_503_when_unavailable(monkeypatch):
    """Test that /api/ocr/detect returns 503 when OCR is unavailable."""
    # Reset singleton state BEFORE patching
    import src.tools.config_assistant.ocr_service as ocr_module
    ocr_module._ocr_service_instance = None
    
    # Mock OCRDetector to always raise an exception
    def mock_ocr_init(self, *args, **kwargs):
        raise OSError("[WinError 127] cudnn_cnn64_9.dll not found")
    
    monkeypatch.setattr('src.ai.ocr_detector.OCRDetector.__init__', mock_ocr_init)
    
    app = create_app()
    app.config['TESTING'] = True
    
    # Create a dummy test image
    import tempfile
    from PIL import Image
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img = Image.new('RGB', (100, 100), color='red')
        img.save(f.name)
        temp_path = f.name
    
    try:
        with app.test_client() as client:
            rv = client.post('/api/ocr/detect', json={
                'image_path': temp_path,
                'roi': None
            })
            assert rv.status_code == 503
            data = rv.get_json()
            assert 'error' in data
            assert data['error'] == 'OCR unavailable'
    finally:
        os.unlink(temp_path)
        # Clean up singleton state for other tests
        ocr_module._ocr_service_instance = None
