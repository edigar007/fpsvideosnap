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
