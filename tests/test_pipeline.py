import pytest
import os
from unittest.mock import MagicMock, patch
from src.pipeline.pipeline import Pipeline, StageStatus

@pytest.fixture
def mock_config():
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
            "colors": {}
        }
    }

@patch("src.pipeline.pipeline.VideoInfo")
@patch("src.pipeline.pipeline.FrameExtractor")
@patch("src.pipeline.pipeline.ModelManager")
@patch("src.pipeline.pipeline.YoloDetector")
@patch("src.pipeline.pipeline.OpenCVMatcher")
@patch("src.pipeline.pipeline.KillDetector")
@patch("src.pipeline.pipeline.ClipExtractor")
@patch("src.pipeline.pipeline.VideoJoiner")
@patch("src.pipeline.pipeline.AudioMixer")
@patch("src.pipeline.pipeline.ReportGenerator")
@patch("src.pipeline.pipeline.HistoryManager")
@patch("src.pipeline.pipeline.temp_manager")
@patch("cv2.imread")
@patch("src.pipeline.pipeline.create_progress_bar")
def test_pipeline_full_flow(
    mock_pbar,
    mock_imread,
    mock_temp_mgr,
    mock_history,
    mock_report,
    mock_mixer,
    mock_joiner,
    mock_clip_ext,
    mock_kill_det,
    mock_cv_matcher,
    mock_yolo_det,
    mock_model_mgr,
    mock_frame_ext,
    mock_video_info,
    mock_config
):
    # Setup mocks
    mock_video_info.return_value.duration = 10
    mock_video_info.return_value.width = 1920
    mock_video_info.return_value.height = 1080
    mock_video_info.return_value.fps = 60
    
    mock_frame_ext.return_value.extract_frames.return_value = ["frame_1000.jpg", "frame_2000.jpg"]
    mock_imread.return_value = MagicMock()
    
    mock_kill_det.return_value.process_video_batch.return_value = [
        {"timestamp_ms": 1000, "confidence": 0.9, "type": "kill"}
    ]
    
    # TASK-003: Ensure clips have required metadata fields
    expected_clips = [{
        "path": "clip1.mp4",
        "start": 0,
        "end": 3,
        "start_ms": 0,
        "end_ms": 3000,
        "kill_count": 1,
        "filename": "clip_001_single_kill_0s.mp4"
    }]
    # TASK-004: Pipeline now uses extract_from_json, mock that method
    mock_clip_ext.return_value.extract_from_json.return_value = expected_clips
    mock_clip_ext.return_value.extract_clips.return_value = expected_clips
    
    mock_joiner.return_value.join_clips.return_value = True
    mock_mixer.return_value.mix_audio.return_value = "final.mp4"
    mock_report.return_value.generate.return_value = "report.md"
    
    mock_temp_mgr.create_temp_dir.return_value = "tmp_dir"
    
    # Run pipeline
    pipeline = Pipeline(mock_config)
    # Disable checkpoint saving to avoid serialization issues with MagicMocks
    pipeline._save_checkpoint = MagicMock() 
    
    # Create the temp directory for checkpointing
    if not os.path.exists("temp"):
        os.makedirs("temp")

    def mock_exists(path):
        if str(path).startswith("test_output"):
            return False
        return True
    
    with patch("os.path.abspath", side_effect=lambda x: x):
        with patch("os.path.exists", side_effect=mock_exists):
            with patch("os.makedirs"):  # Mock directory creation for history
                success = pipeline.run("dummy_video.mp4")
    
    # Verify stages
    assert success is True
    assert pipeline.stages["metadata"].status == StageStatus.SUCCESS
    assert pipeline.stages["frames"].status == StageStatus.SUCCESS
    assert pipeline.stages["detection"].status == StageStatus.SUCCESS
    assert pipeline.stages["clips"].status == StageStatus.SUCCESS
    assert pipeline.stages["join"].status == StageStatus.SUCCESS
    assert pipeline.stages["audio"].status == StageStatus.SUCCESS
    assert pipeline.stages["report"].status == StageStatus.SUCCESS
    assert pipeline.stages["history"].status == StageStatus.SUCCESS
    
    # Verify results
    assert "video_info" in pipeline.results
    assert len(pipeline.results["events"]) == 1
    assert pipeline.results["clips"] == expected_clips
    
    # TASK-003: Verify clip metadata structure
    for clip in pipeline.results["clips"]:
        assert "path" in clip, "Clip should have 'path' field"
        assert "start_ms" in clip, "Clip should have 'start_ms' field"
        assert "end_ms" in clip, "Clip should have 'end_ms' field"
        assert isinstance(clip["start_ms"], int), "start_ms should be integer"
        assert isinstance(clip["end_ms"], int), "end_ms should be integer"

def test_pipeline_loads_templates_from_detection_config(mock_config):
    mock_config["detection"]["templates"] = {
        "kill_icon": {
            "path": "models/templates/test_game/kill_icon.png",
            "threshold": 0.8,
        }
    }
    pipeline = Pipeline(mock_config)
    matcher = MagicMock()
    matcher.templates = {"kill_icon": object()}
    matcher.load_templates_from_config.return_value = 1

    loaded_count = pipeline._load_detection_templates(matcher)

    assert loaded_count == 1
    matcher.load_templates_from_config.assert_called_once()
    detection_cfg = matcher.load_templates_from_config.call_args.args[0]
    assert detection_cfg["templates"]["kill_icon"]["path"] == "models/templates/test_game/kill_icon.png"

def test_pipeline_no_kills(mock_config):
    with patch("src.pipeline.pipeline.VideoInfo") as mock_video_info, \
         patch("src.pipeline.pipeline.FrameExtractor") as mock_frame_ext, \
         patch("src.pipeline.pipeline.KillDetector") as mock_kill_det, \
         patch("src.pipeline.pipeline.ModelManager"), \
         patch("src.pipeline.pipeline.create_progress_bar"), \
         patch("src.pipeline.pipeline.AudioMixer"), \
         patch("src.pipeline.pipeline.ReportGenerator") as mock_report, \
         patch("src.pipeline.pipeline.HistoryManager"), \
         patch("cv2.imread"), \
         patch("src.pipeline.pipeline.temp_manager"):
        
        mock_video_info.return_value.duration = 10
        mock_frame_ext.return_value.extract_frames.return_value = ["frame_1000.jpg"]
        mock_kill_det.return_value.process_video_batch.return_value = []
        mock_report.return_value.generate.return_value = "report.md"
        
        pipeline = Pipeline(mock_config)
        pipeline._save_checkpoint = MagicMock()

        def mock_exists(path):
            if str(path).startswith("test_output"):
                return False
            return True
        
        with patch("os.path.abspath", side_effect=lambda x: x), \
             patch("os.path.exists", side_effect=mock_exists), \
             patch("os.makedirs"):  # Mock directory creation for history
            success = pipeline.run("dummy_video.mp4")
            
        assert success is True
        assert pipeline.stages["clips"].status == StageStatus.SKIPPED
        assert pipeline.results["clips"] == []

def test_pipeline_missing_clip_file(mock_config):
    """TASK-003: Verify pipeline handles missing clip files gracefully"""
    with patch("src.pipeline.pipeline.VideoInfo") as mock_video_info, \
         patch("src.pipeline.pipeline.FrameExtractor") as mock_frame_ext, \
         patch("src.pipeline.pipeline.KillDetector") as mock_kill_det, \
         patch("src.pipeline.pipeline.ModelManager"), \
         patch("src.pipeline.pipeline.ClipExtractor") as mock_clip_ext, \
         patch("src.pipeline.pipeline.create_progress_bar"), \
         patch("cv2.imread"), \
         patch("src.pipeline.pipeline.temp_manager"):
        
        mock_video_info.return_value.duration = 10
        mock_video_info.return_value.width = 1920
        mock_video_info.return_value.height = 1080
        mock_video_info.return_value.fps = 60
        
        mock_frame_ext.return_value.extract_frames.return_value = ["frame_1000.jpg"]
        mock_kill_det.return_value.process_video_batch.return_value = [
            {"timestamp_ms": 1000, "confidence": 0.9, "type": "kill"}
        ]
        
        # Clip with path that doesn't exist
        mock_clip_ext.return_value.extract_clips.return_value = [{
            "path": "/nonexistent/clip1.mp4",
            "start_ms": 0,
            "end_ms": 3000,
            "kill_count": 1
        }]
        
        pipeline = Pipeline(mock_config)
        pipeline._save_checkpoint = MagicMock()
        
        with patch("os.path.abspath", side_effect=lambda x: x):
            # Mock exists to return False for clip path but True for checkpoint dir
            def mock_exists(path):
                if "clip1.mp4" in path:
                    return False
                return True
            
            with patch("os.path.exists", side_effect=mock_exists):
                success = pipeline.run("dummy_video.mp4")
                
        # Pipeline should fail due to missing file
        assert success is False

def test_pipeline_missing_path_field(mock_config):
    """TASK-003: Verify pipeline handles clips without path field"""
    with patch("src.pipeline.pipeline.VideoInfo") as mock_video_info, \
         patch("src.pipeline.pipeline.FrameExtractor") as mock_frame_ext, \
         patch("src.pipeline.pipeline.KillDetector") as mock_kill_det, \
         patch("src.pipeline.pipeline.ModelManager"), \
         patch("src.pipeline.pipeline.ClipExtractor") as mock_clip_ext, \
         patch("src.pipeline.pipeline.create_progress_bar"), \
         patch("cv2.imread"), \
         patch("src.pipeline.pipeline.temp_manager"):
        
        mock_video_info.return_value.duration = 10
        mock_video_info.return_value.width = 1920
        mock_video_info.return_value.height = 1080
        mock_video_info.return_value.fps = 60
        
        mock_frame_ext.return_value.extract_frames.return_value = ["frame_1000.jpg"]
        mock_kill_det.return_value.process_video_batch.return_value = [
            {"timestamp_ms": 1000, "confidence": 0.9, "type": "kill"}
        ]
        
        # Clip without path field (only old output_path field missing)
        mock_clip_ext.return_value.extract_clips.return_value = [{
            "start_ms": 0,
            "end_ms": 3000,
            "kill_count": 1
            # Missing both 'path' and 'output_path'
        }]
        
        pipeline = Pipeline(mock_config)
        pipeline._save_checkpoint = MagicMock()
        
        with patch("os.path.abspath", side_effect=lambda x: x), \
             patch("os.path.exists", return_value=True):
            success = pipeline.run("dummy_video.mp4")
                
        # Pipeline should fail due to missing path field
        assert success is False

if __name__ == "__main__":
    pytest.main([__file__])
