from dataclasses import dataclass, field
from typing import Any, Mapping

DEFAULT_SIGNAL_WEIGHTS = {
    "ocr": 0.4,
    "template": 0.3,
    "color": 0.2,
    "yolo": 0.1,
}
DETECTION_SIGNALS = ("ocr", "template", "color", "yolo")
DEFAULT_ROI = (0.0, 0.0, 1.0, 1.0)


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return bool(value)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalize_roi(value: Any) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return DEFAULT_ROI

    try:
        x, y, w, h = [float(part) for part in value]
    except (TypeError, ValueError):
        return DEFAULT_ROI

    return (x, y, w, h)


@dataclass(frozen=True)
class OCRConfigView:
    """Typed read view for detection.ocr."""

    raw: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = False
    required: bool = False
    keywords: tuple[str, ...] = field(default_factory=tuple)
    similarity_threshold: float = 0.8
    lang: str = "ch"
    use_gpu: bool = True

    @classmethod
    def from_config(cls, ocr_config: Mapping[str, Any] | None) -> "OCRConfigView":
        ocr_config = dict(_as_mapping(ocr_config))
        return cls(
            raw=ocr_config,
            enabled=_as_bool(ocr_config.get("enabled"), False),
            required=_as_bool(ocr_config.get("required"), False),
            keywords=tuple(str(keyword) for keyword in ocr_config.get("keywords", []) or []),
            similarity_threshold=_as_float(
                ocr_config.get("similarity_threshold", ocr_config.get("threshold", 0.8)),
                0.8,
            ),
            lang=str(ocr_config.get("lang", "ch")),
            use_gpu=_as_bool(ocr_config.get("use_gpu"), True),
        )


@dataclass(frozen=True)
class TemplateConfigView:
    """Typed read view for detection.templates."""

    raw: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, templates_config: Mapping[str, Any] | None) -> "TemplateConfigView":
        return cls(raw=dict(_as_mapping(templates_config)))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(str(name) for name in self.raw.keys())

    def threshold_for(self, template_name: str, default: float = 0.8) -> float:
        template_cfg = self.raw.get(template_name, {})
        if not isinstance(template_cfg, Mapping):
            return default
        return _as_float(template_cfg.get("threshold", default), default)

    def roi_for(self, template_name: str, default_roi: list[float]) -> list[float]:
        template_cfg = self.raw.get(template_name, {})
        if not isinstance(template_cfg, Mapping):
            return default_roi
        roi = template_cfg.get("roi", default_roi)
        return list(_normalize_roi(roi)) if roi is not default_roi else default_roi


@dataclass(frozen=True)
class ColorConfigView:
    """Typed read view for detection.colors."""

    raw: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, colors_config: Mapping[str, Any] | None) -> "ColorConfigView":
        return cls(raw=dict(_as_mapping(colors_config)))

    @property
    def items(self) -> tuple[tuple[str, Mapping[str, Any]], ...]:
        return tuple(
            (str(name), cfg)
            for name, cfg in self.raw.items()
            if isinstance(cfg, Mapping)
        )

    @property
    def values(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(cfg for _name, cfg in self.items)


@dataclass(frozen=True)
class PrefilterConfigView:
    """Typed read view for detection.prefilter."""

    raw: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True
    color_threshold: float = 0.01

    @classmethod
    def from_config(cls, prefilter_config: Mapping[str, Any] | None) -> "PrefilterConfigView":
        prefilter_config = dict(_as_mapping(prefilter_config))
        return cls(
            raw=prefilter_config,
            enabled=_as_bool(prefilter_config.get("enabled"), True),
            color_threshold=_as_float(prefilter_config.get("color_threshold", 0.01), 0.01),
        )


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
    killfeed_roi: tuple[float, float, float, float] = DEFAULT_ROI
    confidence_threshold: float = 0.5
    weights: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_SIGNAL_WEIGHTS))
    ocr: OCRConfigView = field(default_factory=OCRConfigView)
    templates: TemplateConfigView = field(default_factory=TemplateConfigView)
    colors: ColorConfigView = field(default_factory=ColorConfigView)
    prefilter: PrefilterConfigView = field(default_factory=PrefilterConfigView)
    rules: tuple[DetectionRuleView, ...] = field(default_factory=tuple)
    signals: tuple[str, ...] = DETECTION_SIGNALS

    @classmethod
    def from_config(cls, detection_config: Mapping[str, Any] | None) -> "DetectionConfigView":
        detection_config = dict(detection_config or {})
        weights = {
            signal: _as_float((detection_config.get("weights") or {}).get(signal, default), default)
            for signal, default in DEFAULT_SIGNAL_WEIGHTS.items()
        }
        rules = tuple(
            DetectionRuleView.from_dict(rule)
            for rule in detection_config.get("rules", []) or []
            if isinstance(rule, Mapping)
        )
        return cls(
            raw=detection_config,
            killfeed_roi=_normalize_roi(detection_config.get("killfeed_roi", DEFAULT_ROI)),
            confidence_threshold=_as_float(detection_config.get("confidence_threshold", 0.5), 0.5),
            weights=weights,
            ocr=OCRConfigView.from_config(detection_config.get("ocr")),
            templates=TemplateConfigView.from_config(detection_config.get("templates")),
            colors=ColorConfigView.from_config(detection_config.get("colors")),
            prefilter=PrefilterConfigView.from_config(detection_config.get("prefilter")),
            rules=rules,
        )

    @property
    def rule_dicts(self) -> list[dict[str, Any]]:
        return [rule.as_dict() for rule in self.rules]

    @property
    def enabled_rule_dicts(self) -> list[dict[str, Any]]:
        return [rule.as_dict() for rule in self.rules if rule.enabled]
