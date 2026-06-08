import json
from unittest.mock import MagicMock, patch

from src.audio.audio_info import AudioInfo
from src.audio.audio_mixer import AudioMixer
from src.video.frame_extractor import FrameExtractor
from src.video.video_info import VideoInfo
from src.video.video_joiner import VideoJoiner


def test_video_info_uses_configured_ffprobe(tmp_path):
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")
    ffprobe_result = MagicMock(
        stdout=json.dumps(
            {
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "60/1"}],
                "format": {"duration": "10.0", "bit_rate": "1000"},
            }
        )
    )

    with patch("subprocess.run", return_value=ffprobe_result) as mock_run:
        info = VideoInfo(str(video_path), ffprobe_path="custom_ffprobe")

    assert info.duration == 10.0
    assert mock_run.call_args.args[0][0] == "custom_ffprobe"


def test_audio_info_uses_configured_ffprobe(tmp_path):
    audio_path = tmp_path / "music.mp3"
    audio_path.write_bytes(b"audio")
    ffprobe_result = MagicMock(
        stdout=json.dumps(
            {
                "streams": [{"codec_type": "audio", "sample_rate": "48000", "channels": 2, "codec_name": "aac"}],
                "format": {"duration": "3.0", "format_name": "mp3", "bit_rate": "128000"},
            }
        )
    )

    with patch("subprocess.run", return_value=ffprobe_result) as mock_run:
        info = AudioInfo(str(audio_path), ffprobe_path="custom_ffprobe")

    assert info.duration == 3.0
    assert mock_run.call_args.args[0][0] == "custom_ffprobe"


def test_frame_extractor_precise_fallback_uses_configured_ffprobe(tmp_path):
    video_path = tmp_path / "input.mp4"
    output_dir = tmp_path / "frames"
    video_path.write_bytes(b"video")

    def run_side_effect(cmd, *args, **kwargs):
        if cmd[0] == "custom_ffprobe":
            return MagicMock(stdout="0.1")
        return MagicMock(stdout="", stderr="", returncode=0)

    extractor = FrameExtractor(
        ffmpeg_path="custom_ffmpeg",
        ffprobe_path="custom_ffprobe",
        hwaccel=None,
        mode="precise",
    )

    with patch("subprocess.run", side_effect=run_side_effect) as mock_run, \
         patch("src.utils.progress.create_progress_bar") as mock_progress:
        mock_progress.return_value.update.return_value = None
        mock_progress.return_value.close.return_value = None
        extractor.extract_frames(str(video_path), str(output_dir), interval_ms=100)

    assert mock_run.call_args_list[0].args[0][0] == "custom_ffprobe"
    assert any(call.args[0][0] == "custom_ffmpeg" for call in mock_run.call_args_list[1:])


def test_audio_mixer_uses_configured_tools_for_probe_and_processing():
    config = {"video": {"ffmpeg_path": "custom_ffmpeg", "ffprobe_path": "custom_ffprobe"}}
    mixer = AudioMixer(config)

    with patch("subprocess.run", return_value=MagicMock(stdout='{"streams": []}')) as mock_run:
        assert mixer._has_audio_stream("joined.mp4") is False

    assert mixer.ffmpeg_path == "custom_ffmpeg"
    assert mixer.music_processor.ffmpeg_path == "custom_ffmpeg"
    assert mixer.music_processor.ffprobe_path == "custom_ffprobe"
    assert mock_run.call_args.args[0][0] == "custom_ffprobe"


def test_video_joiner_passes_configured_ffprobe_to_video_info():
    joiner = VideoJoiner({"video": {"ffprobe_path": "custom_ffprobe", "hwaccel": None}})

    with patch("src.video.video_joiner.VideoInfo") as mock_info, \
         patch.object(joiner, "_build_normalized_input_filters", return_value=([], ["v0", "v1"], ["a0", "a1"])), \
         patch("subprocess.Popen") as mock_popen:
        mock_info.return_value.duration = 2.0
        mock_popen.return_value.communicate.return_value = (b"", b"")
        mock_popen.return_value.returncode = 0

        assert joiner._join_with_xfade(["clip1.mp4", "clip2.mp4"], "out.mp4") is True

    assert mock_info.call_args_list[0].kwargs["ffprobe_path"] == "custom_ffprobe"
    assert mock_info.call_args_list[1].kwargs["ffprobe_path"] == "custom_ffprobe"
