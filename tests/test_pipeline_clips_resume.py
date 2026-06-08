import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.config.fingerprint import compute_config_fingerprints, compute_path_hash
from src.pipeline.pipeline import CHECKPOINT_VERSION, Pipeline, StageStatus


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


@patch("src.pipeline.pipeline.temp_manager")
def test_run_until_clips_checkpoint_includes_path_hash(mock_temp_mgr, base_config):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_temp_mgr.create_temp_dir.return_value = tmpdir
        base_config["global"]["temp_dir"] = tmpdir
        video_path = os.path.abspath(os.path.join(tmpdir, "same_name.mp4"))
        expected_hash = compute_path_hash(video_path)

        pipeline = Pipeline(base_config)

        with patch.object(pipeline, "_run_plan", return_value=[]):
            clips = pipeline.run_until_clips(video_path)

        assert clips == []
        assert os.path.basename(pipeline.checkpoint_file) == f"checkpoint_same_name_{expected_hash}.json"


@patch("src.pipeline.pipeline.temp_manager")
def test_run_until_clips_checkpoint_records_video_and_fingerprints(mock_temp_mgr, base_config):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_temp_mgr.create_temp_dir.return_value = tmpdir
        base_config["global"]["temp_dir"] = tmpdir
        video_path = os.path.abspath(os.path.join(tmpdir, "same_name.mp4"))

        pipeline = Pipeline(base_config)

        def fake_run_plan(*args, **kwargs):
            pipeline.stages["metadata"].status = StageStatus.SUCCESS
            pipeline.results["clips"] = []
            pipeline._save_checkpoint()
            return []

        with patch.object(pipeline, "_run_plan", side_effect=fake_run_plan):
            result = pipeline.run_until_clips_result(video_path)

        with open(pipeline.checkpoint_file, encoding="utf-8") as f:
            checkpoint = json.load(f)

        assert result.success is True
        assert checkpoint["video_path"] == video_path
        assert checkpoint["fingerprints"] == compute_config_fingerprints(base_config)
        assert checkpoint["temp_dir"] == tmpdir


@patch("src.pipeline.pipeline.temp_manager")
def test_run_until_clips_resumes_valid_checkpoint(mock_temp_mgr, base_config):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_temp_mgr.create_temp_dir.return_value = tmpdir
        base_config["global"]["temp_dir"] = tmpdir

        video_path = os.path.abspath(os.path.join(tmpdir, "same_name.mp4"))
        frame_path = os.path.join(tmpdir, "frame_1000.jpg")
        detection_path = os.path.join(tmpdir, "detections.json")
        clip_path = os.path.join(tmpdir, "clip.mp4")
        for path, contents in [
            (frame_path, "frame"),
            (detection_path, "[]"),
            (clip_path, "clip"),
        ]:
            with open(path, "w", encoding="utf-8") as f:
                f.write(contents)

        path_hash = compute_path_hash(video_path)
        checkpoint_file = os.path.join(tmpdir, f"checkpoint_same_name_{path_hash}.json")
        checkpoint_data = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "video_path": video_path,
            "fingerprints": compute_config_fingerprints(base_config),
            "stages": {
                "metadata": {"status": "SUCCESS", "duration": 0},
                "frames": {"status": "SUCCESS", "duration": 0},
                "detection": {"status": "SUCCESS", "duration": 0},
                "clips": {"status": "SUCCESS", "duration": 0},
            },
            "results": {
                "video_info": {"path": video_path, "duration": 1},
                "frames": [frame_path],
                "events": [],
                "detection_json": detection_path,
                "clips": [{"path": clip_path}],
            },
            "temp_dir": tmpdir,
        }
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f)

        pipeline = Pipeline(base_config)

        with patch("src.pipeline.pipeline.FrameExtractor") as mock_frame_extractor, \
             patch("src.pipeline.pipeline.run_detection_stage") as mock_detection_stage, \
             patch("src.pipeline.pipeline.ClipExtractor") as mock_clip_extractor:
            result = pipeline.run_until_clips_result(video_path)

        assert result.success is True
        assert result.clips == [{"path": clip_path}]
        mock_frame_extractor.assert_not_called()
        mock_detection_stage.assert_not_called()
        mock_clip_extractor.assert_not_called()
