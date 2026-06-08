import numpy as np
import pytest
from unittest.mock import MagicMock

from src.ai.signal_extractors import (
    ColorSignalExtractor,
    DetectionSignalExtractor,
    OCRSignalExtractor,
    TemplateSignalExtractor,
    YoloSignalExtractor,
    roi_to_pixels,
)
from src.ai.signal_fusion import WeightedSignalFusion


def test_roi_to_pixels_converts_relative_roi():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)

    assert roi_to_pixels(frame, [0.1, 0.2, 0.3, 0.4]) == [20, 20, 60, 40]


def test_ocr_signal_extractor_passes_threshold_and_normalizes_confidence():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    ocr = MagicMock()
    ocr.find_keywords.return_value = {"found": True, "confidence": 95.0}
    cfg = {"ocr": {"enabled": True, "keywords": ["KILL"], "similarity_threshold": 0.95}}

    result = OCRSignalExtractor().compute(frame, ocr, cfg, [0, 0, 1, 1])

    assert result == pytest.approx(0.95)
    ocr.find_keywords.assert_called_once_with(
        frame,
        ["KILL"],
        roi=[0, 0, 100, 100],
        threshold=0.95,
    )


def test_template_signal_extractor_uses_configured_threshold_and_roi():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    matcher = MagicMock()
    matcher.templates = {"kill": object()}
    matcher.match_template.return_value = ((1, 2), 0.91)
    template_roi = [0.2, 0.3, 0.4, 0.5]
    cfg = {"templates": {"kill": {"threshold": 0.9, "roi": template_roi}}}

    result = TemplateSignalExtractor().compute(frame, matcher, cfg, [0, 0, 1, 1])

    assert result == pytest.approx(0.91)
    matcher.match_template.assert_called_once_with(frame, "kill", threshold=0.9, roi=template_roi)


def test_color_signal_extractor_prefilter_disabled_skips_color_detection():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    matcher = MagicMock()

    passed, cached = ColorSignalExtractor().prefilter(
        frame,
        matcher,
        colors={"red": {"hsv_lower": [0, 0, 0], "hsv_upper": [10, 255, 255]}},
        roi=[0, 0, 1, 1],
        color_threshold=0.5,
        enabled=False,
    )

    assert passed is True
    assert cached is None
    matcher.detect_color.assert_not_called()


def test_yolo_signal_extractor_uses_cached_confidence():
    yolo = MagicMock()

    result = YoloSignalExtractor().compute(np.zeros((1, 1, 3), dtype=np.uint8), yolo, yolo_conf=0.77)

    assert result == pytest.approx(0.77)
    yolo.detect_single.assert_not_called()


def test_detection_signal_extractor_combines_signals():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    yolo = MagicMock()
    yolo.detect_single.return_value = [{"name": "kill", "conf": 0.6}]
    matcher = MagicMock()
    matcher.templates = {}
    matcher.detect_color.return_value = 0.02
    ocr = MagicMock()
    ocr.find_keywords.return_value = {"found": False, "confidence": 0.0}

    result = DetectionSignalExtractor().compute(
        frame,
        yolo,
        matcher,
        ocr,
        {
            "killfeed_roi": [0, 0, 1, 1],
            "ocr": {"enabled": True, "keywords": ["KILL"]},
            "colors": {"red": {"hsv_lower": [0, 0, 0], "hsv_upper": [10, 255, 255]}},
        },
        [0, 0, 1, 1],
    )

    assert result == {
        "ocr": 0.0,
        "template": 0.0,
        "color": 1.0,
        "yolo": 0.6,
    }


def test_weighted_signal_fusion_normalizes_active_weights():
    result = WeightedSignalFusion().calculate(
        {"ocr": 1.0, "template": 0.0, "color": 0.5, "yolo": 0.0},
        {"ocr": 0.4, "template": 0.3, "color": 0.2, "yolo": 0.1},
        ocr_active=True,
        templates_active=False,
    )

    assert result == pytest.approx((1.0 * 0.4 / 0.7) + (0.5 * 0.2 / 0.7))

