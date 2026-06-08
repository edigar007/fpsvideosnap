import json

import cv2
import numpy as np
import pytest
from unittest.mock import MagicMock

from src.ai.kill_detector import KillDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.timestamp_recorder import TimestampRecorder
from src.ai.yolo_detector import YoloDetector


@pytest.fixture
def mock_yolo_model():
    mock = MagicMock()
    mock_result = MagicMock()
    mock_box = MagicMock()
    mock_box.xyxy = [MagicMock(tolist=MagicMock(return_value=[10, 10, 20, 20]))]
    mock_box.conf = [MagicMock(__float__=MagicMock(return_value=0.9))]
    mock_box.cls = [MagicMock(__int__=MagicMock(return_value=0))]
    mock_result.boxes = [mock_box]
    mock_result.names = {0: "kill"}
    mock.return_value = [mock_result]
    return mock


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

def test_template_score_below_threshold_does_not_contribute_to_weighted_confidence():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    yolo = MagicMock()
    yolo.detect_single.return_value = []

    cv_matcher = MagicMock()
    cv_matcher.templates = {"kill_icon": object()}
    cv_matcher.match_template.return_value = (None, 0.55)
    cv_matcher.detect_color.return_value = 0.02

    game_config = {
        'detection': {
            'confidence_threshold': 0.5,
            'killfeed_roi': [0, 0, 1, 1],
            'templates': {
                'kill_icon': {
                    'threshold': 0.8,
                }
            },
            'colors': {
                'kill_color': {
                    'lower': [100, 100, 100],
                    'upper': [140, 255, 255],
                }
            },
            'prefilter': {'color_threshold': 0.01},
            'weights': {
                'ocr': 0.0,
                'template': 0.9,
                'color': 0.1,
                'yolo': 0.0,
            },
        }
    }

    detector = KillDetector(yolo, cv_matcher, game_config)
    result = detector.process_frame(frame)

    assert result["signals"]["template"] == 0.0
    assert result["confidence"] == pytest.approx(0.1)
    assert result["is_kill"] is False

def test_template_matching_uses_template_roi_and_threshold():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    yolo = MagicMock()
    yolo.detect_single.return_value = []

    cv_matcher = MagicMock()
    cv_matcher.templates = {"kill_icon": object()}
    cv_matcher.match_template.return_value = ((20, 30), 0.9)
    cv_matcher.detect_color.return_value = 0.0

    template_roi = [0.2, 0.3, 0.1, 0.15]
    game_config = {
        'detection': {
            'confidence_threshold': 0.5,
            'killfeed_roi': [0, 0, 1, 1],
            'templates': {
                'kill_icon': {
                    'roi': template_roi,
                    'threshold': 0.85,
                }
            },
            'colors': {},
        }
    }

    detector = KillDetector(yolo, cv_matcher, game_config)
    result = detector.process_frame(frame)

    cv_matcher.match_template.assert_called_with(
        frame,
        'kill_icon',
        threshold=0.85,
        roi=template_roi,
    )
    assert result["signals"]["template"] == pytest.approx(0.9)

def test_kill_detector_uses_explicit_color_bounds_without_double_tolerance(mock_yolo_model):
    game_config = {
        'detection': {
            'killfeed_roi': [0, 0, 1, 1],
            'colors': {
                'sample_red': {
                    'hsv_lower': [0, 235, 235],
                    'hsv_upper': [10, 255, 255],
                    'tolerance': 20,
                }
            }
        }
    }
    yolo = YoloDetector(mock_yolo_model)
    cv_matcher = MagicMock()
    cv_matcher.templates = {}
    cv_matcher.detect_color.return_value = 0.0

    detector = KillDetector(yolo, cv_matcher, game_config)
    detector._prefilter_with_result(np.zeros((10, 10, 3), dtype=np.uint8))

    _, lower, upper = cv_matcher.detect_color.call_args.args[:3]
    assert lower == [0, 235, 235]
    assert upper == [10, 255, 255]

def test_kill_detector_prefilter_enabled_false_skips_color_gate(mock_yolo_model):
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    game_config = {
        'detection': {
            'confidence_threshold': 0.5,
            'killfeed_roi': [0, 0, 1, 1],
            'colors': {
                'sample_red': {
                    'hsv_lower': [0, 235, 235],
                    'hsv_upper': [10, 255, 255],
                }
            },
            'prefilter': {
                'enabled': False,
                'color_threshold': 0.99,
            },
        }
    }
    yolo = YoloDetector(mock_yolo_model)
    cv_matcher = MagicMock()
    cv_matcher.templates = {}
    cv_matcher.detect_color.return_value = 0.0

    detector = KillDetector(yolo, cv_matcher, game_config)
    detector._precise_detect = MagicMock(return_value={
        "ocr": 0.0,
        "template": 0.0,
        "color": 1.0,
        "yolo": 0.0,
    })

    result = detector.process_frame(frame)

    detector._precise_detect.assert_called_once_with(frame, cached_color_pct=None)
    cv_matcher.detect_color.assert_not_called()
    assert result["signals"]["color"] == 1.0

def test_kill_detector_passes_configured_ocr_similarity_threshold(mock_yolo_model):
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    yolo = YoloDetector(mock_yolo_model)
    yolo.detect_single = MagicMock(return_value=[])
    cv_matcher = MagicMock()
    cv_matcher.templates = {}

    ocr = MagicMock()
    ocr.find_keywords.return_value = {"found": False, "confidence": 0.0}
    game_config = {
        'detection': {
            'killfeed_roi': [0, 0, 1, 1],
            'ocr': {
                'enabled': True,
                'keywords': ['KILL'],
                'similarity_threshold': 0.95,
            },
            'colors': {},
        }
    }

    detector = KillDetector(yolo, cv_matcher, game_config, ocr_detector=ocr)
    detector._precise_detect(frame)

    ocr.find_keywords.assert_called_once_with(
        frame,
        ['KILL'],
        roi=[0, 0, 100, 100],
        threshold=0.95,
    )

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


