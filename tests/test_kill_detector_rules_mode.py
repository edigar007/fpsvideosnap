import cv2
import numpy as np
import pytest
from unittest.mock import MagicMock

from src.ai.kill_detector import KillDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.yolo_detector import YoloDetector


# ==================== OR-of-AND RULES MODE TESTS ====================

@pytest.fixture
def mock_yolo_model_with_kill():
    def mock_call(frames, **kwargs):
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
    def mock_call(frames, **kwargs):
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
    
    def test_rules_hit_single_rule_yolo_and_color(self, mock_yolo_model_with_kill):
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


