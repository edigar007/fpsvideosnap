from src.config.detection_view import DEFAULT_SIGNAL_WEIGHTS, DETECTION_SIGNALS, DEFAULT_ROI, DetectionConfigView


def test_detection_config_view_normalizes_high_frequency_fields():
    view = DetectionConfigView.from_config(
        {
            "confidence_threshold": "0.7",
            "killfeed_roi": ["0.1", "0.2", "0.3", "0.4"],
            "weights": {"ocr": "0.1", "template": 0.2},
            "ocr": {
                "enabled": True,
                "required": True,
                "keywords": ["KILL", 123],
                "similarity_threshold": "0.9",
                "lang": "en",
                "use_gpu": False,
            },
            "templates": {"kill": {"threshold": "0.85", "roi": [0.2, 0.2, 0.5, 0.5]}},
            "colors": {"red": {"hsv_lower": [0, 0, 0], "hsv_upper": [10, 255, 255]}},
            "prefilter": {"enabled": False, "color_threshold": "0.02"},
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
    assert view.killfeed_roi == (0.1, 0.2, 0.3, 0.4)
    assert view.weights["ocr"] == 0.1
    assert view.weights["template"] == 0.2
    assert view.weights["color"] == DEFAULT_SIGNAL_WEIGHTS["color"]
    assert view.ocr.enabled is True
    assert view.ocr.required is True
    assert view.ocr.keywords == ("KILL", "123")
    assert view.ocr.similarity_threshold == 0.9
    assert view.ocr.lang == "en"
    assert view.ocr.use_gpu is False
    assert view.templates.names == ("kill",)
    assert view.templates.threshold_for("kill") == 0.85
    assert view.templates.roi_for("kill", [0, 0, 1, 1]) == [0.2, 0.2, 0.5, 0.5]
    assert view.colors.items[0][0] == "red"
    assert view.prefilter.enabled is False
    assert view.prefilter.color_threshold == 0.02
    assert view.signals == DETECTION_SIGNALS
    assert view.rules[0].require == ("ocr", "color")
    assert view.rule_dicts[0]["detection_overrides"]["killfeed_roi"] == [0, 0, 1, 1]
    assert [rule["name"] for rule in view.enabled_rule_dicts] == ["rule_a"]


def test_detection_config_view_ignores_non_dict_rules():
    view = DetectionConfigView.from_config({"rules": ["bad", {"name": "ok", "require": ["color"]}]})

    assert [rule.name for rule in view.rules] == ["ok"]


def test_detection_config_view_section_defaults_are_stable():
    view = DetectionConfigView.from_config(
        {
            "killfeed_roi": ["bad"],
            "weights": {"ocr": "bad"},
            "ocr": "bad",
            "templates": "bad",
            "colors": "bad",
            "prefilter": {"color_threshold": "bad"},
        }
    )

    assert view.killfeed_roi == DEFAULT_ROI
    assert view.weights["ocr"] == DEFAULT_SIGNAL_WEIGHTS["ocr"]
    assert view.ocr.enabled is False
    assert view.ocr.similarity_threshold == 0.8
    assert view.templates.names == ()
    assert view.colors.values == ()
    assert view.prefilter.enabled is True
    assert view.prefilter.color_threshold == 0.01
