from types import SimpleNamespace

from src.pipeline.results import CLIPS, FINAL_VIDEO, FRAMES, VIDEO_INFO
from src.pipeline.runner import PipelineRunner, PipelineStageContract


def _contract(results=None, completed=None):
    results = results or {}
    completed = completed or set()
    calls = []
    pending = []

    def stage_completed(stage_name, resume_completed):
        return resume_completed and stage_name in completed

    contract = PipelineStageContract(
        results=results,
        logger=SimpleNamespace(info=lambda message: calls.append(("log", message))),
        stage_completed=stage_completed,
        mark_stage_pending=lambda stage_name: pending.append(stage_name),
        run_metadata=lambda context, resume: calls.append(("metadata", resume)) or results.setdefault(VIDEO_INFO, {}),
        run_frames=lambda context, resume: calls.append(("frames", resume)) or results.setdefault(FRAMES, ["f1.jpg"]),
        run_detection=lambda context, frames, desc, resume: calls.append(("detection", frames, desc, resume)) or [],
        run_clips=lambda context, events, message, resume: calls.append(("clips", events, message, resume))
        or results.setdefault(CLIPS, [{"path": "clip.mp4"}]),
        run_join=lambda context, clips, resume: calls.append(("join", clips, resume)) or "joined.mp4",
        run_audio=lambda context, joined, resume: calls.append(("audio", joined, resume))
        or results.setdefault(FINAL_VIDEO, "final.mp4"),
        run_report=lambda context: calls.append(("report",)),
        run_history=lambda context: calls.append(("history",)),
        run_cleanup=lambda context: calls.append(("cleanup",)),
    )
    return contract, calls, pending


def test_runner_executes_front_plan_from_stage_contract():
    contract, calls, _pending = _contract()
    runner = PipelineRunner(contract, ["metadata", "frames", "detection", "clips"])

    result = runner.run_plan(
        context=object(),
        plan=["metadata", "frames", "detection"],
        progress_desc="Detecting",
        no_events_message="No events",
        resume_completed=True,
    )

    assert result == []
    assert [call[0] for call in calls] == ["metadata", "frames", "detection"]


def test_runner_executes_tail_plan_and_reads_final_result_from_contract():
    contract, calls, _pending = _contract(completed={"report", "history", "cleanup"})
    runner = PipelineRunner(contract, ["metadata", "frames", "detection", "clips"])

    result = runner.run_plan(
        context=object(),
        plan=["metadata", "frames", "detection", "clips", "join", "audio"],
        progress_desc="Detecting",
        no_events_message="No events",
        resume_completed=True,
    )

    assert result == "final.mp4"
    assert [call[0] for call in calls] == ["metadata", "frames", "detection", "clips", "join", "audio"]


def test_runner_reruns_join_when_audio_has_no_final_video():
    results = {}
    calls = []
    pending = []

    def run_audio(context, joined, resume):
        calls.append(("audio", joined, resume))
        if resume is False:
            results[FINAL_VIDEO] = "final.mp4"
            return "final.mp4"
        return None

    contract = PipelineStageContract(
        results=results,
        logger=SimpleNamespace(info=lambda message: calls.append(("log", message))),
        stage_completed=lambda stage_name, resume: False,
        mark_stage_pending=lambda stage_name: pending.append(stage_name),
        run_metadata=lambda context, resume: None,
        run_frames=lambda context, resume: [],
        run_detection=lambda context, frames, desc, resume: [],
        run_clips=lambda context, events, message, resume: [{"path": "clip.mp4"}],
        run_join=lambda context, clips, resume: calls.append(("join", resume)) or "joined.mp4",
        run_audio=run_audio,
        run_report=lambda context: calls.append(("report",)),
        run_history=lambda context: calls.append(("history",)),
        run_cleanup=lambda context: calls.append(("cleanup",)),
    )
    runner = PipelineRunner(contract, ["metadata", "frames", "detection", "clips"])

    result = runner.run_plan(
        context=object(),
        plan=["metadata", "frames", "detection", "clips", "join", "audio"],
        progress_desc="Detecting",
        no_events_message="No events",
        resume_completed=True,
    )

    assert result == "final.mp4"
    assert pending == ["join"]
    assert calls == [
        ("join", True),
        ("audio", "joined.mp4", True),
        ("log", "Joined video missing, re-running join stage for chain fallback"),
        ("join", False),
        ("audio", "joined.mp4", False),
        ("report",),
        ("history",),
        ("cleanup",),
    ]
