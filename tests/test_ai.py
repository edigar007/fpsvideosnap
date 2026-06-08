import pytest
import numpy as np
import cv2
import os
import json
from unittest.mock import MagicMock
from src.ai.model_manager import ModelManager
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.kill_detector import KillDetector
from src.ai.timestamp_recorder import TimestampRecorder

@pytest.fixture
def mock_frame():
    # Create a 100x100 black image with a blue square for color detection test
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Blue in BGR: (255, 0, 0)
    frame[40:60, 40:60] = (255, 0, 0)
    return frame

@pytest.fixture
def mock_yolo_model():
    mock = MagicMock()
    # Mock result object from Ultralytics
    mock_result = MagicMock()
    mock_box = MagicMock()
    # Use MagicMock with proper return values instead of torch.tensor
    # since torch is mocked in conftest.py
    mock_box.xyxy = [MagicMock(tolist=MagicMock(return_value=[10, 10, 20, 20]))]
    mock_box.conf = [MagicMock(__float__=MagicMock(return_value=0.9))]
    mock_box.cls = [MagicMock(__int__=MagicMock(return_value=0))]
    mock_result.boxes = [mock_box]
    mock_result.names = {0: 'kill'}
    
    mock.return_value = [mock_result]
    return mock

def test_model_manager_init():
    manager = ModelManager()
    assert manager.get_device() in ["cuda", "cpu"]
    assert manager.model is None

def test_yolo_detector_inference(mock_frame, mock_yolo_model):
    detector = YoloDetector(mock_yolo_model)
    results = detector.detect_single(mock_frame)
    
    assert len(results) == 1
    assert results[0]['name'] == 'kill'
    assert results[0]['conf'] == pytest.approx(0.9)

def test_opencv_matcher_color(mock_frame):
    matcher = OpenCVMatcher()
    # Blue in HSV is roughly around 120 (OpenCV H: 0-180)
    lower_blue = [100, 100, 100]
    upper_blue = [140, 255, 255]
    
    # Check full frame
    score = matcher.detect_color(mock_frame, lower_blue, upper_blue)
    assert score > 0
    # 20x20 in 100x100 should be 400/10000 = 0.04
    assert abs(score - 0.04) < 0.01

def test_opencv_matcher_template(mock_frame):
    matcher = OpenCVMatcher()
    # Create a more unique template
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Add a white cross on blue background
    frame[40:60, 40:60] = (255, 0, 0)
    frame[48:52, 40:60] = (255, 255, 255)
    frame[40:60, 48:52] = (255, 255, 255)
    
    template = frame[40:60, 40:60].copy()
    template_path = "temp_template.png"
    cv2.imwrite(template_path, template)
    
    try:
        matcher.load_templates(".")
        # matcher.templates["temp_template"] = template # load_templates works on files
        loc, score = matcher.match_template(frame, "temp_template")
        assert score > 0.9
        assert loc == (40, 40)
    finally:
        if os.path.exists(template_path):
            os.remove(template_path)

def test_kill_detector_integration(mock_frame, mock_yolo_model):
    game_config = {
        'detection': {
            'confidence_threshold': 0.5,
            'killfeed_roi': [0, 0, 1, 1],
            'colors': {
                'player_kill_blue': {
                    'lower': [100, 100, 100],
                    'upper': [140, 255, 255]
                }
            }
        }
    }
    yolo = YoloDetector(mock_yolo_model)
    cv_matcher = OpenCVMatcher()
    
    detector = KillDetector(yolo, cv_matcher, game_config)
    result = detector.process_frame(mock_frame)
    
    assert result["is_kill"] is True
    assert result["confidence"] > 0.5
    assert "yolo" in result["signals"]
    assert "color" in result["signals"]

def test_timestamp_recorder(tmp_path):
    output_file = tmp_path / "results.json"
    recorder = TimestampRecorder(str(output_file))
    
    recorder.record_event(1000, "kill", 0.95)
    recorder.record_event(5000, "kill", 0.88, {"player": "enemy1"})
    recorder.save()
    
    assert os.path.exists(output_file)
    with open(output_file, 'r') as f:
        data = json.load(f)
        assert len(data) == 2
        assert data[0]["timestamp_ms"] == 1000
        assert data[1]["meta"]["player"] == "enemy1"

# ==================== PHASE 2 REGRESSION TESTS (TASK-006) ====================

def test_opencv_template_loading(tmp_path):
    """TASK-006: Verify template loading works correctly."""
    # Create test template directory
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    
    # Create sample templates
    template1 = np.ones((20, 20, 3), dtype=np.uint8) * 100
    template2 = np.ones((30, 30, 3), dtype=np.uint8) * 200
    
    cv2.imwrite(str(template_dir / "skull.png"), template1)
    cv2.imwrite(str(template_dir / "crosshair.png"), template2)
    # Create a non-image file that should be ignored by load_templates
    with open(str(template_dir / "notimage.txt"), "w") as f:
        f.write("text")
    
    # Load templates
    matcher = OpenCVMatcher()
    matcher.load_templates(str(template_dir))
    
    # Verify correct number of templates loaded
    assert len(matcher.templates) == 2
    assert "skull" in matcher.templates
    assert "crosshair" in matcher.templates
    assert matcher.templates["skull"].shape == (20, 20, 3)
    assert matcher.templates["crosshair"].shape == (30, 30, 3)

def test_opencv_template_loading_missing_dir():
    """TASK-006: Verify graceful handling of missing template directory."""
    matcher = OpenCVMatcher()
    # Should not crash, just log warning
    matcher.load_templates("/nonexistent/path")
    assert len(matcher.templates) == 0

def test_opencv_template_loading_from_config_paths(tmp_path):
    """Config-assistant templates should load from detection.templates.*.path."""
    template_dir = tmp_path / "models" / "templates" / "test_game"
    template_dir.mkdir(parents=True)
    template = np.ones((12, 16, 3), dtype=np.uint8) * 180
    cv2.imwrite(str(template_dir / "kill_icon.png"), template)

    detection_config = {
        "templates": {
            "kill_icon": {
                "path": "models/templates/test_game/kill_icon.png",
                "threshold": 0.8,
            }
        }
    }

    matcher = OpenCVMatcher()
    loaded_count = matcher.load_templates_from_config(
        detection_config,
        project_root=str(tmp_path),
    )

    assert loaded_count == 1
    assert "kill_icon" in matcher.templates
    assert matcher.templates["kill_icon"].shape == (12, 16, 3)

def test_opencv_template_loading_from_rule_override_paths(tmp_path):
    """Rule-level template paths should be loaded for formal detection."""
    template_path = tmp_path / "rule_icon.png"
    template = np.ones((10, 10, 3), dtype=np.uint8) * 90
    cv2.imwrite(str(template_path), template)

    detection_config = {
        "rules": [
            {
                "name": "template_rule",
                "enabled": True,
                "require": ["template"],
                "detection_overrides": {
                    "templates": {
                        "rule_icon": {
                            "path": str(template_path),
                            "threshold": 0.8,
                        }
                    }
                },
            }
        ]
    }

    matcher = OpenCVMatcher()
    loaded_count = matcher.load_templates_from_config(detection_config)

    assert loaded_count == 1
    assert "rule_icon" in matcher.templates

def test_opencv_match_all_templates(tmp_path):
    """TASK-006: Verify match_all_templates method works correctly."""
    # Create a test frame with a distinct pattern
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[30:50, 30:50] = (255, 255, 255)  # White square
    
    # Create template directory
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    
    # Create matching template
    template = frame[30:50, 30:50].copy()
    cv2.imwrite(str(template_dir / "white_square.png"), template)
    
    # Load and match
    matcher = OpenCVMatcher()
    matcher.load_templates(str(template_dir))
    matches = matcher.match_all_templates(frame, threshold=0.9)
    
    assert len(matches) == 1
    assert "white_square" in matches
    loc, score = matches["white_square"]
    assert score > 0.99
    # Location should be top-left corner of the match
    assert loc[0] >= 0 and loc[1] >= 0

