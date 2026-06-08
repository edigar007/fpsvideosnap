from src.ai.signal_evaluator import signals_to_booleans


def test_signals_to_booleans_uses_cached_color_threshold():
    result = signals_to_booleans(
        {"ocr": 0.0, "template": 0.0, "color": 1.0, "yolo": 0.0},
        {"prefilter": {"color_threshold": 0.2}},
        cached_color_pct=0.1,
    )

    assert result["color"] is False


def test_signals_to_booleans_uses_template_thresholds():
    result = signals_to_booleans(
        {"template": 0.75},
        {"templates": {"kill": {"threshold": 0.7}}},
    )

    assert result["template"] is True


def test_signals_to_booleans_handles_unloaded_templates():
    result = signals_to_booleans(
        {"template": 0.95},
        {"templates": {"kill": {"threshold": 0.7}}},
        templates_loaded=False,
    )

    assert result["template"] is False
