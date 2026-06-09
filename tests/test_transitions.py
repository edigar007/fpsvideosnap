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
def test_video_joiner_pre_normalizes_clips_before_concat(mock_run):
    config = {
        "global": {"temp_dir": "temp"},
        "video": {
            "ffmpeg_path": "ffmpeg",
            "encoder": "h264_nvenc",
            "fps": 60,
            "bitrate": "20M",
            "hwaccel": "cuda",
            "join_fix": {
                "pre_normalize_clips": True,
                "keep_intermediates": False,
                "safe_preset": "medium",
                "safe_crf": 18,
                "safe_audio_rate": 48000,
                "safe_channel_layout": "stereo",
            },
        },
        "highlights": {
            "transition_type": "none",
            "transition_duration": 0.5
        }
    }

    joiner = VideoJoiner(config)
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(
        joiner,
        "_prepare_join_inputs",
        return_value=(["norm1.mp4", "norm2.mp4"], "temp/join_norm"),
    ) as mock_prepare:
        success = joiner.join_clips(["c1.mp4", "c2.mp4"], "out.mp4")

    assert success
    mock_prepare.assert_called_once_with(["c1.mp4", "c2.mp4"])
    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)
    assert "-i norm1.mp4" in cmd_str
    assert "-i norm2.mp4" in cmd_str


@patch("subprocess.run")
def test_video_joiner_forces_pre_normalize_when_clip_has_no_audio(mock_run):
    config = {
        "global": {"temp_dir": "temp"},
        "video": {
            "ffmpeg_path": "ffmpeg",
            "join_fix": {
                "pre_normalize_clips": False,
            },
        },
        "highlights": {"transition_type": "none"},
    }

    joiner = VideoJoiner(config)
    mock_run.return_value = MagicMock(returncode=0)

    with (
        patch.object(joiner, "_any_clip_missing_audio", return_value=True),
        patch.object(
            joiner,
            "_prepare_join_inputs",
            return_value=(["norm1.mp4", "norm2.mp4"], "temp/join_norm"),
        ) as mock_prepare,
    ):
        success = joiner.join_clips(["c1.mp4", "c2.mp4"], "out.mp4")

    assert success
    mock_prepare.assert_called_once_with(["c1.mp4", "c2.mp4"])


@patch("subprocess.run")
def test_video_joiner_concat_normalizes_inputs_and_forces_first_keyframe(mock_run):
    config = {
        "video": {
            "ffmpeg_path": "ffmpeg",
            "encoder": "h264_nvenc",
            "fps": 60,
            "bitrate": "20M",
            "hwaccel": "cuda",
            "join_fix": {
                "pre_normalize_clips": False,
                "safe_audio_rate": 48000,
                "safe_channel_layout": "stereo",
            },
        },
        "highlights": {
            "transition_type": "none",
            "transition_duration": 0.5
        }
    }

    joiner = VideoJoiner(config)
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(joiner, "_any_clip_missing_audio", return_value=False):
        success = joiner.join_clips(["c1.mp4", "c2.mp4"], "out.mp4")

    assert success
    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)

    assert "fps=60" in cmd_str
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos" in cmd_str
    assert "setsar=1" in cmd_str
    assert "format=yuv420p" in cmd_str
    assert "settb=AVTB" in cmd_str
    assert "setpts=PTS-STARTPTS" in cmd_str
    assert "aformat=sample_rates=48000:channel_layouts=stereo" in cmd_str
    assert "aresample=async=1:first_pts=0" in cmd_str
    assert "asetpts=PTS-STARTPTS" in cmd_str
    assert "concat=n=2:v=1:a=0" in cmd_str
    assert "concat=n=2:v=0:a=1" in cmd_str
    assert "-force_key_frames" in cmd
    assert "-movflags" in cmd and "+faststart" in cmd
    assert "-avoid_negative_ts" in cmd and "make_zero" in cmd
    assert "-max_interleave_delta" in cmd and "0" in cmd


@patch("src.video.video_joiner.VideoInfo")
@patch("subprocess.Popen")
def test_video_joiner_complex_filter_logic(mock_popen, mock_info):
    mock_instance = MagicMock()
    mock_instance.duration = 10.0
    mock_info.return_value = mock_instance

    config = {
        "video": {
            "ffmpeg_path": "ffmpeg",
            "encoder": "h264_nvenc",
            "fps": 60,
            "bitrate": "20M",
            "hwaccel": "cuda",
            "join_fix": {
                "pre_normalize_clips": False,
                "safe_audio_rate": 48000,
                "safe_channel_layout": "stereo",
            },
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

    with patch.object(joiner, "_any_clip_missing_audio", return_value=False):
        success = joiner.join_clips(["c1.mp4", "c2.mp4", "c3.mp4"], "out.mp4")

    assert success
    cmd = mock_popen.call_args[0][0]
    cmd_str = " ".join(cmd)

    assert "fps=60" in cmd_str
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos" in cmd_str
    assert "setsar=1" in cmd_str
    assert "format=yuv420p" in cmd_str
    assert "settb=AVTB" in cmd_str
    assert "setpts=PTS-STARTPTS" in cmd_str
    assert "aformat=sample_rates=48000:channel_layouts=stereo" in cmd_str
    assert "aresample=async=1:first_pts=0" in cmd_str
    assert "asetpts=PTS-STARTPTS" in cmd_str
    assert "xfade=transition=fade" in cmd_str
    assert "acrossfade=d=0.5" in cmd_str
    assert "[vnorm0][vnorm1]xfade=transition=fade:duration=0.5:offset=9.5[v1]" in cmd_str
    assert "[a1][anorm2]acrossfade=d=0.5[a2]" in cmd_str
    assert "offset=9.5" in cmd_str
    assert "offset=19.0" in cmd_str
    assert "-force_key_frames" in cmd
    assert "-movflags" in cmd and "+faststart" in cmd
    assert "-avoid_negative_ts" in cmd and "make_zero" in cmd
    assert "-max_interleave_delta" in cmd and "0" in cmd


@patch("src.video.video_joiner.VideoInfo")
@patch("subprocess.Popen")
def test_video_joiner_segments_long_xfade_chain(mock_popen, mock_info, tmp_path):
    mock_instance = MagicMock()
    mock_instance.duration = 10.0
    mock_info.return_value = mock_instance

    mock_process = MagicMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    config = {
        "global": {"temp_dir": str(tmp_path)},
        "video": {
            "ffmpeg_path": "ffmpeg",
            "encoder": "h264_nvenc",
            "fps": 60,
            "bitrate": "20M",
            "hwaccel": "cuda",
            "join_fix": {
                "pre_normalize_clips": False,
                "keep_intermediates": True,
                "safe_audio_rate": 48000,
                "safe_channel_layout": "stereo",
                "xfade_segment_size": 3,
            },
        },
        "highlights": {
            "transition_type": "fade",
            "transition_duration": 0.5
        }
    }

    joiner = VideoJoiner(config)
    clips = [f"c{i}.mp4" for i in range(1, 7)]

    with patch.object(joiner, "_any_clip_missing_audio", return_value=False):
        success = joiner.join_clips(clips, "out.mp4")

    assert success
    assert mock_popen.call_count == 3

    first_cmd = " ".join(mock_popen.call_args_list[0].args[0])
    second_cmd = " ".join(mock_popen.call_args_list[1].args[0])
    final_cmd = " ".join(mock_popen.call_args_list[2].args[0])

    assert "-i c1.mp4" in first_cmd
    assert "-i c3.mp4" in first_cmd
    assert "-i c4.mp4" in second_cmd
    assert "-i c6.mp4" in second_cmd
    assert "xfade_segment_001.mp4" in final_cmd
    assert "xfade_segment_002.mp4" in final_cmd
    assert final_cmd.endswith(" out.mp4")


@patch("src.video.video_joiner.VideoInfo")
def test_video_joiner_duration_reading_via_property(mock_info):
    config = {
        "video": {
            "ffmpeg_path": "ffmpeg",
            "encoder": "h264_nvenc",
            "fps": 60,
            "bitrate": "20M",
            "hwaccel": "cuda",
            "join_fix": {"pre_normalize_clips": False},
        },
        "highlights": {
            "transition_type": "fade",
            "transition_duration": 0.5
        }
    }

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
        with patch.object(joiner, "_any_clip_missing_audio", return_value=False):
            success = joiner.join_clips(["c1.mp4", "c2.mp4"], "out.mp4")

        assert success
        assert mock_info.call_count == 2


@patch("src.video.video_joiner.VideoInfo")
def test_video_joiner_handles_missing_duration(mock_info):
    config = {
        "video": {"ffmpeg_path": "ffmpeg", "join_fix": {"pre_normalize_clips": False}},
        "highlights": {"transition_type": "fade", "transition_duration": 0.5}
    }

    mock_info.side_effect = RuntimeError("Failed to extract video metadata")

    joiner = VideoJoiner(config)
    with patch.object(joiner, "_any_clip_missing_audio", return_value=False):
        success = joiner.join_clips(["bad.mp4", "clip2.mp4"], "out.mp4")

    assert not success


@patch("src.video.video_joiner.VideoInfo")
def test_video_joiner_handles_zero_duration(mock_info):
    config = {
        "video": {"ffmpeg_path": "ffmpeg", "join_fix": {"pre_normalize_clips": False}},
        "highlights": {"transition_type": "fade", "transition_duration": 0.5}
    }

    mock_instance1 = MagicMock()
    mock_instance1.duration = 0.0
    mock_instance2 = MagicMock()
    mock_instance2.duration = 5.0
    mock_info.side_effect = [mock_instance1, mock_instance2]

    joiner = VideoJoiner(config)
    with patch.object(joiner, "_any_clip_missing_audio", return_value=False):
        success = joiner.join_clips(["zero.mp4", "clip2.mp4"], "out.mp4")

    assert not success


