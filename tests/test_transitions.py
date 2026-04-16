import pytest
from unittest.mock import MagicMock, patch
from src.video.transitions import TransitionManager
from src.video.video_joiner import VideoJoiner

def test_transition_manager_init():
    tm = TransitionManager(transition_type="fade", duration=1.0)
    assert tm.transition_type == "fade"
    assert tm.get_duration() == 1.0

def test_transition_manager_random():
    tm = TransitionManager(transition_type="random")
    trans = tm.get_transition()
    assert trans in TransitionManager.SUPPORTED_TRANSITIONS

def test_transition_manager_none():
    tm = TransitionManager(transition_type="none")
    assert tm.get_transition() is None

def test_transition_manager_unsupported():
    tm = TransitionManager(transition_type="invalid_effect")
    # Should fallback to fade
    assert tm.get_transition() == "fade"

@patch("src.video.video_joiner.VideoInfo")
@patch("subprocess.run")
def test_video_joiner_single_clip(mock_run, mock_info):
    config = {
        "video": {"ffmpeg_path": "ffmpeg"},
        "highlights": {"transition_type": "fade", "transition_duration": 0.5}
    }
    joiner = VideoJoiner(config)
    mock_run.return_value = MagicMock(returncode=0)
    
    success = joiner.join_clips(["clip1.mp4"], "output.mp4")
    
    assert success
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "-c" in args
    assert "copy" in args

@patch("subprocess.run")
def test_video_joiner_concat_normalizes_inputs_and_forces_first_keyframe(mock_run):
    config = {
        "video": {
            "ffmpeg_path": "ffmpeg",
            "encoder": "h264_nvenc",
            "fps": 60,
            "bitrate": "20M",
            "hwaccel": "cuda"
        },
        "highlights": {
            "transition_type": "none",
            "transition_duration": 0.5
        }
    }

    joiner = VideoJoiner(config)
    mock_run.return_value = MagicMock(returncode=0)

    success = joiner.join_clips(["c1.mp4", "c2.mp4"], "out.mp4")

    assert success
    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)

    assert "settb=AVTB" in cmd_str
    assert "setpts=PTS-STARTPTS" in cmd_str
    assert "aresample=async=1:first_pts=0" in cmd_str
    assert "asetpts=PTS-STARTPTS" in cmd_str
    assert "concat=n=2:v=1:a=0" in cmd_str
    assert "concat=n=2:v=0:a=1" in cmd_str
    assert "-force_key_frames" in cmd
    assert "0" in cmd


@patch("src.video.video_joiner.VideoInfo")
@patch("subprocess.Popen")
def test_video_joiner_complex_filter_logic(mock_popen, mock_info):
    # Mock VideoInfo to return fixed duration via property
    mock_instance = MagicMock()
    # TASK-007: Mock the duration property, not get_metadata
    mock_instance.duration = 10.0
    mock_info.return_value = mock_instance

    config = {
        "video": {
            "ffmpeg_path": "ffmpeg",
            "encoder": "h264_nvenc",
            "fps": 60,
            "bitrate": "20M",
            "hwaccel": "cuda"
        },
        "highlights": {
            "transition_type": "fade",
            "transition_duration": 0.5
        }
    }

    joiner = VideoJoiner(config)
    mock_process = MagicMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    success = joiner.join_clips(["c1.mp4", "c2.mp4", "c3.mp4"], "out.mp4")

    assert success
    assert mock_popen.called

    # Check if complex filter contains expected xfade and acrossfade
    cmd = mock_popen.call_args[0][0]
    cmd_str = " ".join(cmd)

    assert "settb=AVTB" in cmd_str
    assert "setpts=PTS-STARTPTS" in cmd_str
    assert "aresample=async=1:first_pts=0" in cmd_str
    assert "asetpts=PTS-STARTPTS" in cmd_str
    assert "xfade=transition=fade" in cmd_str
    assert "acrossfade=d=0.5" in cmd_str
    assert "[vnorm0][vnorm1]xfade=transition=fade:duration=0.5:offset=9.5[v1]" in cmd_str
    assert "[a1][anorm2]acrossfade=d=0.5[a2]" in cmd_str
    # Check offsets:
    # c1 duration 10. offset = 10 - 0.5 = 9.5
    # c2 start after 10 - 0.5 = 9.5. c2 duration 10.
    # combined duration so far = 10 + 10 - 0.5 = 19.5
    # next offset = 19.5 - 0.5 = 19.0
    assert "offset=9.5" in cmd_str
    assert "offset=19.0" in cmd_str
    assert "-force_key_frames" in cmd
    assert "0" in cmd

@patch("src.video.video_joiner.VideoInfo")
def test_video_joiner_duration_reading_via_property(mock_info):
    """TASK-007: Test that VideoJoiner reads durations via VideoInfo.duration property."""
    config = {
        "video": {
            "ffmpeg_path": "ffmpeg",
            "encoder": "h264_nvenc",
            "fps": 60,
            "bitrate": "20M",
            "hwaccel": "cuda"
        },
        "highlights": {
            "transition_type": "fade",
            "transition_duration": 0.5
        }
    }
    
    # Mock VideoInfo instances with duration property
    mock_instance1 = MagicMock()
    mock_instance1.duration = 5.0
    
    mock_instance2 = MagicMock()
    mock_instance2.duration = 7.5
    
    mock_info.side_effect = [mock_instance1, mock_instance2]
    
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        joiner = VideoJoiner(config)
        success = joiner.join_clips(["c1.mp4", "c2.mp4"], "out.mp4")
        
        assert success
        # Verify VideoInfo was called for each clip
        assert mock_info.call_count == 2

@patch("src.video.video_joiner.VideoInfo")
def test_video_joiner_handles_missing_duration(mock_info):
    """TASK-007: Test that VideoJoiner guards against missing/invalid duration metadata."""
    config = {
        "video": {"ffmpeg_path": "ffmpeg"},
        "highlights": {"transition_type": "fade", "transition_duration": 0.5}
    }
    
    # Mock VideoInfo to raise exception
    mock_info.side_effect = RuntimeError("Failed to extract video metadata")
    
    joiner = VideoJoiner(config)
    success = joiner.join_clips(["bad.mp4", "clip2.mp4"], "out.mp4")
    
    assert not success  # Should fail gracefully

@patch("src.video.video_joiner.VideoInfo")
def test_video_joiner_handles_zero_duration(mock_info):
    """TASK-007: Test that VideoJoiner guards against zero duration."""
    config = {
        "video": {"ffmpeg_path": "ffmpeg"},
        "highlights": {"transition_type": "fade", "transition_duration": 0.5}
    }

    mock_instance1 = MagicMock()
    mock_instance1.duration = 0.0  # Invalid duration
    mock_instance2 = MagicMock()
    mock_instance2.duration = 5.0
    mock_info.side_effect = [mock_instance1, mock_instance2]

    joiner = VideoJoiner(config)
    success = joiner.join_clips(["zero.mp4", "clip2.mp4"], "out.mp4")

    assert not success  # Should fail due to invalid duration
