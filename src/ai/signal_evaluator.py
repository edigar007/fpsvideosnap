from typing import Any, Dict, Optional


def signals_to_booleans(
    signals: Dict[str, float],
    detection_cfg: Dict[str, Any],
    cached_color_pct: Optional[float] = None,
    templates_loaded: bool = True,
) -> Dict[str, bool]:
    """Convert numeric detection signals into rule booleans."""
    prefilter_cfg = detection_cfg.get("prefilter", {}) or {}
    color_threshold = float(prefilter_cfg.get("color_threshold", 0.01))

    if cached_color_pct is not None:
        color_bool = cached_color_pct >= color_threshold
    else:
        color_bool = float(signals.get("color", 0.0) or 0.0) > 0

    template_bool = False
    template_score = float(signals.get("template", 0.0) or 0.0)
    templates_cfg = detection_cfg.get("templates", {}) or {}
    if templates_loaded:
        if not templates_cfg:
            template_bool = template_score >= 0.8
        else:
            for t_cfg in templates_cfg.values():
                threshold = t_cfg.get("threshold", 0.8) if isinstance(t_cfg, dict) else 0.8
                if template_score >= threshold:
                    template_bool = True
                    break

    return {
        "ocr": float(signals.get("ocr", 0.0) or 0.0) > 0,
        "yolo": float(signals.get("yolo", 0.0) or 0.0) > 0,
        "color": color_bool,
        "template": template_bool,
    }
