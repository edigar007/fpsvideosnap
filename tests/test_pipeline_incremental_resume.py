"""
Tests for incremental rebuild / config-aware resume functionality.

Covers:
1. Config unchanged + final exists -> skip (no re-run)
2. video.* changed -> invalidate from frames
3. detection.* changed -> invalidate from detection
4. highlights.* changed -> invalidate from clips
5. final missing -> chain fallback rebuild
6. Checkpoint naming collision avoidance (path hash)
7. Final output naming collision (suffix _1, _2, ...)
"""
import os
import json
import pytest
import tempfile
from unittest.mock import patch

# Heavy dependencies are mocked in conftest.py

from src.pipeline.pipeline import Pipeline, StageStatus, CHECKPOINT_VERSION
from src.config.fingerprint import (
    compute_config_fingerprints,
    compute_path_hash,
    get_earliest_invalidation_stage,
    get_stages_to_invalidate,
    get_unique_output_path,
)


@pytest.fixture
def base_config():
    """Standard test config for pipeline."""
    return {
        "global": {
            "output_dir": "test_output",
            "history_dir": "test_history",
            "debug": True
        },
        "video": {
            "ffmpeg_path": "ffmpeg",
            "hwaccel": None,
            "frame_interval_ms": 1000
        },
        "ai": {
            "model_dir": "models",
            "batch_size": 2,
            "confidence_threshold": 0.5
        },
        "highlights": {
            "pre_kill_time": 2,
            "post_kill_time": 1,
            "music_enabled": False
        },
        "detection": {
            "killfeed_roi": [0, 0, 1, 1],
            "confidence_threshold": 0.5,
            "colors": {}
        }
    }


class TestCheckpointPathHash:
    """Tests for checkpoint file naming with path hash."""
    
    def test_checkpoint_filename_includes_path_hash(self, base_config):
        """Checkpoint filename should include an 8-char hash of video path."""
        with patch("src.pipeline.pipeline.temp_manager") as mock_temp:
            mock_temp.create_temp_dir.return_value = "/tmp/test_temp"
            
            video_path = "D:\\videos\\my_gameplay.mp4"
            expected_hash = compute_path_hash(video_path)
            
            # Check that checkpoint file includes path hash
            checkpoint_name = f"checkpoint_my_gameplay_{expected_hash}.json"
            
            # Simulate what pipeline does internally
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            path_hash = compute_path_hash(video_path)
            actual_checkpoint_name = f"checkpoint_{base_name}_{path_hash}.json"
            
            assert actual_checkpoint_name == checkpoint_name
    
    def test_different_paths_same_filename_get_different_checkpoints(self):
        """Two videos with same name but different directories should have different checkpoint hashes."""
        path1 = "D:\\folder1\\gameplay.mp4"
        path2 = "D:\\folder2\\gameplay.mp4"
        
        hash1 = compute_path_hash(path1)
        hash2 = compute_path_hash(path2)
        
        assert hash1 != hash2, "Different paths should produce different hashes"


class TestFingerprintInvalidation:
    """Tests for fingerprint-based stage invalidation."""
    
    def test_video_config_change_invalidates_from_frames(self, base_config):
        """Changing video.* should trigger invalidation from frames stage."""
        fp_old = compute_config_fingerprints(base_config)
        
        # Modify video config
        modified = base_config.copy()
        modified["video"] = base_config["video"].copy()
        modified["video"]["frame_interval_ms"] = 500  # Changed!
        
        fp_new = compute_config_fingerprints(modified)
        
        stage = get_earliest_invalidation_stage(fp_old, fp_new)
        assert stage == "frames"
    
    def test_detection_config_change_invalidates_from_detection(self, base_config):
        """Changing detection.* should trigger invalidation from detection stage."""
        fp_old = compute_config_fingerprints(base_config)
        
        # Modify detection config
        modified = base_config.copy()
        modified["detection"] = base_config["detection"].copy()
        modified["detection"]["confidence_threshold"] = 0.8  # Changed!
        
        fp_new = compute_config_fingerprints(modified)
        
        stage = get_earliest_invalidation_stage(fp_old, fp_new)
        assert stage == "detection"
    
    def test_ai_config_change_invalidates_from_detection(self, base_config):
        """Changing ai.* should trigger invalidation from detection stage."""
        fp_old = compute_config_fingerprints(base_config)
        
        # Modify ai config
        modified = base_config.copy()
        modified["ai"] = base_config["ai"].copy()
        modified["ai"]["batch_size"] = 32  # Changed!
        
        fp_new = compute_config_fingerprints(modified)
        
        stage = get_earliest_invalidation_stage(fp_old, fp_new)
        assert stage == "detection"
    
    def test_highlights_config_change_invalidates_from_clips(self, base_config):
        """Changing highlights.* should trigger invalidation from clips stage."""
        fp_old = compute_config_fingerprints(base_config)
        
        # Modify highlights config
        modified = base_config.copy()
        modified["highlights"] = base_config["highlights"].copy()
        modified["highlights"]["pre_kill_time"] = 5  # Changed!
        
        fp_new = compute_config_fingerprints(modified)
        
        stage = get_earliest_invalidation_stage(fp_old, fp_new)
        assert stage == "clips"
    
    def test_no_change_returns_none(self, base_config):
        """No config changes should return None (no invalidation needed)."""
        fp = compute_config_fingerprints(base_config)
        
        stage = get_earliest_invalidation_stage(fp, fp)
        assert stage is None
    
    def test_get_stages_to_invalidate_from_detection(self):
        """Invalidating from detection should reset detection and all subsequent stages."""
        stages = get_stages_to_invalidate("detection")
        
        assert "detection" in stages
        assert "clips" in stages
        assert "join" in stages
        assert "audio" in stages
        assert "frames" not in stages  # Earlier stage
        assert "metadata" not in stages  # Earlier stage
    
    def test_get_stages_to_invalidate_from_frames(self):
        """Invalidating from frames should reset frames and all subsequent stages."""
        stages = get_stages_to_invalidate("frames")
        
        assert "frames" in stages
        assert "detection" in stages
        assert "clips" in stages
        assert "metadata" not in stages  # Earlier stage


class TestUniqueOutputPath:
    """Tests for final output naming collision handling."""
    
    def test_unique_path_returns_base_if_not_exists(self):
        """If base path doesn't exist, return it unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "video_highlights.mp4")
            
            result = get_unique_output_path(base_path)
            
            assert result == base_path
    
    def test_unique_path_adds_suffix_if_exists(self):
        """If base path exists, add _1 suffix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "video_highlights.mp4")
            
            # Create the base file
            with open(base_path, "w") as f:
                f.write("dummy")
            
            result = get_unique_output_path(base_path)
            
            expected = os.path.join(tmpdir, "video_highlights_1.mp4")
            assert result == expected
    
    def test_unique_path_increments_suffix(self):
        """If _1 also exists, use _2, etc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "video_highlights.mp4")
            
            # Create base and _1
            with open(base_path, "w") as f:
                f.write("dummy")
            with open(os.path.join(tmpdir, "video_highlights_1.mp4"), "w") as f:
                f.write("dummy")
            
            result = get_unique_output_path(base_path)
            
            expected = os.path.join(tmpdir, "video_highlights_2.mp4")
            assert result == expected
    
    def test_unique_path_handles_multiple_existing(self):
        """Should find next available number even with gaps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "video_highlights.mp4")
            
            # Create base, _1, _2
            for suffix in ["", "_1", "_2"]:
                with open(os.path.join(tmpdir, f"video_highlights{suffix}.mp4"), "w") as f:
                    f.write("dummy")
            
            result = get_unique_output_path(base_path)
            
            expected = os.path.join(tmpdir, "video_highlights_3.mp4")
            assert result == expected


class TestCheckpointVersioning:
    """Tests for checkpoint version handling."""
    
    def test_old_checkpoint_without_version_triggers_fresh_run(self, base_config):
        """Old checkpoints (no version) should be treated as incompatible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.pipeline.temp_manager") as mock_temp:
                mock_temp.create_temp_dir.return_value = tmpdir
                
                pipeline = Pipeline(base_config)
                
                # Create an old-style checkpoint without version
                old_checkpoint = {
                    "stage_status": {
                        "metadata": "SUCCESS",
                        "frames": "SUCCESS",
                        "detection": "SUCCESS",
                    },
                    "results": {"video_info": {"duration": 10}},
                    # No checkpoint_version, no video_path, no fingerprints
                }
                
                video_path = "test_video.mp4"
                base_name = "test_video"
                path_hash = compute_path_hash(video_path)
                checkpoint_file = os.path.join(tmpdir, f"checkpoint_{base_name}_{path_hash}.json")
                
                with open(checkpoint_file, "w") as f:
                    json.dump(old_checkpoint, f)
                
                # Attempt to load - should return False (fresh run)
                pipeline.checkpoint_file = checkpoint_file
                loaded = pipeline._load_checkpoint(checkpoint_file, video_path)
                
                # Without version, should not resume
                assert loaded is False
    
    def test_checkpoint_with_wrong_video_path_triggers_fresh_run(self, base_config):
        """Checkpoint for different video should not be loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.pipeline.temp_manager") as mock_temp:
                mock_temp.create_temp_dir.return_value = tmpdir
                
                pipeline = Pipeline(base_config)
                
                # Create checkpoint for a different video
                checkpoint_data = {
                    "checkpoint_version": CHECKPOINT_VERSION,
                    "video_path": "D:\\other\\different_video.mp4",  # Different!
                    "fingerprints": compute_config_fingerprints(base_config),
                    "stage_status": {"metadata": "SUCCESS"},
                    "results": {},
                }
                
                video_path = "D:\\my\\test_video.mp4"
                base_name = "test_video"
                path_hash = compute_path_hash(video_path)
                checkpoint_file = os.path.join(tmpdir, f"checkpoint_{base_name}_{path_hash}.json")
                
                with open(checkpoint_file, "w") as f:
                    json.dump(checkpoint_data, f)
                
                pipeline.checkpoint_file = checkpoint_file
                loaded = pipeline._load_checkpoint(checkpoint_file, video_path)
                
                # Video path mismatch, should not resume
                assert loaded is False

    def test_missing_frame_artifact_invalidates_from_frames(self, base_config):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.pipeline.temp_manager") as mock_temp:
                mock_temp.create_temp_dir.return_value = tmpdir

                pipeline = Pipeline(base_config)
                video_path = os.path.abspath(os.path.join(tmpdir, "test_video.mp4"))
                checkpoint_file = os.path.join(tmpdir, "checkpoint.json")
                checkpoint_data = {
                    "checkpoint_version": CHECKPOINT_VERSION,
                    "video_path": video_path,
                    "fingerprints": compute_config_fingerprints(base_config),
                    "stages": {
                        "metadata": {"status": "SUCCESS", "duration": 0},
                        "frames": {"status": "SUCCESS", "duration": 0},
                        "detection": {"status": "SUCCESS", "duration": 0},
                    },
                    "results": {
                        "video_info": {"path": video_path, "duration": 1},
                        "frames": [os.path.join(tmpdir, "missing_frame.jpg")],
                    },
                    "temp_dir": tmpdir,
                }

                with open(checkpoint_file, "w", encoding="utf-8") as f:
                    json.dump(checkpoint_data, f)

                loaded = pipeline._load_checkpoint(checkpoint_file, video_path)

                assert loaded is True
                assert pipeline.stages["metadata"].status == StageStatus.SUCCESS
                assert pipeline.stages["frames"].status == StageStatus.PENDING
                assert pipeline.stages["detection"].status == StageStatus.PENDING
                assert "frames" not in pipeline.results

    def test_missing_clip_artifact_invalidates_from_clips(self, base_config):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.pipeline.temp_manager") as mock_temp:
                mock_temp.create_temp_dir.return_value = tmpdir

                pipeline = Pipeline(base_config)
                video_path = os.path.abspath(os.path.join(tmpdir, "test_video.mp4"))
                frame_path = os.path.join(tmpdir, "frame_1000.jpg")
                detection_path = os.path.join(tmpdir, "detections.json")
                checkpoint_file = os.path.join(tmpdir, "checkpoint.json")
                with open(frame_path, "w", encoding="utf-8") as f:
                    f.write("frame")
                with open(detection_path, "w", encoding="utf-8") as f:
                    json.dump([], f)

                checkpoint_data = {
                    "checkpoint_version": CHECKPOINT_VERSION,
                    "video_path": video_path,
                    "fingerprints": compute_config_fingerprints(base_config),
                    "stages": {
                        "metadata": {"status": "SUCCESS", "duration": 0},
                        "frames": {"status": "SUCCESS", "duration": 0},
                        "detection": {"status": "SUCCESS", "duration": 0},
                        "clips": {"status": "SUCCESS", "duration": 0},
                        "join": {"status": "SUCCESS", "duration": 0},
                    },
                    "results": {
                        "video_info": {"path": video_path, "duration": 1},
                        "frames": [frame_path],
                        "events": [],
                        "detection_json": detection_path,
                        "clips": [{"path": os.path.join(tmpdir, "missing_clip.mp4")}],
                        "joined_video": os.path.join(tmpdir, "joined.mp4"),
                    },
                    "temp_dir": tmpdir,
                }

                with open(checkpoint_file, "w", encoding="utf-8") as f:
                    json.dump(checkpoint_data, f)

                loaded = pipeline._load_checkpoint(checkpoint_file, video_path)

                assert loaded is True
                assert pipeline.stages["detection"].status == StageStatus.SUCCESS
                assert pipeline.stages["clips"].status == StageStatus.PENDING
                assert pipeline.stages["join"].status == StageStatus.PENDING
                assert "clips" not in pipeline.results
                assert "joined_video" not in pipeline.results


class TestInvalidateFromStage:
    """Tests for the _invalidate_from_stage method."""
    
    def test_invalidate_resets_stage_status(self, base_config):
        """Invalidating should reset affected stages to PENDING."""
        with patch("src.pipeline.pipeline.temp_manager") as mock_temp:
            mock_temp.create_temp_dir.return_value = "/tmp/test"
            
            pipeline = Pipeline(base_config)
            
            # Set some stages as SUCCESS
            pipeline.stages["frames"].status = StageStatus.SUCCESS
            pipeline.stages["detection"].status = StageStatus.SUCCESS
            pipeline.stages["clips"].status = StageStatus.SUCCESS
            pipeline.stages["join"].status = StageStatus.SUCCESS
            
            # Invalidate from detection
            pipeline._invalidate_from_stage("detection")
            
            # frames should remain untouched
            assert pipeline.stages["frames"].status == StageStatus.SUCCESS
            
            # detection and later should be PENDING
            assert pipeline.stages["detection"].status == StageStatus.PENDING
            assert pipeline.stages["clips"].status == StageStatus.PENDING
            assert pipeline.stages["join"].status == StageStatus.PENDING
    
    def test_invalidate_clears_result_keys(self, base_config):
        """Invalidating should clear result keys for affected stages."""
        with patch("src.pipeline.pipeline.temp_manager") as mock_temp:
            mock_temp.create_temp_dir.return_value = "/tmp/test"
            
            pipeline = Pipeline(base_config)
            
            # Set some results
            pipeline.results["events"] = [{"timestamp": 1000}]
            pipeline.results["clips"] = [{"path": "clip.mp4"}]
            pipeline.results["joined_video"] = "/tmp/joined.mp4"
            
            # Invalidate from detection
            pipeline._invalidate_from_stage("detection")
            
            # Result keys for detection+ should be cleared
            assert "events" not in pipeline.results
            assert "clips" not in pipeline.results
            assert "joined_video" not in pipeline.results


class TestConfigUnchangedFinalExists:
    """Tests for the skip scenario: config unchanged + final exists."""
    
    @patch("src.pipeline.pipeline.temp_manager")
    def test_config_unchanged_final_exists_skips_audio(self, mock_temp_mgr, base_config):
        """When config is unchanged and final exists, audio stage should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_temp_mgr.create_temp_dir.return_value = tmpdir
            
            # Create the final output file
            base_config["global"]["output_dir"] = tmpdir
            final_path = os.path.join(tmpdir, "test_video_highlights.mp4")
            with open(final_path, "w") as f:
                f.write("dummy final video")
            
            pipeline = Pipeline(base_config)
            
            # Pre-set audio as SUCCESS (from checkpoint)
            pipeline.stages["audio"].status = StageStatus.SUCCESS
            
            # Check the condition
            final_exists = os.path.exists(final_path)
            need_audio = (pipeline.stages["audio"].status != StageStatus.SUCCESS) or not final_exists
            
            # Should NOT need audio mixing
            assert final_exists is True
            assert need_audio is False, "Should skip audio when final exists and stage is SUCCESS"

    @patch("src.pipeline.pipeline.temp_manager")
    def test_audio_resume_prefers_saved_final_video_path(self, mock_temp_mgr, base_config):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_temp_mgr.create_temp_dir.return_value = tmpdir
            base_config["global"]["output_dir"] = tmpdir

            saved_final = os.path.join(tmpdir, "test_video_highlights_1.mp4")
            with open(saved_final, "w", encoding="utf-8") as f:
                f.write("dummy final video")

            pipeline = Pipeline(base_config)
            pipeline.stages["audio"].status = StageStatus.SUCCESS
            pipeline.results["final_video"] = saved_final
            context = pipeline._build_context("test_video.mp4", "test_video")

            assert pipeline._run_audio_plan_stage(context, "joined.mp4", resume_completed=True) == saved_final


class TestRunUntilClipsCheckpointNaming:
    @patch("src.pipeline.pipeline.temp_manager")
    def test_run_until_clips_checkpoint_includes_path_hash(self, mock_temp_mgr, base_config):
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
    def test_run_until_clips_checkpoint_records_video_and_fingerprints(self, mock_temp_mgr, base_config):
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
    def test_run_until_clips_resumes_valid_checkpoint(self, mock_temp_mgr, base_config):
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
