from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from src.ai.color_utils import get_hsv_bounds
from src.ai.detection_preview import DetectionPreviewEvaluator
from src.ai.opencv_matcher import OpenCVMatcher
from src.tools.config_assistant.ocr_service import OCRUnavailableError, get_ocr_service
from src.utils.logger import get_logger

logger = get_logger("config_assistant.config_test_service")


def normalize_roi(roi: Optional[List[float]]) -> List[float]:
    """Clamp a normalized [x, y, w, h] ROI to image-relative bounds."""
    if not isinstance(roi, list) or len(roi) != 4:
        return [0.0, 0.0, 1.0, 1.0]

    try:
        x, y, w, h = [float(v) for v in roi]
    except (TypeError, ValueError):
        return [0.0, 0.0, 1.0, 1.0]

    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.0, min(1.0 - x, w))
    h = max(0.0, min(1.0 - y, h))

    if w <= 0.0 or h <= 0.0:
        return [0.0, 0.0, 1.0, 1.0]
    return [x, y, w, h]


def merge_detection_config(detection_cfg: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
    """Merge rule.detection_overrides into the global detection config."""
    return DetectionPreviewEvaluator(
        detection_cfg,
        templates_loaded=False,
        ocr_active=False,
    ).merge_detection_config(rule)


def text_similarity(text: str, keyword: str) -> float:
    """Return a simple fuzzy similarity in the OCRDetector 0.0-1.0 range."""
    if not text or not keyword:
        return 0.0
    return SequenceMatcher(None, text.lower(), keyword.lower()).ratio()


def match_ocr_keywords(detections: List[Dict[str, Any]], ocr_cfg: Dict[str, Any]) -> Dict[str, Any]:
    keywords = ocr_cfg.get("keywords", []) or []
    threshold = float(ocr_cfg.get("similarity_threshold", ocr_cfg.get("threshold", 0.8)))

    best = {
        "found": False,
        "signal": 0.0,
        "matched_keyword": None,
        "text": None,
        "similarity": 0.0,
        "confidence": 0.0,
    }

    for det in detections:
        text = str(det.get("text", "")).strip()
        confidence = float(det.get("confidence", 0.0) or 0.0)
        for keyword in keywords:
            similarity = text_similarity(text, str(keyword))
            if similarity >= threshold and similarity > best["similarity"]:
                best.update({
                    "found": True,
                    "signal": confidence,
                    "matched_keyword": keyword,
                    "text": text,
                    "similarity": similarity,
                    "confidence": confidence,
                })

    return best


def calculate_weighted_confidence(
    signals: Dict[str, float],
    detection_cfg: Dict[str, Any],
    templates_loaded: bool,
    ocr_active: bool,
    yolo_active: bool = False,
) -> float:
    return DetectionPreviewEvaluator(
        detection_cfg,
        templates_loaded=templates_loaded,
        ocr_active=ocr_active,
        yolo_active=yolo_active,
    ).weighted_confidence(signals)


class ConfigTestService:
    def __init__(self, project_root: str, matcher_cls: type[OpenCVMatcher] = OpenCVMatcher):
        self.project_root = project_root
        self.matcher_cls = matcher_cls

    def test_image(self, game: str, config: Dict[str, Any], image_path: str) -> Dict[str, Any]:
        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError("Failed to load image")

        detection_cfg = config.get("detection", {}) or {}
        matcher = self.matcher_cls()
        matcher.load_templates_from_config(detection_cfg, self.project_root)

        base_result = self._evaluate_test_signals(frame, image_path, detection_cfg, matcher)
        warnings = list(base_result.get("warnings", []))

        prefilter_passed = True
        if detection_cfg.get("colors"):
            prefilter_passed = bool(base_result["booleans"]["color"])

        ocr_required = bool((detection_cfg.get("ocr", {}) or {}).get("required", False))
        if ocr_required and not base_result["booleans"]["ocr"]:
            prefilter_passed = False
            warnings.append("OCR is marked required but no OCR keyword matched.")

        rules = detection_cfg.get("rules", []) or []
        rule_results = []
        mode = "weighted"
        confidence = 0.0
        is_kill = False

        if not prefilter_passed:
            confidence = 0.0
            is_kill = False
        elif rules:
            mode = "rules"
            is_kill, rule_results, rule_warnings = self._evaluate_rules_for_test(
                frame,
                image_path,
                detection_cfg,
                matcher,
            )
            warnings.extend(rule_warnings)
            confidence = 1.0 if is_kill else 0.0
        else:
            confidence = calculate_weighted_confidence(
                base_result["signals"],
                detection_cfg,
                templates_loaded=base_result["templates"]["loaded_count"] > 0,
                ocr_active=(
                    bool((detection_cfg.get("ocr", {}) or {}).get("enabled", False))
                    and base_result["ocr"]["available"]
                ),
            )
            confidence_threshold = float(detection_cfg.get("confidence_threshold", 0.5))
            is_kill = confidence >= confidence_threshold

        return {
            "game": game,
            "image_path": image_path,
            "status": "success" if is_kill else "failure",
            "is_kill": is_kill,
            "confidence": confidence,
            "confidence_threshold": float(detection_cfg.get("confidence_threshold", 0.5)),
            "mode": mode,
            "prefilter_passed": prefilter_passed,
            "signals": base_result["signals"],
            "booleans": base_result["booleans"],
            "details": {
                "roi": base_result["roi"],
                "color": base_result["color"],
                "templates": base_result["templates"],
                "ocr": base_result["ocr"],
                "yolo": base_result["yolo"],
                "rules": rule_results,
            },
            "warnings": warnings,
        }

    def _evaluate_test_signals(
        self,
        frame: np.ndarray,
        image_path: str,
        detection_cfg: Dict[str, Any],
        matcher: OpenCVMatcher,
    ) -> Dict[str, Any]:
        """Run local, single-image signals used by the config assistant test endpoint."""
        roi = normalize_roi(detection_cfg.get("killfeed_roi", [0, 0, 1, 1]))
        prefilter_cfg = detection_cfg.get("prefilter", {}) or {}
        color_threshold = float(prefilter_cfg.get("color_threshold", 0.01))

        color_details = []
        max_color_pct = 0.0
        for color_name, color_cfg in (detection_cfg.get("colors", {}) or {}).items():
            if not isinstance(color_cfg, dict):
                continue
            hsv_lower, hsv_upper = get_hsv_bounds(color_cfg)
            if not hsv_lower or not hsv_upper:
                color_details.append({
                    "name": color_name,
                    "matched": False,
                    "match_percent": 0.0,
                    "error": "HSV range missing",
                })
                continue

            match_percent = matcher.detect_color(frame, hsv_lower, hsv_upper, roi=roi)
            max_color_pct = max(max_color_pct, match_percent)
            color_details.append({
                "name": color_name,
                "matched": match_percent >= color_threshold,
                "match_percent": match_percent,
                "threshold": color_threshold,
                "hsv_lower": hsv_lower,
                "hsv_upper": hsv_upper,
            })

        color_signal = min(max_color_pct * 50, 1.0)
        template_details, max_template_score = self._evaluate_templates(
            frame,
            detection_cfg,
            matcher,
            roi,
        )
        ocr_details, warnings = self._evaluate_ocr(image_path, detection_cfg, roi)

        signals = {
            "ocr": float(ocr_details["match"]["signal"]),
            "template": float(max_template_score),
            "color": float(color_signal),
            "yolo": 0.0,
        }
        evaluator = DetectionPreviewEvaluator(
            detection_cfg,
            templates_loaded=bool(template_details),
            ocr_active=bool(ocr_details["available"]),
            yolo_active=False,
        )

        return {
            "roi": roi,
            "signals": signals,
            "booleans": evaluator.signal_booleans(
                signals,
                detection_cfg=detection_cfg,
                cached_color_pct=max_color_pct,
            ),
            "color": {
                "max_match_percent": max_color_pct,
                "threshold": color_threshold,
                "items": color_details,
            },
            "templates": {
                "loaded_count": len(matcher.templates),
                "items": template_details,
            },
            "ocr": ocr_details,
            "yolo": {
                "available": False,
                "signal": 0.0,
                "note": "YOLO is not run inside the config assistant image test.",
            },
            "warnings": warnings,
        }

    def _evaluate_templates(
        self,
        frame: np.ndarray,
        detection_cfg: Dict[str, Any],
        matcher: OpenCVMatcher,
        roi: List[float],
    ) -> Tuple[List[Dict[str, Any]], float]:
        template_details = []
        max_template_score = 0.0
        templates_cfg = detection_cfg.get("templates", {}) or {}
        template_names = list(templates_cfg.keys()) if templates_cfg else list(matcher.templates.keys())

        for template_name in template_names:
            template_cfg = templates_cfg.get(template_name, {}) if isinstance(templates_cfg, dict) else {}
            threshold = template_cfg.get("threshold", 0.8) if isinstance(template_cfg, dict) else 0.8
            location, score = matcher.match_template(frame, template_name, threshold=threshold, roi=roi)
            max_template_score = max(max_template_score, float(score or 0.0))
            template_details.append({
                "name": template_name,
                "matched": location is not None,
                "score": float(score or 0.0),
                "threshold": threshold,
                "loaded": template_name in matcher.templates,
            })

        return template_details, max_template_score

    def _evaluate_ocr(
        self,
        image_path: str,
        detection_cfg: Dict[str, Any],
        roi: List[float],
    ) -> Tuple[Dict[str, Any], List[str]]:
        ocr_cfg = detection_cfg.get("ocr", {}) or {}
        ocr_details = {
            "enabled": bool(ocr_cfg.get("enabled", False)),
            "available": False,
            "detections": [],
            "match": {
                "found": False,
                "signal": 0.0,
                "matched_keyword": None,
                "text": None,
                "similarity": 0.0,
                "confidence": 0.0,
            },
        }
        warnings = []

        if ocr_details["enabled"]:
            try:
                ocr_service = get_ocr_service()
                detections = ocr_service.detect(image_path, roi)
                ocr_details["available"] = True
                ocr_details["detections"] = detections
                ocr_details["match"] = match_ocr_keywords(detections, ocr_cfg)
            except OCRUnavailableError as e:
                warnings.append(f"OCR unavailable: {e}")
                ocr_details["error"] = str(e)
            except Exception as e:
                logger.error(f"Config test OCR failed: {e}", exc_info=True)
                warnings.append(f"OCR failed: {e}")
                ocr_details["error"] = str(e)

        return ocr_details, warnings

    def _evaluate_rules_for_test(
        self,
        frame: np.ndarray,
        image_path: str,
        detection_cfg: Dict[str, Any],
        matcher: OpenCVMatcher,
    ) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
        evaluator = DetectionPreviewEvaluator(
            detection_cfg,
            templates_loaded=lambda: bool(matcher.templates),
            ocr_active=bool((detection_cfg.get("ocr", {}) or {}).get("enabled", False)),
            yolo_active=False,
        )
        evaluation = evaluator.evaluate_rules(
            lambda effective_cfg: self._evaluate_test_signals(frame, image_path, effective_cfg, matcher)
        )
        return evaluation.matched, evaluation.rule_results, evaluation.warnings
