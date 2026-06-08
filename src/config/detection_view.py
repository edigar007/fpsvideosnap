from dataclasses import dataclass, field
from typing import Any, Mapping

DEFAULT_SIGNAL_WEIGHTS = {
    "ocr": 0.4,
    "template": 0.3,
    "color": 0.2,
    "yolo": 0.1,
}
DETECTION_SIGNALS = ("ocr", "template", "color", "yolo")


@dataclass(frozen=True)
class DetectionRuleView:
    """Typed read view for one detection rule."""

    name: str
    enabled: bool = True
    require: tuple[str, ...] = field(default_factory=tuple)
    detection_overrides: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, rule: Mapping[str, Any]) -> "DetectionRuleView":
        return cls(
            name=str(rule.get("name", "")),
            enabled=bool(rule.get("enabled", True)),
            require=tuple(str(signal) for signal in rule.get("require", []) or []),
            detection_overrides=dict(rule.get("detection_overrides", {}) or {}),
        )

    def as_dict(self) -> dict[str, Any]:
        values = {
            "name": self.name,
            "enabled": self.enabled,
            "require": list(self.require),
        }
        if self.detection_overrides:
            values["detection_overrides"] = dict(self.detection_overrides)
        return values


@dataclass(frozen=True)
class DetectionConfigView:
    """Typed read view for high-traffic detection config fields."""

    raw: Mapping[str, Any]
    confidence_threshold: float = 0.5
    weights: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_SIGNAL_WEIGHTS))
    rules: tuple[DetectionRuleView, ...] = field(default_factory=tuple)
    signals: tuple[str, ...] = DETECTION_SIGNALS

    @classmethod
    def from_config(cls, detection_config: Mapping[str, Any] | None) -> "DetectionConfigView":
        detection_config = dict(detection_config or {})
        weights = {
            signal: float((detection_config.get("weights") or {}).get(signal, default))
            for signal, default in DEFAULT_SIGNAL_WEIGHTS.items()
        }
        rules = tuple(
            DetectionRuleView.from_dict(rule)
            for rule in detection_config.get("rules", []) or []
            if isinstance(rule, Mapping)
        )
        return cls(
            raw=detection_config,
            confidence_threshold=float(detection_config.get("confidence_threshold", 0.5)),
            weights=weights,
            rules=rules,
        )

    @property
    def rule_dicts(self) -> list[dict[str, Any]]:
        return [rule.as_dict() for rule in self.rules]

    @property
    def enabled_rule_dicts(self) -> list[dict[str, Any]]:
        return [rule.as_dict() for rule in self.rules if rule.enabled]
