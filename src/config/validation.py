from typing import Any, Dict


VALID_CONFIG_VERSION = 1


def validate_config(config: Dict[str, Any]) -> None:
    """Validate critical configuration fields."""
    config_version = config.get("config_version")
    if config_version is not None and config_version != VALID_CONFIG_VERSION:
        raise ValueError(f"config_version must be {VALID_CONFIG_VERSION}")

    video = config.get("video", {})
    frame_extraction_mode = video.get("frame_extraction_mode")
    if frame_extraction_mode is not None and frame_extraction_mode not in {"bulk", "precise"}:
        raise ValueError("video.frame_extraction_mode must be 'bulk' or 'precise'")

    highlights = config.get("highlights", {})
    for key in ("pre_kill_time", "post_kill_time"):
        if key in highlights and (
            not isinstance(highlights[key], (int, float)) or highlights[key] < 0
        ):
            raise ValueError(f"highlights.{key} must be a non-negative number")

    for key in ("game_volume", "music_volume"):
        if key in highlights and (
            not isinstance(highlights[key], (int, float)) or not 0 <= highlights[key] <= 1
        ):
            raise ValueError(f"highlights.{key} must be between 0 and 1")

    if "detection" not in config:
        return

    det = config["detection"]

    if "killfeed_roi" in det:
        validate_roi(det["killfeed_roi"], "detection.killfeed_roi")

    if "templates" in det and isinstance(det["templates"], dict):
        for name, template_cfg in det["templates"].items():
            if isinstance(template_cfg, dict) and "roi" in template_cfg:
                validate_roi(template_cfg["roi"], f"detection.templates.{name}.roi")

    if "colors" in det and isinstance(det["colors"], dict):
        for name, color_cfg in det["colors"].items():
            if not isinstance(color_cfg, dict):
                raise ValueError(f"detection.colors.{name} must be a dict")
            for key in ("hsv_lower", "hsv_upper"):
                if key in color_cfg:
                    validate_hsv(color_cfg[key], f"detection.colors.{name}.{key}")

    if "ocr" in det:
        ocr = det["ocr"]
        if not isinstance(ocr.get("enabled"), bool):
            raise ValueError("detection.ocr.enabled must be a boolean")
        if not isinstance(ocr.get("keywords"), list):
            raise ValueError("detection.ocr.keywords must be a list")
        if not 0 <= ocr.get("similarity_threshold", 0) <= 1:
            raise ValueError("detection.ocr.similarity_threshold must be between 0 and 1")

    if "weights" in det:
        weights = det["weights"]
        positive_count = 0
        for key, value in weights.items():
            if not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"Weight for {key} must be a non-negative number")
            if value > 0:
                positive_count += 1
        if weights and positive_count == 0:
            raise ValueError("detection.weights must contain at least one positive value")

    if "prefilter" in det:
        pre = det["prefilter"]
        if "color_threshold" in pre and not 0 <= pre["color_threshold"] <= 1:
            raise ValueError("detection.prefilter.color_threshold must be between 0 and 1")

    if "rules" in det:
        validate_rules(det["rules"])


def validate_roi(roi: Any, field_name: str) -> None:
    if (
        not isinstance(roi, list)
        or len(roi) != 4
        or not all(isinstance(value, (int, float)) for value in roi)
    ):
        raise ValueError(f"{field_name} must be a list of 4 numbers")

    _x, _y, width, height = roi
    if not all(0.0 <= value <= 1.0 for value in roi):
        raise ValueError(f"{field_name} values must be between 0.0 and 1.0")
    if width <= 0 or height <= 0:
        raise ValueError(f"{field_name} width and height must be greater than 0")


def validate_hsv(hsv: Any, field_name: str) -> None:
    if (
        not isinstance(hsv, list)
        or len(hsv) != 3
        or not all(isinstance(value, (int, float)) for value in hsv)
    ):
        raise ValueError(f"{field_name} must be a list of 3 numbers")

    hue, saturation, value = hsv
    if not 0 <= hue <= 180:
        raise ValueError(f"{field_name}[0] hue must be between 0 and 180")
    if not 0 <= saturation <= 255:
        raise ValueError(f"{field_name}[1] saturation must be between 0 and 255")
    if not 0 <= value <= 255:
        raise ValueError(f"{field_name}[2] value must be between 0 and 255")


def validate_rules(rules: Any) -> None:
    if not isinstance(rules, list):
        raise ValueError("detection.rules must be a list")

    allowed_signals = {"ocr", "template", "color", "yolo"}
    seen_names = set()

    for i, rule in enumerate(rules):
        prefix = f"detection.rules[{i}]"

        if not isinstance(rule, dict):
            raise ValueError(f"{prefix} must be a dict")

        name = rule.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{prefix}.name must be a non-empty string")

        if name in seen_names:
            raise ValueError(f"detection.rules: duplicate name '{name}'")
        seen_names.add(name)

        enabled = rule.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError(f"{prefix}.enabled must be a boolean")

        require = rule.get("require")
        if not isinstance(require, list):
            raise ValueError(f"{prefix}.require must be a list")

        if len(require) == 0:
            raise ValueError(f"{prefix}.require must not be empty")

        for j, signal in enumerate(require):
            if not isinstance(signal, str) or signal not in allowed_signals:
                raise ValueError(
                    f"{prefix}.require[{j}] '{signal}' is not a valid signal. "
                    f"Allowed: {', '.join(sorted(allowed_signals))}"
                )

        overrides = rule.get("detection_overrides", {})
        if overrides:
            _validate_rule_overrides(overrides, prefix)


def _validate_rule_overrides(overrides: Dict[str, Any], prefix: str) -> None:
    if not isinstance(overrides, dict):
        raise ValueError(f"{prefix}.detection_overrides must be a dict")
    if "killfeed_roi" in overrides:
        validate_roi(overrides["killfeed_roi"], f"{prefix}.detection_overrides.killfeed_roi")
    if "ocr" in overrides:
        ocr_override = overrides["ocr"]
        if not isinstance(ocr_override, dict):
            raise ValueError(f"{prefix}.detection_overrides.ocr must be a dict")
        threshold = ocr_override.get("similarity_threshold")
        if threshold is not None and not 0 <= threshold <= 1:
            raise ValueError(
                f"{prefix}.detection_overrides.ocr.similarity_threshold "
                "must be between 0 and 1"
            )
    if "colors" in overrides and isinstance(overrides["colors"], dict):
        for color_name, color_cfg in overrides["colors"].items():
            if not isinstance(color_cfg, dict):
                raise ValueError(f"{prefix}.detection_overrides.colors.{color_name} must be a dict")
            for key in ("hsv_lower", "hsv_upper"):
                if key in color_cfg:
                    validate_hsv(
                        color_cfg[key],
                        f"{prefix}.detection_overrides.colors.{color_name}.{key}",
                    )
