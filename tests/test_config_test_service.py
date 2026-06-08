from unittest.mock import MagicMock

import numpy as np
import pytest

from src.ai.signal_fusion import WeightedSignalFusion
from src.tools.config_assistant.services import config_test_service as service_module
from src.tools.config_assistant.services.config_test_service import ConfigTestService


class DummyMatcher:
    def __init__(self):
        self.templates = {}

    def load_templates_from_config(self, detection_cfg, project_root):
        self.templates = {
            name: object()
            for name in (detection_cfg.get("templates", {}) or {})
        }
        return len(self.templates)

    def detect_color(self, frame, hsv_lower, hsv_upper, roi=None):
        return 1.0

    def match_template(self, frame, template_name, threshold=0.8, roi=None):
        return (0, 0), threshold


class ScoredMatcher(DummyMatcher):
    score = 0.85

    def match_template(self, frame, template_name, threshold=0.8, roi=None):
        if self.score >= threshold:
            return (0, 0), self.score
        return None, self.score


def _config(**detection_overrides):
    detection = {
        "killfeed_roi": [0, 0, 1, 1],
        "ocr": {"enabled": False, "keywords": [], "similarity_threshold": 0.8},
        "colors": {},
        "templates": {},
        "prefilter": {"color_threshold": 0.01},
        "confidence_threshold": 0.5,
        "weights": {"ocr": 0.4, "template": 0.3, "color": 0.2, "yolo": 0.1},
    }
    detection.update(detection_overrides)
    return {"detection": detection}


def test_service_weighted_color_success(monkeypatch, tmp_path):
    monkeypatch.setattr(service_module.cv2, "imread", lambda path: np.zeros((4, 4, 3)))
    config = _config(colors={"red": {"hsv_lower": [0, 0, 0], "hsv_upper": [10, 10, 10]}})

    result = ConfigTestService(str(tmp_path), matcher_cls=DummyMatcher).test_image(
        "game",
        config,
        "image.png",
    )

    assert result["is_kill"] is True
    assert result["booleans"]["color"] is True


def test_service_ocr_unavailable_adds_warning(monkeypatch, tmp_path):
    monkeypatch.setattr(service_module.cv2, "imread", lambda path: np.zeros((4, 4, 3)))
    monkeypatch.setattr(
        service_module,
        "get_ocr_service",
        lambda: MagicMock(detect=MagicMock(side_effect=service_module.OCRUnavailableError("missing"))),
    )
    config = _config(ocr={"enabled": True, "keywords": ["KILL"], "similarity_threshold": 0.8})

    result = ConfigTestService(str(tmp_path), matcher_cls=DummyMatcher).test_image(
        "game",
        config,
        "image.png",
    )

    assert result["details"]["ocr"]["available"] is False
    assert "OCR unavailable" in result["warnings"][0]


def test_service_rules_match_template(monkeypatch, tmp_path):
    monkeypatch.setattr(service_module.cv2, "imread", lambda path: np.zeros((4, 4, 3)))
    config = _config(
        templates={"kill": {"threshold": 0.8}},
        rules=[{"name": "template_only", "enabled": True, "require": ["template"]}],
    )

    result = ConfigTestService(str(tmp_path), matcher_cls=DummyMatcher).test_image(
        "game",
        config,
        "image.png",
    )

    assert result["mode"] == "rules"
    assert result["is_kill"] is True
    assert result["details"]["rules"][0]["matched"] is True


def test_weighted_confidence_reuses_signal_fusion_with_inactive_yolo_weight():
    detection_cfg = _config()["detection"]
    signals = {"ocr": 1.0, "template": 0.0, "color": 0.5, "yolo": 0.0}
    weights = dict(detection_cfg["weights"])
    weights["yolo"] = 0.0

    result = service_module.calculate_weighted_confidence(
        signals,
        detection_cfg,
        templates_loaded=False,
        ocr_active=True,
        yolo_active=False,
    )
    expected = WeightedSignalFusion().calculate(
        signals,
        weights,
        ocr_active=True,
        templates_active=False,
    )

    assert result == pytest.approx(expected)


def test_service_rules_use_shared_override_merge_for_template_threshold(monkeypatch, tmp_path):
    monkeypatch.setattr(service_module.cv2, "imread", lambda path: np.zeros((4, 4, 3)))
    config = _config(
        templates={"kill": {"threshold": 0.95}},
        rules=[
            {
                "name": "lower_template_threshold",
                "enabled": True,
                "require": ["template"],
                "detection_overrides": {"templates": {"kill": {"threshold": 0.8}}},
            }
        ],
    )

    result = ConfigTestService(str(tmp_path), matcher_cls=ScoredMatcher).test_image(
        "game",
        config,
        "image.png",
    )

    assert result["mode"] == "rules"
    assert result["is_kill"] is True
    assert result["details"]["rules"][0]["matched"] is True
    assert result["details"]["rules"][0]["signals"]["template"] == pytest.approx(0.85)
