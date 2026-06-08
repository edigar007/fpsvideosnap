import json
from types import SimpleNamespace

from src.pipeline.checkpoint import ArtifactValidator, CheckpointData, CheckpointStore


def test_checkpoint_store_save_and_load_round_trip(tmp_path):
    checkpoint_path = tmp_path / "checkpoint.json"
    store = CheckpointStore(checkpoint_version=2)
    stages = {
        "metadata": SimpleNamespace(status=SimpleNamespace(value="SUCCESS"), duration=0.1),
        "frames": SimpleNamespace(status=SimpleNamespace(value="PENDING"), duration=0.0),
    }
    results = {"video_info": {"path": "video.mp4"}}
    fingerprints = {"config_hash": "abc"}

    store.save(
        str(checkpoint_path),
        video_path="video.mp4",
        fingerprints=fingerprints,
        stages=stages,
        results=results,
        temp_dir="temp/run",
    )

    loaded = store.load(str(checkpoint_path), current_video_path="video.mp4")

    assert loaded is not None
    assert loaded.stages["metadata"]["status"] == "SUCCESS"
    assert loaded.results == results
    assert loaded.temp_dir == "temp/run"
    assert loaded.fingerprints == fingerprints


def test_checkpoint_store_rejects_old_version(tmp_path):
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(
        json.dumps({"checkpoint_version": 1, "video_path": "video.mp4"}),
        encoding="utf-8",
    )

    assert CheckpointStore(checkpoint_version=2).load(str(checkpoint_path), "video.mp4") is None


def test_checkpoint_store_rejects_wrong_video_path(tmp_path):
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(
        json.dumps({"checkpoint_version": 2, "video_path": "other.mp4"}),
        encoding="utf-8",
    )

    assert CheckpointStore(checkpoint_version=2).load(str(checkpoint_path), "video.mp4") is None


def test_artifact_validator_finds_missing_clip_stage(tmp_path):
    frame_path = tmp_path / "frame_1000.jpg"
    detection_path = tmp_path / "detections.json"
    frame_path.write_text("frame", encoding="utf-8")
    detection_path.write_text("[]", encoding="utf-8")

    checkpoint = CheckpointData(
        stages={
            "metadata": {"status": "SUCCESS", "duration": 0},
            "frames": {"status": "SUCCESS", "duration": 0},
            "detection": {"status": "SUCCESS", "duration": 0},
            "clips": {"status": "SUCCESS", "duration": 0},
        },
        results={
            "frames": [str(frame_path)],
            "events": [],
            "detection_json": str(detection_path),
            "clips": [{"path": str(tmp_path / "missing.mp4")}],
        },
    )

    assert ArtifactValidator().get_invalid_stage(checkpoint) == "clips"

