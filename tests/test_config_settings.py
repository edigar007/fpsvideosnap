import os

from src.config.settings import AISettings, AppSettings, DetectionSettings, VideoSettings


def test_app_settings_collects_main_runtime_defaults():
    settings = AppSettings.from_config({})

    assert settings.video == VideoSettings()
    assert settings.ai == AISettings()
    assert settings.detection == DetectionSettings(model_path=os.path.join("models", "yolov8n.pt"))


def test_app_settings_reads_runtime_config_values():
    config = {
        "video": {
            "ffmpeg_path": "custom_ffmpeg",
            "ffprobe_path": "custom_ffprobe",
            "hwaccel": None,
            "frame_extraction_mode": "precise",
            "frame_interval_ms": 250,
        },
        "ai": {
            "model_dir": "custom_models",
            "batch_size": 4,
            "allow_model_download": True,
        },
        "detection": {
            "model_path": "custom/model.pt",
            "chunk_size": 32,
        },
    }

    settings = AppSettings.from_config(config)

    assert settings.video.ffmpeg_path == "custom_ffmpeg"
    assert settings.video.ffprobe_path == "custom_ffprobe"
    assert settings.video.hwaccel is None
    assert settings.video.frame_extraction_mode == "precise"
    assert settings.video.frame_interval_ms == 250
    assert settings.ai.model_dir == "custom_models"
    assert settings.ai.batch_size == 4
    assert settings.ai.allow_model_download is True
    assert settings.detection.model_path == "custom/model.pt"
    assert settings.detection.chunk_size == 32


def test_detection_settings_model_path_falls_back_to_ai_model_dir():
    settings = AppSettings.from_config({"ai": {"model_dir": "weights"}, "detection": {}})

    assert settings.detection.model_path == os.path.join("weights", "yolov8n.pt")
