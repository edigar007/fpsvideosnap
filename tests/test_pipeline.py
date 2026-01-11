import pytest
import os
import shutil
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
    
    expected_clips = [{"path": "clip1.mp4", "start": 0, "end": 3, "kill_count": 1}]
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
    
    with patch("os.path.abspath", side_effect=lambda x: x):
        with patch("os.path.exists", return_value=True):
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

def test_pipeline_no_kills(mock_config):
    with patch("src.pipeline.pipeline.VideoInfo") as mock_video_info, \
         patch("src.pipeline.pipeline.FrameExtractor") as mock_frame_ext, \
         patch("src.pipeline.pipeline.KillDetector") as mock_kill_det, \
         patch("src.pipeline.pipeline.ModelManager") as mock_model_mgr, \
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
        
        with patch("os.path.abspath", side_effect=lambda x: x), \
             patch("os.path.exists", return_value=True):
            success = pipeline.run("dummy_video.mp4")
            
        assert success is True
        assert pipeline.stages["clips"].status == StageStatus.SKIPPED
        assert pipeline.results["clips"] == []

if __name__ == "__main__":
    pytest.main([__file__])
