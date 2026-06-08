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


# ==================== OR-of-AND RULES MODE TESTS ====================

@pytest.fixture
def mock_yolo_model_with_kill():
    """Mock YOLO model that returns a kill detection for each frame in batch."""
    def mock_call(frames, **kwargs):
        """Return one result per frame in the batch."""
        results = []
        for _ in frames:
            mock_result = MagicMock()
            mock_box = MagicMock()
            # Use MagicMock with proper return values instead of torch.tensor
            mock_box.xyxy = [MagicMock(tolist=MagicMock(return_value=[10, 10, 20, 20]))]
            mock_box.conf = [MagicMock(__float__=MagicMock(return_value=0.9))]
            mock_box.cls = [MagicMock(__int__=MagicMock(return_value=0))]
            mock_result.boxes = [mock_box]
            mock_result.names = {0: 'kill'}
            results.append(mock_result)
        return results
    
    mock = MagicMock(side_effect=mock_call)
    return mock


@pytest.fixture
def mock_yolo_model_no_kill():
    """Mock YOLO model that returns NO kill detection for each frame in batch."""
    def mock_call(frames, **kwargs):
        """Return one result per frame in the batch (no detections)."""
        results = []
        for _ in frames:
            mock_result = MagicMock()
            mock_result.boxes = []  # No detections
            mock_result.names = {0: 'kill'}
            results.append(mock_result)
        return results
    
    mock = MagicMock(side_effect=mock_call)
    return mock


class TestKillDetectorRulesMode:
    """Tests for OR-of-AND rules mode in KillDetector."""
    
    def test_rules_hit_single_rule_yolo_and_color(self, mock_yolo_model_with_kill):
        """
        When rules are defined and a rule is satisfied (all signals in require are True),
        is_kill should be True and confidence should be exactly 1.0.
        """
        # Frame with blue color to pass color detection
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = (255, 0, 0)  # Blue in BGR
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {
                    'color_threshold': 0.01
                },
                # OR-of-AND rules: require yolo AND color
                'rules': [
                    {
                        'name': 'yolo_and_color',
                        'enabled': True,
                        'require': ['yolo', 'color']
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        result = detector.process_frame(frame)
        
        assert result["is_kill"] is True
        assert result["confidence"] == 1.0
    
    def test_rules_hit_multiple_rules_or(self, mock_yolo_model_with_kill):
        """
        When multiple rules exist (OR relationship), hitting ANY one should trigger is_kill=True.
        """
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = (255, 0, 0)  # Blue
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': [
                    {
                        'name': 'rule_template_only',
                        'enabled': True,
                        'require': ['template']  # Won't hit - no templates loaded
                    },
                    {
                        'name': 'rule_yolo_color',
                        'enabled': True,
                        'require': ['yolo', 'color']  # This one WILL hit
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        result = detector.process_frame(frame)
        
        assert result["is_kill"] is True
        assert result["confidence"] == 1.0
    
    def test_rules_miss_no_rule_satisfied(self, mock_yolo_model_no_kill):
        """
        When rules are defined but NONE are satisfied, is_kill=False and confidence=0.0.
        """
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = (255, 0, 0)  # Blue - color passes
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': [
                    {
                        'name': 'require_yolo_and_color',
                        'enabled': True,
                        'require': ['yolo', 'color']  # yolo=False, so rule fails
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_no_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        result = detector.process_frame(frame)
        
        assert result["is_kill"] is False
        assert result["confidence"] == 0.0
    
    def test_rules_disabled_rule_ignored(self, mock_yolo_model_with_kill):
        """
        Disabled rules (enabled=False) should be ignored entirely.
        """
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = (255, 0, 0)  # Blue
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': [
                    {
                        'name': 'would_pass_but_disabled',
                        'enabled': False,  # Disabled!
                        'require': ['yolo', 'color']
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        result = detector.process_frame(frame)
        
        # No enabled rules means no rule can match → is_kill=False, confidence=0.0
        assert result["is_kill"] is False
        assert result["confidence"] == 0.0
    
    def test_legacy_fallback_when_rules_empty(self, mock_yolo_model_with_kill):
        """
        When rules is empty list [], fall back to legacy weighted scoring.
        """
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = (255, 0, 0)  # Blue
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.3,  # Low threshold so legacy mode passes
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': []  # Empty rules → legacy fallback
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        result = detector.process_frame(frame)
        
        # Legacy mode: is_kill based on weighted confidence vs threshold
        assert result["is_kill"] is True
        # Confidence should be a weighted value, NOT exactly 1.0
        assert 0.0 < result["confidence"] < 1.0
    
    def test_legacy_fallback_when_rules_missing(self, mock_yolo_model_with_kill):
        """
        When rules key is not present at all, fall back to legacy weighted scoring.
        """
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = (255, 0, 0)  # Blue
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.3,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01}
                # Note: 'rules' key is NOT present
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        result = detector.process_frame(frame)
        
        # Legacy mode behavior
        assert result["is_kill"] is True
        assert 0.0 < result["confidence"] < 1.0
    
    def test_template_threshold_from_config(self, mock_yolo_model_no_kill, tmp_path):
        """
        Template signal should use per-template threshold from config.
        If score < configured threshold, template signal is False.
        """
        # Create template with a cross pattern
        template = np.zeros((20, 20, 3), dtype=np.uint8)
        template[8:12, :] = 255  # Horizontal line
        template[:, 8:12] = 255  # Vertical line
        
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        cv2.imwrite(str(template_dir / "kill_icon.png"), template)
        
        # Create frame with a plain square (different pattern from cross)
        # This will give a low match score (~0.3)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = 128  # Gray square - no cross pattern
        
        # Set threshold at 0.5 - the mismatched pattern (~0.3) won't reach this
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {},
                'prefilter': {'color_threshold': 0.0},  # Always pass prefilter
                'templates': {
                    'kill_icon': {
                        'threshold': 0.5  # Threshold higher than expected score
                    }
                },
                'rules': [
                    {
                        'name': 'require_template',
                        'enabled': True,
                        'require': ['template']
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_no_kill)
        cv_matcher = OpenCVMatcher(game_config)
        cv_matcher.load_templates(str(template_dir))
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        result = detector.process_frame(frame)
        
        # Template score is ~0.3 < 0.5 threshold, so template signal is False
        # Rule requires template, so is_kill=False
        assert result["is_kill"] is False
        assert result["confidence"] == 0.0
    
    def test_template_passes_with_default_threshold(self, mock_yolo_model_no_kill, tmp_path):
        """
        Template signal with default threshold (0.8) should pass when score >= 0.8.
        """
        # Create frame and matching template (exact match = 1.0 score)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = (255, 255, 255)  # White square
        
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template = frame[40:60, 40:60].copy()
        cv2.imwrite(str(template_dir / "kill_icon.png"), template)
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {},
                'prefilter': {'color_threshold': 0.0},
                # No explicit threshold → default 0.8
                'rules': [
                    {
                        'name': 'require_template',
                        'enabled': True,
                        'require': ['template']
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_no_kill)
        cv_matcher = OpenCVMatcher(game_config)
        cv_matcher.load_templates(str(template_dir))
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        result = detector.process_frame(frame)
        
        # Exact template match (score ~1.0) > default threshold 0.8
        assert result["is_kill"] is True
        assert result["confidence"] == 1.0


class TestKillDetectorRulesModeBatch:
    """Tests for rules mode in batch processing path."""
    
    def test_batch_rules_mode_confidence_1_0(self, mock_yolo_model_with_kill):
        """
        In batch processing (process_video_batch), rules mode should produce
        confidence=1.0 for events that match a rule.
        """
        frames = []
        timestamps = []
        
        # Create 3 frames with blue color
        for i in range(3):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            frame[40:60, 40:60] = (255, 0, 0)  # Blue
            frames.append(frame)
            timestamps.append(i * 1000)
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': [
                    {
                        'name': 'yolo_and_color',
                        'enabled': True,
                        'require': ['yolo', 'color']
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        events = detector.process_video_batch(frames, timestamps)
        
        # Should have events for frames that pass rules
        assert len(events) >= 1
        
        # All events should have confidence=1.0 in rules mode
        for event in events:
            assert event["confidence"] == 1.0
            assert event["type"] == "kill"
    
    def test_batch_legacy_mode_weighted_confidence(self, mock_yolo_model_with_kill):
        """
        In batch processing with legacy mode (no rules), events should have
        weighted confidence values (not exactly 1.0).
        """
        frames = []
        timestamps = []
        
        for i in range(3):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            frame[40:60, 40:60] = (255, 0, 0)  # Blue
            frames.append(frame)
            timestamps.append(i * 1000)
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.3,  # Low threshold for legacy to pass
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': []  # Empty = legacy mode
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        events = detector.process_video_batch(frames, timestamps)
        
        assert len(events) >= 1
        
        # Legacy mode: confidence should be weighted (0 < conf < 1)
        for event in events:
            assert 0.0 < event["confidence"] < 1.0
    
    def test_batch_rules_mode_no_events_when_no_match(self, mock_yolo_model_no_kill):
        """
        Batch processing should produce no events when rules don't match.
        """
        frames = []
        timestamps = []
        
        for i in range(3):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            frame[40:60, 40:60] = (255, 0, 0)  # Blue - color passes
            frames.append(frame)
            timestamps.append(i * 1000)
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': [
                    {
                        'name': 'require_yolo',
                        'enabled': True,
                        'require': ['yolo', 'color']  # yolo=False, so no match
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_no_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        events = detector.process_video_batch(frames, timestamps)
        
        # No events because yolo signal is False
        assert len(events) == 0


