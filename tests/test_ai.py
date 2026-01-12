import pytest
import numpy as np
import cv2
import os
import torch
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
    mock_box.xyxy = [torch.tensor([10, 10, 20, 20])]
    mock_box.conf = [torch.tensor(0.9)]
    mock_box.cls = [torch.tensor(0)]
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
    cv2.imwrite(str(template_dir / "notimage.txt"), b"text")  # Should be ignored
    
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

def test_detection_weights_with_templates(tmp_path, mock_yolo_model):
    """TASK-006: Verify detection weights incorporate template scores when templates exist."""
    # Create frame with both color and template patterns
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    # Blue region for color detection
    frame[80:120, 80:120] = (255, 0, 0)  # Blue in BGR
    # White cross pattern for template
    frame[90:110, 80:120] = (255, 255, 255)
    frame[80:120, 90:110] = (255, 255, 255)
    
    # Create template
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = frame[80:120, 80:120].copy()
    cv2.imwrite(str(template_dir / "kill_icon.png"), template)
    
    # Setup config
    game_config = {
        'detection': {
            'confidence_threshold': 0.3,
            'killfeed_roi': [0, 0, 1, 1],
            'colors': {
                'player_kill_blue': {
                    'lower': [100, 100, 100],
                    'upper': [140, 255, 255]
                }
            }
        }
    }
    
    # Test WITHOUT templates
    yolo = YoloDetector(mock_yolo_model)
    cv_matcher_no_templates = OpenCVMatcher(game_config)
    detector_no_templates = KillDetector(yolo, cv_matcher_no_templates, game_config)
    result_no_templates = detector_no_templates.process_frame(frame)
    
    # Test WITH templates
    cv_matcher_with_templates = OpenCVMatcher(game_config)
    cv_matcher_with_templates.load_templates(str(template_dir))
    detector_with_templates = KillDetector(yolo, cv_matcher_with_templates, game_config)
    result_with_templates = detector_with_templates.process_frame(frame)
    
    # Verify template signal is present and improves confidence
    assert "template" in result_with_templates["signals"]
    assert result_with_templates["signals"]["template"] > 0.8
    assert result_with_templates["confidence"] > result_no_templates["confidence"]
    
    # Both should detect kill, but with different confidence scores
    assert result_no_templates["is_kill"] is True
    assert result_with_templates["is_kill"] is True

def test_timestamp_recorder_multiple_saves(tmp_path):
    """TASK-006: Verify TimestampRecorder handles multiple save operations correctly."""
    output_file = tmp_path / "detections.json"
    recorder = TimestampRecorder(str(output_file))
    
    # First batch of events
    recorder.record_event(1000, "kill", 0.92, {"type": "rifle"})
    recorder.record_event(2500, "kill", 0.88, {"type": "grenade"})
    recorder.save()
    
    # Verify first save
    with open(output_file, 'r') as f:
        data1 = json.load(f)
        assert len(data1) == 2
    
    # Add more events
    recorder.record_event(5000, "kill", 0.95, {"type": "sniper"})
    recorder.save()
    
    # Verify all events persisted
    with open(output_file, 'r') as f:
        data2 = json.load(f)
        assert len(data2) == 3
        assert data2[2]["timestamp_ms"] == 5000
        assert data2[2]["meta"]["type"] == "sniper"

def test_timestamp_recorder_json_structure(tmp_path):
    """TASK-006: Verify TimestampRecorder saves correct JSON structure."""
    output_file = tmp_path / "structure_test.json"
    recorder = TimestampRecorder(str(output_file))
    
    recorder.record_event(
        timestamp_ms=1234,
        event_type="kill",
        confidence=0.876,
        meta={"weapon": "M4A1", "distance": 25.5}
    )
    recorder.save()
    
    with open(output_file, 'r') as f:
        data = json.load(f)
        assert len(data) == 1
        event = data[0]
        
        # Verify required fields
        assert "timestamp_ms" in event
        assert "type" in event
        assert "confidence" in event
        assert "recorded_at" in event
        assert "meta" in event
        
        # Verify values
        assert event["timestamp_ms"] == 1234
        assert event["type"] == "kill"
        assert event["confidence"] == 0.876
        assert event["meta"]["weapon"] == "M4A1"
        assert event["meta"]["distance"] == 25.5

def test_kill_detector_with_empty_templates(mock_yolo_model):
    """TASK-006: Verify KillDetector handles missing templates gracefully."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    game_config = {
        'detection': {
            'confidence_threshold': 0.5,
            'killfeed_roi': [0, 0, 1, 1],
            'colors': {}
        }
    }
    
    yolo = YoloDetector(mock_yolo_model)
    cv_matcher = OpenCVMatcher(game_config)
    # Don't load any templates
    detector = KillDetector(yolo, cv_matcher, game_config)
    
    result = detector.process_frame(frame)
    
    # Should work without crashing
    assert "confidence" in result
    assert "signals" in result
    assert result["signals"]["template"] == 0.0


