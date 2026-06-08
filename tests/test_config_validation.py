import pytest

from src.config.config_loader import ConfigLoader


@pytest.fixture
def loader() -> ConfigLoader:
    return ConfigLoader(config_dir="config")


@pytest.fixture
def valid_config() -> dict:
    return {
        "video": {"frame_extraction_mode": "bulk"},
        "detection": {
            "killfeed_roi": [0.1, 0.2, 0.3, 0.4],
            "ocr": {"enabled": False, "keywords": [], "similarity_threshold": 0.8},
            "colors": {
                "red": {
                    "hsv_lower": [0, 10, 20],
                    "hsv_upper": [180, 255, 255],
                }
            },
            "weights": {"ocr": 0.0, "template": 0.5, "color": 0.5, "yolo": 0.0},
            "prefilter": {"enabled": True, "color_threshold": 0.01},
        },
        "highlights": {
            "pre_kill_time": 5.0,
            "post_kill_time": 2.0,
            "game_volume": 0.5,
            "music_volume": 0.5,
        },
    }


def test_valid_config_passes(loader: ConfigLoader, valid_config: dict) -> None:
    loader._validate_config(valid_config)


@pytest.mark.parametrize(
    ("field_value", "message"),
    [
        ([0, 0, 1], "detection.killfeed_roi must be a list of 4 numbers"),
        ([0, 0, 0, 1], "width and height must be greater than 0"),
        ([0, 0, 1.2, 1], "values must be between 0.0 and 1.0"),
    ],
)
def test_roi_validation(loader: ConfigLoader, valid_config: dict, field_value: list, message: str) -> None:
    valid_config["detection"]["killfeed_roi"] = field_value
    with pytest.raises(ValueError, match=message):
        loader._validate_config(valid_config)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("hsv_lower", [0, 0], "must be a list of 3 numbers"),
        ("hsv_lower", [181, 0, 0], "hue must be between 0 and 180"),
        ("hsv_upper", [180, 256, 0], "saturation must be between 0 and 255"),
        ("hsv_upper", [180, 255, 256], "value must be between 0 and 255"),
    ],
)
def test_hsv_validation(loader: ConfigLoader, valid_config: dict, field: str, value: list, message: str) -> None:
    valid_config["detection"]["colors"]["red"][field] = value
    with pytest.raises(ValueError, match=message):
        loader._validate_config(valid_config)


def test_highlight_times_must_be_non_negative(loader: ConfigLoader, valid_config: dict) -> None:
    valid_config["highlights"]["pre_kill_time"] = -1
    with pytest.raises(ValueError, match="highlights.pre_kill_time"):
        loader._validate_config(valid_config)


def test_highlight_volumes_must_be_0_to_1(loader: ConfigLoader, valid_config: dict) -> None:
    valid_config["highlights"]["music_volume"] = 1.5
    with pytest.raises(ValueError, match="highlights.music_volume"):
        loader._validate_config(valid_config)


def test_frame_extraction_mode_is_limited(loader: ConfigLoader, valid_config: dict) -> None:
    valid_config["video"]["frame_extraction_mode"] = "fast"
    with pytest.raises(ValueError, match="video.frame_extraction_mode"):
        loader._validate_config(valid_config)


def test_weights_must_have_positive_value(loader: ConfigLoader, valid_config: dict) -> None:
    valid_config["detection"]["weights"] = {"ocr": 0.0, "template": 0.0}
    with pytest.raises(ValueError, match="at least one positive"):
        loader._validate_config(valid_config)
