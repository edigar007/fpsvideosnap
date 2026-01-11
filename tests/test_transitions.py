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

@patch("src.video.video_joiner.VideoInfo")
@patch("subprocess.Popen")
def test_video_joiner_complex_filter_logic(mock_popen, mock_info):
    # Mock VideoInfo to return fixed duration
    mock_instance = mock_info.return_value
    mock_instance.get_metadata.return_value = {"format": {"duration": "10.0"}}
    
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
    
    assert "xfade=transition=fade" in cmd_str
    assert "acrossfade=d=0.5" in cmd_str
    # Check offsets: 
    # c1 duration 10. offset = 10 - 0.5 = 9.5
    # c2 start after 10 - 0.5 = 9.5. c2 duration 10. 
    # combined duration so far = 10 + 10 - 0.5 = 19.5
    # next offset = 19.5 - 0.5 = 19.0
    assert "offset=9.5" in cmd_str
    assert "offset=19.0" in cmd_str
