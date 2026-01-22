import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from src.ai.kill_detector import KillDetector

@pytest.fixture
def mock_detectors():
    yolo = MagicMock()
    yolo.detect_single.return_value = []
    yolo.detect_batch.return_value = [[]]
    
    cv = MagicMock()
    cv.templates = {}
    cv.match_template.return_value = (None, 0.0)
    cv.detect_color.return_value = 0.0
    
    ocr = MagicMock()
    ocr.find_keywords.return_value = {"found": False, "confidence": 0.0}
    
    return yolo, cv, ocr

def test_rule_with_roi_override(mock_detectors):
    yolo, cv, ocr = mock_detectors
    config = {
        "detection": {
            "killfeed_roi": [0, 0, 0.5, 0.5],
            "colors": {
                "test": {"hsv_lower": [0, 0, 0], "hsv_upper": [255, 255, 255]}
            },
            "rules": [
                {
                    "name": "rule_roi_override",
                    "enabled": True,
                    "require": ["color"],
                    "detection_overrides": {
                        "killfeed_roi": [0.5, 0.5, 0.5, 0.5],
                        "_force_color_recompute": True
                    }
                }
            ]
        }
    }
    
    detector = KillDetector(yolo, cv, config, ocr_detector=ocr)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Pre-filter needs to pass
    def mock_detect_color(f, lower, upper, roi):
        if roi == [0.5, 0.5, 0.5, 0.5]:
            return 1.0
        # For pre-filter (global ROI)
        if roi == [0, 0, 0.5, 0.5]:
            return 1.0
        return 0.0
    
    cv.detect_color.side_effect = mock_detect_color
    
    # Should be kill because rule uses override ROI
    # Add a mock color to trigger evaluation if needed, 
    # but here we rely on _force_color_recompute
    result = detector.process_frame(frame)
    assert result["is_kill"] is True
    assert cv.detect_color.call_count >= 1
    # Check if it was called with override ROI at least once
    roi_calls = [call.kwargs.get('roi') or call.args[3] for call in cv.detect_color.call_args_list]
    assert [0.5, 0.5, 0.5, 0.5] in roi_calls

def test_rule_with_ocr_keywords_override(mock_detectors):
    yolo, cv, ocr = mock_detectors
    config = {
        "detection": {
            "ocr": {"enabled": True, "keywords": ["Global"]},
            "rules": [
                {
                    "name": "rule_ocr_override",
                    "enabled": True,
                    "require": ["ocr"],
                    "detection_overrides": {
                        "ocr": {"keywords": ["Override"]}
                    }
                }
            ]
        }
    }
    
    detector = KillDetector(yolo, cv, config, ocr_detector=ocr)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    def mock_find_keywords(f, keywords, roi):
        if "Override" in keywords:
            return {"found": True, "confidence": 100.0}
        return {"found": False, "confidence": 0.0}
    
    ocr.find_keywords.side_effect = mock_find_keywords
    
    result = detector.process_frame(frame)
    assert result["is_kill"] is True
    # Verify it was called with "Override"
    keywords_called = [call.kwargs.get('keywords') or call.args[1] for call in ocr.find_keywords.call_args_list]
    assert any("Override" in k for k in keywords_called)

def test_multiple_rules_independent_evaluation(mock_detectors):
    yolo, cv, ocr = mock_detectors
    config = {
        "detection": {
            "rules": [
                {
                    "name": "rule_1",
                    "enabled": True,
                    "require": ["ocr"],
                    "detection_overrides": {"ocr": {"enabled": True, "keywords": ["K1"]}}
                },
                {
                    "name": "rule_2",
                    "enabled": True,
                    "require": ["ocr"],
                    "detection_overrides": {"ocr": {"enabled": True, "keywords": ["K2"]}}
                }
            ]
        }
    }
    
    detector = KillDetector(yolo, cv, config, ocr_detector=ocr)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Only K2 matches
    def mock_find_keywords(f, keywords, roi):
        if "K2" in keywords:
            return {"found": True, "confidence": 100.0}
        return {"found": False, "confidence": 0.0}
    
    ocr.find_keywords.side_effect = mock_find_keywords
    
    result = detector.process_frame(frame)
    assert result["is_kill"] is True
    
    # If both fail
    ocr.find_keywords.side_effect = lambda f, k, roi=None: {"found": False, "confidence": 0.0}
    result = detector.process_frame(frame)
    assert result["is_kill"] is False

def test_backward_compatibility_no_overrides(mock_detectors):
    yolo, cv, ocr = mock_detectors
    config = {
        "detection": {
            "killfeed_roi": [0, 0, 1, 1],
            "colors": {
                "test": {"hsv_lower": [0, 0, 0], "hsv_upper": [255, 255, 255]}
            },
            "rules": [
                {
                    "name": "rule_no_override",
                    "enabled": True,
                    "require": ["color"],
                    "detection_overrides": {"_force_color_recompute": True}
                }
            ]
        }
    }
    
    detector = KillDetector(yolo, cv, config, ocr_detector=ocr)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    cv.detect_color.return_value = 1.0
    
    result = detector.process_frame(frame)
    assert result["is_kill"] is True
    roi_calls = [call.kwargs.get('roi') or call.args[3] for call in cv.detect_color.call_args_list]
    assert [0, 0, 1, 1] in roi_calls
