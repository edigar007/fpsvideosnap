from typing import Any, Dict, Optional

import numpy as np

from src.ai.color_utils import get_hsv_bounds
from src.ai.signals import SignalResult


def roi_to_pixels(frame: np.ndarray, roi: list) -> list[int]:
    h, w = frame.shape[:2]
    return [int(roi[0] * w), int(roi[1] * h), int(roi[2] * w), int(roi[3] * h)]


class OCRSignalExtractor:
    def compute(self, frame: np.ndarray, ocr: Any, detection_cfg: Dict[str, Any], roi: list) -> float:
        ocr_cfg = detection_cfg.get("ocr", {})
        if not ocr_cfg.get("enabled", False) or not ocr:
            return 0.0

        keywords = ocr_cfg.get("keywords", ["击杀", "KILL"])
        threshold = ocr_cfg.get("similarity_threshold", 0.8)
        result = ocr.find_keywords(frame, keywords, roi=roi_to_pixels(frame, roi), threshold=threshold)
        if not result.get("found"):
            return 0.0

        confidence = result.get("confidence", 0.0)
        return confidence / 100.0 if confidence > 1.0 else confidence


class TemplateSignalExtractor:
    def compute(self, frame: np.ndarray, matcher: Any, detection_cfg: Dict[str, Any], default_roi: list) -> float:
        if not matcher.templates:
            return 0.0

        max_template_conf = 0.0
        templates_cfg = detection_cfg.get("templates", {})
        if not templates_cfg:
            for template_name in matcher.templates:
                loc, score = matcher.match_template(frame, template_name, threshold=0.8, roi=default_roi)
                if loc is not None:
                    max_template_conf = max(max_template_conf, score)
            return max_template_conf

        for template_name, template_cfg in templates_cfg.items():
            if template_name not in matcher.templates:
                continue

            threshold = 0.8
            template_roi = default_roi
            if isinstance(template_cfg, dict):
                threshold = template_cfg.get("threshold", 0.8)
                template_roi = template_cfg.get("roi", default_roi)

            loc, score = matcher.match_template(
                frame,
                template_name,
                threshold=threshold,
                roi=template_roi,
            )
            if loc is not None:
                max_template_conf = max(max_template_conf, score)

        return max_template_conf


class ColorSignalExtractor:
    def prefilter(
        self,
        frame: np.ndarray,
        matcher: Any,
        colors: Dict[str, Any],
        roi: list,
        color_threshold: float,
        enabled: bool = True,
    ) -> tuple[bool, Optional[float]]:
        if not enabled:
            return True, None

        if not colors:
            return True, 1.0

        max_color_pct = 0.0
        for color_cfg in colors.values():
            hsv_lower, hsv_upper = get_hsv_bounds(color_cfg)
            if hsv_lower and hsv_upper:
                pct = matcher.detect_color(frame, hsv_lower, hsv_upper, roi=roi)
                max_color_pct = max(max_color_pct, pct)

        return max_color_pct >= color_threshold, max_color_pct

    def compute(
        self,
        frame: np.ndarray,
        matcher: Any,
        detection_cfg: Dict[str, Any],
        roi: list,
        cached_color_pct: Optional[float] = None,
    ) -> float:
        if cached_color_pct is not None and not detection_cfg.get("_force_color_recompute"):
            return min(cached_color_pct * 50, 1.0)

        max_color_conf = 0.0
        for color_cfg in detection_cfg.get("colors", {}).values():
            hsv_lower, hsv_upper = get_hsv_bounds(color_cfg)
            if hsv_lower and hsv_upper:
                match_percent = matcher.detect_color(frame, hsv_lower, hsv_upper, roi=roi)
                max_color_conf = max(max_color_conf, min(match_percent * 50, 1.0))

        return max_color_conf


class YoloSignalExtractor:
    def compute(self, frame: np.ndarray, yolo: Any, yolo_conf: Optional[float] = None) -> float:
        if yolo_conf is not None:
            return yolo_conf

        detections = yolo.detect_single(frame)
        return max((d["conf"] for d in detections if d["name"] == "kill"), default=0.0)


class DetectionSignalExtractor:
    """Compute the normalized OCR/template/color/YOLO signal dictionary."""

    def __init__(
        self,
        ocr_extractor: OCRSignalExtractor = None,
        template_extractor: TemplateSignalExtractor = None,
        color_extractor: ColorSignalExtractor = None,
        yolo_extractor: YoloSignalExtractor = None,
    ):
        self.ocr = ocr_extractor or OCRSignalExtractor()
        self.template = template_extractor or TemplateSignalExtractor()
        self.color = color_extractor or ColorSignalExtractor()
        self.yolo = yolo_extractor or YoloSignalExtractor()

    def compute(
        self,
        frame: np.ndarray,
        yolo: Any,
        matcher: Any,
        ocr: Any,
        detection_cfg: Dict[str, Any],
        default_roi: list,
        cached_color_pct: Optional[float] = None,
        yolo_conf: Optional[float] = None,
    ) -> Dict[str, float]:
        roi = detection_cfg.get("killfeed_roi", default_roi)
        signals = {
            "ocr": self.ocr.compute(frame, ocr, detection_cfg, roi),
            "template": self.template.compute(frame, matcher, detection_cfg, roi),
            "yolo": self.yolo.compute(frame, yolo, yolo_conf=yolo_conf),
            "color": self.color.compute(
                frame,
                matcher,
                detection_cfg,
                roi,
                cached_color_pct=cached_color_pct,
            ),
        }
        return SignalResult.from_dict(signals).as_dict()

