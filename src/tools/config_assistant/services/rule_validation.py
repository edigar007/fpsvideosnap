VALID_SIGNALS = {"ocr", "template", "color", "yolo"}


def validate_rules(rules):
    """Validate rules structure. Raises ValueError with descriptive message on failure."""
    if not isinstance(rules, list):
        raise ValueError("detection.rules must be a list")

    seen_names = set()
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"detection.rules[{i}] must be a dict")

        if "name" not in rule:
            raise ValueError(f"detection.rules[{i}].name is required")
        if "enabled" not in rule:
            raise ValueError(f"detection.rules[{i}].enabled is required")
        if "require" not in rule:
            raise ValueError(f"detection.rules[{i}].require is required")

        name = rule["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"detection.rules[{i}].name must be a non-empty string")

        if not isinstance(rule["enabled"], bool):
            raise ValueError(f"detection.rules[{i}].enabled must be a boolean")

        require = rule["require"]
        if not isinstance(require, list):
            raise ValueError(f"detection.rules[{i}].require must be a list")
        if len(require) == 0:
            raise ValueError(f"detection.rules[{i}].require cannot be empty")

        for j, signal in enumerate(require):
            if not isinstance(signal, str):
                raise ValueError(f"detection.rules[{i}].require[{j}] must be a string")
            if signal not in VALID_SIGNALS:
                raise ValueError(
                    f"detection.rules[{i}].require[{j}]: "
                    f"unknown signal '{signal}'. Valid: {VALID_SIGNALS}"
                )

        if name in seen_names:
            raise ValueError(f"detection.rules[{i}].name: duplicate name '{name}'")
        seen_names.add(name)

        if "detection_overrides" in rule:
            _validate_overrides(rule["detection_overrides"], i)


def _validate_overrides(overrides, rule_index: int) -> None:
    if not isinstance(overrides, dict):
        raise ValueError(f"detection.rules[{rule_index}].detection_overrides must be a dict")

    if "killfeed_roi" in overrides:
        roi = overrides["killfeed_roi"]
        if not isinstance(roi, list) or len(roi) != 4:
            raise ValueError(
                f"detection.rules[{rule_index}].detection_overrides.killfeed_roi "
                "must be a list of 4 numbers"
            )

    if "ocr" in overrides:
        ocr = overrides["ocr"]
        if not isinstance(ocr, dict):
            raise ValueError(f"detection.rules[{rule_index}].detection_overrides.ocr must be a dict")
        if "keywords" in ocr and not isinstance(ocr["keywords"], list):
            raise ValueError(f"detection.rules[{rule_index}].detection_overrides.ocr.keywords must be a list")
        if "similarity_threshold" in ocr and not isinstance(
            ocr["similarity_threshold"],
            (int, float),
        ):
            raise ValueError(
                f"detection.rules[{rule_index}].detection_overrides.ocr.similarity_threshold "
                "must be a number"
            )
        if "similarity_threshold" in ocr and not (0 <= ocr["similarity_threshold"] <= 1):
            raise ValueError(
                f"detection.rules[{rule_index}].detection_overrides.ocr.similarity_threshold must be 0-1"
            )

    if "templates" in overrides and not isinstance(overrides["templates"], dict):
        raise ValueError(f"detection.rules[{rule_index}].detection_overrides.templates must be a dict")

    if "colors" in overrides:
        colors = overrides["colors"]
        if not isinstance(colors, dict):
            raise ValueError(f"detection.rules[{rule_index}].detection_overrides.colors must be a dict")
        for color_name, color_data in colors.items():
            if not isinstance(color_data, dict):
                raise ValueError(
                    f"detection.rules[{rule_index}].detection_overrides.colors.{color_name} must be a dict"
                )
            if "hsv_lower" not in color_data or "hsv_upper" not in color_data:
                raise ValueError(
                    f"detection.rules[{rule_index}].detection_overrides.colors.{color_name} "
                    "must have hsv_lower and hsv_upper"
                )

