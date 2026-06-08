import pytest

from src.tools.config_assistant.services.rule_validation import validate_rules


def test_validate_rules_accepts_valid_rule_with_overrides():
    validate_rules(
        [
            {
                "name": "headshot",
                "enabled": True,
                "require": ["ocr", "color"],
                "detection_overrides": {
                    "killfeed_roi": [0.1, 0.2, 0.3, 0.4],
                    "ocr": {"keywords": ["HEADSHOT"], "similarity_threshold": 0.9},
                    "templates": {"skull": {"path": "skull.png"}},
                    "colors": {
                        "red": {
                            "hsv_lower": [0, 100, 100],
                            "hsv_upper": [10, 255, 255],
                        }
                    },
                },
            }
        ]
    )


def test_validate_rules_rejects_invalid_signal():
    with pytest.raises(ValueError, match="unknown signal"):
        validate_rules([{"name": "bad", "enabled": True, "require": ["bad_signal"]}])


def test_validate_rules_rejects_bad_color_override():
    with pytest.raises(ValueError, match="must have hsv_lower and hsv_upper"):
        validate_rules(
            [
                {
                    "name": "bad_color",
                    "enabled": True,
                    "require": ["color"],
                    "detection_overrides": {"colors": {"red": {"hsv_lower": [0, 0, 0]}}},
                }
            ]
        )

