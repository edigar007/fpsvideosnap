import numpy as np
from unittest.mock import MagicMock

from src.ai.kill_detector import KillDetector


def test_rule_without_overrides_reuses_precise_signals() -> None:
    yolo = MagicMock()
    yolo.detect_single.return_value = []

    cv = MagicMock()
    cv.templates = {"kill_icon": object()}
    cv.match_template.return_value = ((1, 1), 0.95)
    cv.detect_color.return_value = 1.0

    ocr = MagicMock()
    ocr.find_keywords.return_value = {"found": True, "confidence": 100.0}

    config = {
        "detection": {
            "killfeed_roi": [0, 0, 1, 1],
            "ocr": {"enabled": True, "keywords": ["KILL"]},
            "colors": {
                "red": {"hsv_lower": [0, 0, 0], "hsv_upper": [10, 255, 255]},
            },
            "templates": {"kill_icon": {"threshold": 0.8}},
            "rules": [
                {
                    "name": "global_ocr_template",
                    "enabled": True,
                    "require": ["ocr", "template"],
                }
            ],
        }
    }

    detector = KillDetector(yolo, cv, config, ocr_detector=ocr)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    result = detector.process_frame(frame)

    assert result["is_kill"] is True
    assert ocr.find_keywords.call_count == 1
    assert cv.match_template.call_count == 1
