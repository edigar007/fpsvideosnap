from src.pipeline.multi_video import merge_clips_to_highlight


class CancelEvent:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled

    def set(self):
        self.cancelled = True

    def is_set(self):
        return self.cancelled


class Joiner:
    calls = 0
    cancel_event = None

    def __init__(self, config):
        self.config = config

    def join_clips(self, clip_paths, output_path):
        type(self).calls += 1
        if type(self).cancel_event:
            type(self).cancel_event.set()
        return True


class Mixer:
    calls = 0
    cancel_event = None

    def __init__(self, config):
        self.config = config

    def mix_audio(self, input_path, output_path):
        type(self).calls += 1
        if type(self).cancel_event:
            type(self).cancel_event.set()
        return output_path


class ReportGenerator:
    calls = 0

    def __init__(self, output_dir):
        self.output_dir = output_dir

    def generate(self, video_info, clips, config):
        type(self).calls += 1
        return "report.md"


def _config(tmp_path):
    return {"global": {"output_dir": str(tmp_path)}}


def _clips():
    return [{"path": "clip1.mp4"}]


def _reset_fakes():
    Joiner.calls = 0
    Joiner.cancel_event = None
    Mixer.calls = 0
    Mixer.cancel_event = None
    ReportGenerator.calls = 0


def test_merge_cancel_before_join_skips_joiner(tmp_path):
    _reset_fakes()

    result = merge_clips_to_highlight(
        _config(tmp_path),
        ["video1.mp4"],
        _clips(),
        video_joiner_cls=Joiner,
        audio_mixer_cls=Mixer,
        report_generator_cls=ReportGenerator,
        cancel_event=CancelEvent(cancelled=True),
    )

    assert result["cancelled"] is True
    assert result["stage"] == "merge_join"
    assert Joiner.calls == 0
    assert Mixer.calls == 0
    assert ReportGenerator.calls == 0


def test_merge_cancel_after_join_skips_audio_mix(tmp_path):
    _reset_fakes()
    cancel_event = CancelEvent()
    Joiner.cancel_event = cancel_event

    result = merge_clips_to_highlight(
        _config(tmp_path),
        ["video1.mp4"],
        _clips(),
        video_joiner_cls=Joiner,
        audio_mixer_cls=Mixer,
        report_generator_cls=ReportGenerator,
        cancel_event=cancel_event,
    )

    assert result["cancelled"] is True
    assert result["stage"] == "merge_audio"
    assert Joiner.calls == 1
    assert Mixer.calls == 0
    assert ReportGenerator.calls == 0


def test_merge_cancel_after_audio_skips_report(tmp_path):
    _reset_fakes()
    cancel_event = CancelEvent()
    Mixer.cancel_event = cancel_event

    result = merge_clips_to_highlight(
        _config(tmp_path),
        ["video1.mp4"],
        _clips(),
        video_joiner_cls=Joiner,
        audio_mixer_cls=Mixer,
        report_generator_cls=ReportGenerator,
        cancel_event=cancel_event,
    )

    assert result["cancelled"] is True
    assert result["stage"] == "merge_report"
    assert Joiner.calls == 1
    assert Mixer.calls == 1
    assert ReportGenerator.calls == 0
