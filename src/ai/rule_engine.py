import json
from typing import Any, Callable, Dict, Optional

from src.ai.rule_evaluator import RuleEvaluator
from src.ai.signal_evaluator import signals_to_booleans
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DetectionRuleEngine:
    """Evaluate detection.rules and isolate per-rule override handling."""

    SIGNAL_AFFECTING_OVERRIDE_KEYS = {
        "killfeed_roi",
        "ocr",
        "templates",
        "colors",
        "prefilter",
        "_force_color_recompute",
    }

    def __init__(self, detection_config: Dict[str, Any], templates_loaded: Callable[[], bool]):
        self.detection_config = detection_config
        self.rules = detection_config.get("rules", [])
        self.templates_loaded = templates_loaded
        self._config_cache: Dict[tuple, Dict[str, Any]] = {}

    def merge_detection_config(self, rule: dict) -> dict:
        """Merge rule.detection_overrides with global detection config."""
        overrides = rule.get("detection_overrides", {})
        cache_key = (
            rule.get("name", ""),
            json.dumps(overrides, sort_keys=True, ensure_ascii=False, default=str),
        )

        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        detection_cfg = self.detection_config.copy()
        if not overrides:
            self._config_cache[cache_key] = detection_cfg
            return detection_cfg

        for key, value in overrides.items():
            if key in detection_cfg and isinstance(detection_cfg[key], dict) and isinstance(value, dict):
                detection_cfg[key] = {**detection_cfg[key], **value}
            else:
                detection_cfg[key] = value

        self._config_cache[cache_key] = detection_cfg
        return detection_cfg

    def overrides_affect_signal_calculation(self, overrides: dict) -> bool:
        """Return True when rule overrides require fresh OCR/template/color signal computation."""
        if not overrides:
            return False
        return any(key in self.SIGNAL_AFFECTING_OVERRIDE_KEYS for key in overrides)

    def _signal_booleans(
        self,
        signals: dict,
        detection_cfg: dict,
        cached_color_pct: Optional[float] = None,
    ) -> dict:
        return signals_to_booleans(
            signals,
            detection_cfg,
            cached_color_pct=cached_color_pct,
            templates_loaded=self.templates_loaded(),
        )

    def evaluate(
        self,
        frame,
        signals: Dict,
        compute_signals: Callable[[Any, dict, Optional[float], Optional[float]], dict],
        cached_color_pct: Optional[float] = None,
        yolo_conf: Optional[float] = None,
    ) -> Optional[bool]:
        """
        Evaluate OR-of-AND rules.

        Returns True if any rule matches, False if rules exist but none match, None if no rules are configured.
        """
        if not self.rules:
            return None

        enabled_rules = [rule for rule in self.rules if rule.get("enabled", True)]
        if not enabled_rules:
            return False

        reusable_rules = []

        for rule in enabled_rules:
            overrides = rule.get("detection_overrides", {})
            if not self.overrides_affect_signal_calculation(overrides):
                reusable_rules.append(rule)
                continue

            effective_cfg = self.merge_detection_config(rule)
            rule_signals = compute_signals(frame, effective_cfg, cached_color_pct, yolo_conf)
            signal_booleans = self._signal_booleans(rule_signals, effective_cfg, cached_color_pct)
            evaluation = RuleEvaluator.evaluate([rule], signal_booleans)
            if evaluation.matched:
                logger.debug(f"Rule matched: {evaluation.rule_name}")
                return True

        if reusable_rules:
            signal_booleans = self._signal_booleans(signals, self.detection_config, cached_color_pct)
            evaluation = RuleEvaluator.evaluate(reusable_rules, signal_booleans)
            if evaluation.matched:
                logger.debug(f"Rule matched: {evaluation.rule_name}")
                return True

        return False

