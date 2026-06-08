from src.config.detection_view import DEFAULT_SIGNAL_WEIGHTS, DETECTION_SIGNALS, DetectionConfigView


def test_detection_config_view_normalizes_high_frequency_fields():
    view = DetectionConfigView.from_config(
        {
            "confidence_threshold": "0.7",
            "weights": {"ocr": "0.1", "template": 0.2},
            "rules": [
                {
                    "name": "rule_a",
                    "enabled": True,
                    "require": ["ocr", "color"],
                    "detection_overrides": {"killfeed_roi": [0, 0, 1, 1]},
                },
                {"name": "rule_b", "enabled": False, "require": ["yolo"]},
            ],
        }
    )

    assert view.confidence_threshold == 0.7
    assert view.weights["ocr"] == 0.1
    assert view.weights["template"] == 0.2
    assert view.weights["color"] == DEFAULT_SIGNAL_WEIGHTS["color"]
    assert view.signals == DETECTION_SIGNALS
    assert view.rules[0].require == ("ocr", "color")
    assert view.rule_dicts[0]["detection_overrides"]["killfeed_roi"] == [0, 0, 1, 1]
    assert [rule["name"] for rule in view.enabled_rule_dicts] == ["rule_a"]


def test_detection_config_view_ignores_non_dict_rules():
    view = DetectionConfigView.from_config({"rules": ["bad", {"name": "ok", "require": ["color"]}]})

    assert [rule.name for rule in view.rules] == ["ok"]
