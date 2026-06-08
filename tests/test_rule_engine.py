from src.ai.rule_engine import DetectionRuleEngine


def test_rule_engine_merges_nested_overrides():
    engine = DetectionRuleEngine(
        {
            "ocr": {"enabled": True, "keywords": ["global"], "similarity_threshold": 0.8},
            "colors": {"red": {"hsv_lower": [0, 0, 0]}},
        },
        templates_loaded=lambda: False,
    )
    rule = {
        "name": "override_ocr",
        "detection_overrides": {"ocr": {"keywords": ["override"]}},
    }

    merged = engine.merge_detection_config(rule)

    assert merged["ocr"] == {
        "enabled": True,
        "keywords": ["override"],
        "similarity_threshold": 0.8,
    }
    assert merged["colors"] == {"red": {"hsv_lower": [0, 0, 0]}}


def test_rule_engine_reuses_existing_signals_for_non_affecting_overrides():
    engine = DetectionRuleEngine(
        {
            "rules": [
                {
                    "name": "reusable",
                    "enabled": True,
                    "require": ["color"],
                    "detection_overrides": {"note": "does not affect signals"},
                }
            ],
            "prefilter": {"color_threshold": 0.5},
        },
        templates_loaded=lambda: False,
    )

    def compute_signals(*args, **kwargs):
        raise AssertionError("non-affecting overrides should not recompute signals")

    assert engine.evaluate(
        frame=object(),
        signals={"color": 1.0},
        compute_signals=compute_signals,
        cached_color_pct=1.0,
    ) is True


def test_rule_engine_recomputes_signals_for_signal_affecting_overrides():
    engine = DetectionRuleEngine(
        {
            "rules": [
                {
                    "name": "override_roi",
                    "enabled": True,
                    "require": ["color"],
                    "detection_overrides": {"killfeed_roi": [0.5, 0.5, 0.5, 0.5]},
                }
            ],
            "prefilter": {"color_threshold": 0.5},
        },
        templates_loaded=lambda: False,
    )
    calls = []

    def compute_signals(frame, detection_cfg, cached_color_pct, yolo_conf):
        calls.append((frame, detection_cfg, cached_color_pct, yolo_conf))
        return {"color": 1.0}

    assert engine.evaluate(
        frame="frame",
        signals={"color": 0.0},
        compute_signals=compute_signals,
        cached_color_pct=1.0,
        yolo_conf=0.7,
    ) is True
    assert calls[0][1]["killfeed_roi"] == [0.5, 0.5, 0.5, 0.5]
    assert calls[0][2] == 1.0
    assert calls[0][3] == 0.7


def test_rule_engine_returns_none_when_rules_missing():
    engine = DetectionRuleEngine({}, templates_loaded=lambda: False)

    assert engine.evaluate(object(), {}, compute_signals=lambda *args: {}) is None
