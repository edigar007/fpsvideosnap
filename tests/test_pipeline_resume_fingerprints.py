import os
import tempfile

import pytest

from src.config.fingerprint import (
    compute_config_fingerprints,
    compute_path_hash,
    get_earliest_invalidation_stage,
    get_stages_to_invalidate,
    get_unique_output_path,
)


@pytest.fixture
def base_config():
    return {
        "global": {
            "output_dir": "test_output",
            "history_dir": "test_history",
            "debug": True,
        },
        "video": {
            "ffmpeg_path": "ffmpeg",
            "hwaccel": None,
            "frame_interval_ms": 1000,
        },
        "ai": {
            "model_dir": "models",
            "batch_size": 2,
            "confidence_threshold": 0.5,
        },
        "highlights": {
            "pre_kill_time": 2,
            "post_kill_time": 1,
            "music_enabled": False,
        },
        "detection": {
            "killfeed_roi": [0, 0, 1, 1],
            "confidence_threshold": 0.5,
            "colors": {},
        },
    }


def test_checkpoint_filename_includes_path_hash():
    video_path = "D:\\videos\\my_gameplay.mp4"
    expected_hash = compute_path_hash(video_path)

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    path_hash = compute_path_hash(video_path)
    actual_checkpoint_name = f"checkpoint_{base_name}_{path_hash}.json"

    assert actual_checkpoint_name == f"checkpoint_my_gameplay_{expected_hash}.json"


def test_different_paths_same_filename_get_different_checkpoints():
    path1 = "D:\\folder1\\gameplay.mp4"
    path2 = "D:\\folder2\\gameplay.mp4"

    hash1 = compute_path_hash(path1)
    hash2 = compute_path_hash(path2)

    assert hash1 != hash2


def test_video_config_change_invalidates_from_frames(base_config):
    fp_old = compute_config_fingerprints(base_config)
    modified = base_config.copy()
    modified["video"] = base_config["video"].copy()
    modified["video"]["frame_interval_ms"] = 500

    fp_new = compute_config_fingerprints(modified)

    assert get_earliest_invalidation_stage(fp_old, fp_new) == "frames"


def test_detection_config_change_invalidates_from_detection(base_config):
    fp_old = compute_config_fingerprints(base_config)
    modified = base_config.copy()
    modified["detection"] = base_config["detection"].copy()
    modified["detection"]["confidence_threshold"] = 0.8

    fp_new = compute_config_fingerprints(modified)

    assert get_earliest_invalidation_stage(fp_old, fp_new) == "detection"


def test_ai_config_change_invalidates_from_detection(base_config):
    fp_old = compute_config_fingerprints(base_config)
    modified = base_config.copy()
    modified["ai"] = base_config["ai"].copy()
    modified["ai"]["batch_size"] = 32

    fp_new = compute_config_fingerprints(modified)

    assert get_earliest_invalidation_stage(fp_old, fp_new) == "detection"


def test_highlights_config_change_invalidates_from_clips(base_config):
    fp_old = compute_config_fingerprints(base_config)
    modified = base_config.copy()
    modified["highlights"] = base_config["highlights"].copy()
    modified["highlights"]["pre_kill_time"] = 5

    fp_new = compute_config_fingerprints(modified)

    assert get_earliest_invalidation_stage(fp_old, fp_new) == "clips"


def test_no_change_returns_none(base_config):
    fingerprints = compute_config_fingerprints(base_config)

    assert get_earliest_invalidation_stage(fingerprints, fingerprints) is None


def test_get_stages_to_invalidate_from_detection():
    stages = get_stages_to_invalidate("detection")

    assert "detection" in stages
    assert "clips" in stages
    assert "join" in stages
    assert "audio" in stages
    assert "frames" not in stages
    assert "metadata" not in stages


def test_get_stages_to_invalidate_from_frames():
    stages = get_stages_to_invalidate("frames")

    assert "frames" in stages
    assert "detection" in stages
    assert "clips" in stages
    assert "metadata" not in stages


def test_unique_path_returns_base_if_not_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = os.path.join(tmpdir, "video_highlights.mp4")

        assert get_unique_output_path(base_path) == base_path


def test_unique_path_adds_suffix_if_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = os.path.join(tmpdir, "video_highlights.mp4")
        with open(base_path, "w", encoding="utf-8") as f:
            f.write("dummy")

        result = get_unique_output_path(base_path)

        assert result == os.path.join(tmpdir, "video_highlights_1.mp4")


def test_unique_path_increments_suffix():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = os.path.join(tmpdir, "video_highlights.mp4")
        with open(base_path, "w", encoding="utf-8") as f:
            f.write("dummy")
        with open(os.path.join(tmpdir, "video_highlights_1.mp4"), "w", encoding="utf-8") as f:
            f.write("dummy")

        result = get_unique_output_path(base_path)

        assert result == os.path.join(tmpdir, "video_highlights_2.mp4")


def test_unique_path_handles_multiple_existing():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = os.path.join(tmpdir, "video_highlights.mp4")
        for suffix in ["", "_1", "_2"]:
            with open(os.path.join(tmpdir, f"video_highlights{suffix}.mp4"), "w", encoding="utf-8") as f:
                f.write("dummy")

        result = get_unique_output_path(base_path)

        assert result == os.path.join(tmpdir, "video_highlights_3.mp4")
