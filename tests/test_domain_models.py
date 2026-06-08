import pytest

from src.ai.events import DetectionEvent
from src.ai.kill_detector import KillDetector
from src.clip.metadata import ClipMetadata


def test_detection_event_round_trip():
    event = DetectionEvent.from_dict({
        "timestamp_ms": "1200",
        "confidence": "0.75",
        "type": "kill",
        "signals": {"ocr": 0.5},
        "meta": {"frame_path": "frame_1200.jpg"},
    })

    assert event.timestamp_ms == 1200
    assert event.confidence == 0.75
    assert event.to_dict()["signals"] == {"ocr": 0.5}
    assert event.to_dict()["meta"]["frame_path"] == "frame_1200.jpg"


def test_clip_metadata_accepts_legacy_output_path():
    clip = ClipMetadata.from_dict({
        "output_path": "clip.mp4",
        "start_ms": 100,
        "end_ms": 200,
        "kill_count": 2,
        "filename": "clip.mp4",
    })

    assert clip.path == "clip.mp4"
    assert clip.to_dict()["kill_count"] == 2


def test_clip_metadata_requires_path():
    with pytest.raises(RuntimeError, match="missing path field"):
        ClipMetadata.from_dict({"id": "clip-1"})


def test_kill_detector_event_builder_uses_detection_event_shape():
    event = KillDetector._build_detection_event(
        object(),
        timestamp_ms=1200,
        confidence=0.75,
        signals={"ocr": "0.5", "unknown": 0.8},
    )

    assert event == {
        "timestamp_ms": 1200,
        "confidence": 0.75,
        "type": "kill",
        "signals": {"ocr": 0.5, "template": 0.0, "color": 0.0, "yolo": 0.0},
    }
