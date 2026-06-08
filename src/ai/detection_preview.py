from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.ai.rule_engine import DetectionRuleEngine
from src.ai.rule_evaluator import RuleEvaluator
from src.ai.signal_evaluator import signals_to_booleans
from src.ai.signal_fusion import WeightedSignalFusion
from src.config.detection_view import DetectionConfigView


@dataclass(frozen=True)
class PreviewRuleEvaluation:
    matched: bool
    rule_results: List[Dict[str, Any]]
    warnings: List[str]


class DetectionPreviewEvaluator:
    """Evaluate Config Assistant preview signals with the production detection semantics."""

    def __init__(
        self,
        detection_cfg: Dict[str, Any],
        templates_loaded: Callable[[], bool] | bool,
        ocr_active: bool,
        yolo_active: bool = False,
    ):
        self.detection_view = DetectionConfigView.from_config(detection_cfg)
        self.detection_cfg = dict(self.detection_view.raw)
        self.templates_loaded = templates_loaded if callable(templates_loaded) else lambda: bool(templates_loaded)
        self.ocr_active = ocr_active
        self.yolo_active = yolo_active
        self.rule_engine = DetectionRuleEngine(self.detection_view, templates_loaded=self.templates_loaded)
        self.signal_fusion = WeightedSignalFusion()

    def merge_detection_config(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_engine.merge_detection_config(rule)

    def weighted_confidence(self, signals: Dict[str, float]) -> float:
        weights = dict(self.detection_view.weights)
        if not self.yolo_active:
            weights["yolo"] = 0.0
        return self.signal_fusion.calculate(
            signals,
            weights,
            ocr_active=self.ocr_active,
            templates_active=self.templates_loaded(),
        )

    def signal_booleans(
        self,
        signals: Dict[str, float],
        detection_cfg: Optional[Dict[str, Any]] = None,
        cached_color_pct: Optional[float] = None,
    ) -> Dict[str, bool]:
        return signals_to_booleans(
            signals,
            detection_cfg or self.detection_cfg,
            cached_color_pct=cached_color_pct,
            templates_loaded=self.templates_loaded(),
        )

    def evaluate_rules(
        self,
        compute_signals: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> PreviewRuleEvaluation:
        rule_results = []
        warnings = []

        for rule in self.detection_view.enabled_rule_dicts:
            effective_cfg = self.merge_detection_config(rule)
            result = compute_signals(effective_cfg)
            booleans = result["booleans"]
            evaluation = RuleEvaluator.evaluate([rule], booleans)
            required = list(rule.get("require", []) or [])
            missing = evaluation.failed_reasons.get(rule.get("name", "unnamed"), [])

            if "yolo" in required:
                warnings.append(
                    f"Rule '{rule.get('name', 'unnamed')}' requires YOLO, "
                    "which is not run by this test."
                )

            rule_results.append({
                "name": rule.get("name", "unnamed"),
                "enabled": True,
                "require": required,
                "matched": evaluation.matched,
                "missing": missing,
                "signals": result["signals"],
                "booleans": booleans,
            })

        return PreviewRuleEvaluation(
            matched=any(item["matched"] for item in rule_results),
            rule_results=rule_results,
            warnings=warnings,
        )
