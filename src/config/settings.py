from dataclasses import dataclass
import os
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class VideoSettings:
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    hwaccel: Optional[str] = "cuda"
    frame_extraction_mode: str = "bulk"
    frame_interval_ms: int = 1000

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "VideoSettings":
        video = config.get("video", {}) or {}
        return cls(
            ffmpeg_path=video.get("ffmpeg_path", "ffmpeg"),
            ffprobe_path=video.get("ffprobe_path", "ffprobe"),
            hwaccel=video.get("hwaccel", "cuda"),
            frame_extraction_mode=video.get("frame_extraction_mode", "bulk"),
            frame_interval_ms=int(video.get("frame_interval_ms", 1000)),
        )


@dataclass(frozen=True)
class AISettings:
    model_dir: str = "models"
    batch_size: int = 16
    allow_model_download: bool = False

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "AISettings":
        ai = config.get("ai", {}) or {}
        return cls(
            model_dir=ai.get("model_dir", "models"),
            batch_size=int(ai.get("batch_size", 16)),
            allow_model_download=bool(ai.get("allow_model_download", False)),
        )


@dataclass(frozen=True)
class DetectionSettings:
    model_path: str = ""
    chunk_size: int = 256

    @classmethod
    def from_config(cls, config: Dict[str, Any], ai_settings: AISettings) -> "DetectionSettings":
        detection = config.get("detection", {}) or {}
        return cls(
            model_path=detection.get("model_path") or os.path.join(ai_settings.model_dir, "yolov8n.pt"),
            chunk_size=int(detection.get("chunk_size", 256)),
        )


@dataclass(frozen=True)
class AppSettings:
    video: VideoSettings
    ai: AISettings
    detection: DetectionSettings

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "AppSettings":
        ai_settings = AISettings.from_config(config)
        return cls(
            video=VideoSettings.from_config(config),
            ai=ai_settings,
            detection=DetectionSettings.from_config(config, ai_settings),
        )
