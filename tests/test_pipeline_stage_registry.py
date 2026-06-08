from src.pipeline.results import CLIPS, EVENTS, FRAMES, JOINED_VIDEO
from src.pipeline.stage_registry import ArtifactStore, StageRegistry


def test_stage_registry_exposes_stage_order():
    registry = StageRegistry()

    assert registry.stage_names[:3] == ["metadata", "frames", "detection"]
    assert registry.stage_names[-1] == "cleanup"


def test_stage_registry_result_keys_to_clear():
    registry = StageRegistry()

    result = registry.result_keys_to_clear(["frames", "detection", "clips", "join"])

    assert result == [FRAMES, EVENTS, "detection_json", CLIPS, JOINED_VIDEO]


def test_artifact_store_removes_stage_artifacts(tmp_path):
    frames_dir = tmp_path / "frames"
    clips_dir = tmp_path / "clips"
    joined_video = tmp_path / "joined_no_audio.mp4"
    frames_dir.mkdir()
    clips_dir.mkdir()
    joined_video.write_bytes(b"joined")

    store = ArtifactStore(str(tmp_path))
    store.remove_stage_artifacts(["frames", "clips", "join"])

    assert not frames_dir.exists()
    assert not clips_dir.exists()
    assert not joined_video.exists()


def test_artifact_store_ignores_non_artifact_stages(tmp_path):
    metadata_file = tmp_path / "metadata.txt"
    metadata_file.write_text("keep", encoding="utf-8")

    ArtifactStore(str(tmp_path)).remove_stage_artifacts(["metadata", "report"])

    assert metadata_file.exists()

