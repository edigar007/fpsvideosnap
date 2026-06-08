from src.video.ffmpeg_command import JoinCommandBuilder


def _builder():
    return JoinCommandBuilder(
        ffmpeg_path="ffmpeg",
        encoder="h264_nvenc",
        fps=60,
        bitrate="20M",
        hwaccel="cuda",
        output_preset="p4",
        safe_preset="medium",
        safe_crf="18",
        safe_audio_rate="48000",
        safe_channel_layout="stereo",
    )


def _filters(count):
    filter_parts = []
    video_labels = []
    audio_labels = []
    for index in range(count):
        video_labels.append(f"vnorm{index}")
        audio_labels.append(f"anorm{index}")
    return filter_parts, video_labels, audio_labels


def test_join_command_builder_builds_concat_command_structure():
    command = _builder().build_concat_command(["c1.mp4", "c2.mp4"], "out.mp4", _filters)

    assert command.args[:4] == ["ffmpeg", "-y", "-hwaccel", "cuda"]
    assert command.args[-1] == "out.mp4"
    assert "concat=n=2:v=1:a=0[vout]" in command.filter_complex
    assert "concat=n=2:v=0:a=1[aout]" in command.filter_complex
    assert "-forced-idr" in command.args
    assert "-strict_gop" in command.args


def test_join_command_builder_builds_xfade_command_and_short_clip_warning():
    command = _builder().build_xfade_command(
        ["c1.mp4", "c2.mp4"],
        "out.mp4",
        durations=[0.4, 2.0],
        transition_duration=0.5,
        transitions=["fade"],
        normalized_input_filters=_filters,
    )

    assert command.args[-1] == "out.mp4"
    assert "xfade=transition=fade:duration=0.2:offset=0.2" in command.filter_complex
    assert "acrossfade=d=0.2" in command.filter_complex
    assert command.warnings == ["Clip 0 or 1 is too short. Reducing transition duration to 0.20s"]


def test_join_command_builder_builds_normalize_command_with_silent_audio():
    command = _builder().build_normalize_command(
        "clip.mp4",
        "norm.mp4",
        has_audio=False,
        duration=5.0,
    )

    assert "-f" in command.args
    assert "lavfi" in command.args
    assert "-t" in command.args
    assert "5.000" in command.args
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in command.args
    assert "[1:a]aformat=sample_rates=48000:channel_layouts=stereo" in command.filter_complex
