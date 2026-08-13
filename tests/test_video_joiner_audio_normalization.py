from unittest.mock import MagicMock, patch

from src.video.video_joiner import AudioProbeResult, VideoJoiner


@patch("subprocess.run")
def test_video_joiner_normalize_command_uses_safe_intermediate_settings(mock_run):
    config = {
        "global": {"temp_dir": "temp"},
        "video": {
            "ffmpeg_path": "ffmpeg",
            "fps": 60,
            "join_fix": {
                "safe_preset": "medium",
                "safe_crf": 18,
                "safe_audio_rate": 48000,
                "safe_channel_layout": "stereo",
            },
        },
        "highlights": {"transition_type": "none"},
    }
    joiner = VideoJoiner(config)
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(joiner, "_has_audio_stream", return_value=True):
        output = joiner._normalize_clip_for_join("clip1.mp4", "temp/join_norm", 0)

    assert output.endswith("join_norm_001.mp4")
    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)
    assert "fps=60" in cmd_str
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos" in cmd_str
    assert "setsar=1" in cmd_str
    assert "format=yuv420p" in cmd_str
    assert "aformat=sample_rates=48000:channel_layouts=stereo" in cmd_str
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-movflags" in cmd and "+faststart" in cmd
    assert "-avoid_negative_ts" in cmd and "make_zero" in cmd
    assert "-max_interleave_delta" in cmd and "0" in cmd


@patch("src.video.video_joiner.VideoInfo")
@patch("subprocess.run")
def test_video_joiner_normalize_adds_silent_track_for_no_audio(mock_run, mock_info):
    config = {
        "global": {"temp_dir": "temp"},
        "video": {
            "ffmpeg_path": "ffmpeg",
            "fps": 60,
            "join_fix": {
                "safe_audio_rate": 48000,
                "safe_channel_layout": "stereo",
            },
        },
        "highlights": {"transition_type": "none"},
    }
    joiner = VideoJoiner(config)
    mock_info.return_value.duration = 5.0
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(joiner, "_has_audio_stream", return_value=False):
        output = joiner._normalize_clip_for_join("clip1.mp4", "temp/join_norm", 0)

    assert output.endswith("join_norm_001.mp4")
    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)
    assert "-f lavfi" in cmd_str
    assert "-t 5.000" in cmd_str
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in cmd_str
    assert "[1:a]aformat=sample_rates=48000:channel_layouts=stereo" in cmd_str


@patch("subprocess.run")
def test_video_joiner_audio_probe_distinguishes_missing_audio(mock_run):
    joiner = VideoJoiner({"video": {"ffprobe_path": "custom_ffprobe"}})
    mock_run.return_value = MagicMock(stdout='{"streams": []}')

    assert joiner._probe_audio_stream("clip.mp4") == AudioProbeResult.NO_AUDIO
    assert joiner._any_clip_missing_audio(["clip.mp4"]) is True
    assert mock_run.call_args.args[0][0] == "custom_ffprobe"


@patch("src.video.video_joiner.VideoInfo")
@patch("subprocess.run")
def test_video_joiner_probes_each_clip_once_during_join(mock_run, mock_info):
    """join_clips must not ffprobe the same clip twice (audio check + normalize)."""
    config = {
        "global": {"temp_dir": "temp"},
        "video": {
            "ffmpeg_path": "ffmpeg",
            "ffprobe_path": "ffprobe",
            "hwaccel": None,
            "join_fix": {"pre_normalize_clips": False},
        },
        "highlights": {"transition_type": "none"},
    }
    joiner = VideoJoiner(config)
    mock_info.return_value.duration = 5.0
    mock_run.return_value = MagicMock(stdout='{"streams": []}')

    # No audio on either clip -> the join flow checks audio presence and then
    # normalizes each clip, which used to probe every clip twice.
    success = joiner.join_clips(["clip1.mp4", "clip2.mp4"], "out.mp4")

    assert success
    probe_calls = [call for call in mock_run.call_args_list if call.args[0][0] == "ffprobe"]
    assert len(probe_calls) == 2
    assert {call.args[0][-1] for call in probe_calls} == {"clip1.mp4", "clip2.mp4"}


@patch("subprocess.Popen")
@patch("subprocess.run")
def test_video_joiner_audio_probe_failure_stops_join(mock_run, mock_popen):
    joiner = VideoJoiner(
        {
            "video": {
                "join_fix": {"pre_normalize_clips": False},
                "hwaccel": None,
            },
            "highlights": {"transition_type": "none"},
        }
    )
    mock_run.side_effect = OSError("ffprobe unavailable")

    assert joiner.join_clips(["clip1.mp4", "clip2.mp4"], "out.mp4") is False
    mock_popen.assert_not_called()
