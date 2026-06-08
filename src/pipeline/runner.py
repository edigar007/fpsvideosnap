from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.pipeline.results import FINAL_VIDEO, VIDEO_INFO


@dataclass
class PipelineStageContract:
    """Public stage execution contract consumed by PipelineRunner."""

    results: Dict[str, Any]
    logger: Any
    stage_completed: Callable[[str, bool], bool]
    mark_stage_pending: Callable[[str], None]
    run_metadata: Callable[[Any, bool], None]
    run_frames: Callable[[Any, bool], List[str]]
    run_detection: Callable[[Any, List[str], str, bool], List[Dict[str, Any]]]
    run_clips: Callable[[Any, List[Dict[str, Any]], str, bool], List[Dict[str, Any]]]
    run_join: Callable[[Any, List[Dict[str, Any]], bool], Optional[str]]
    run_audio: Callable[[Any, Optional[str], bool], Optional[str]]
    run_report: Callable[[Any], Any]
    run_history: Callable[[Any], Any]
    run_cleanup: Callable[[Any], Any]


class PipelineRunner:
    """Execute pipeline plans through a public stage contract."""

    def __init__(self, stages: PipelineStageContract, clips_plan: List[str]):
        self.stages = stages
        self.clips_plan = clips_plan

    def run_front_plan(
        self,
        context,
        target_stage: str,
        progress_desc: str,
        no_events_message: str,
        resume_completed: bool = True,
    ) -> Any:
        self.stages.run_metadata(context, resume_completed)
        if target_stage == "metadata":
            return self.stages.results.get(VIDEO_INFO, {})

        frames = self.stages.run_frames(context, resume_completed)
        if target_stage == "frames":
            return frames

        detected_events = self.stages.run_detection(context, frames, progress_desc, resume_completed)
        if target_stage == "detection":
            return detected_events

        extracted_clips = self.stages.run_clips(
            context,
            detected_events,
            no_events_message,
            resume_completed,
        )
        if target_stage == "clips":
            return extracted_clips

        raise ValueError(f"Unknown target stage: {target_stage}")

    def run_tail_plan(self, context, extracted_clips, resume_completed: bool) -> None:
        joined_video = self.stages.run_join(context, extracted_clips, resume_completed)

        final_video = self.stages.run_audio(context, joined_video, resume_completed)
        if final_video is None and extracted_clips:
            self.stages.logger.info("Joined video missing, re-running join stage for chain fallback")
            self.stages.mark_stage_pending("join")
            joined_video = self.stages.run_join(context, extracted_clips, False)
            self.stages.run_audio(context, joined_video, False)

        if not self.stages.stage_completed("report", resume_completed):
            self.stages.run_report(context)

        if not self.stages.stage_completed("history", resume_completed):
            self.stages.run_history(context)

        if not self.stages.stage_completed("cleanup", resume_completed):
            self.stages.run_cleanup(context)

    def run_plan(
        self,
        context,
        plan: List[str],
        progress_desc: str,
        no_events_message: str,
        resume_completed: bool,
    ) -> Any:
        target_stage = plan[-1]
        front_target = target_stage if target_stage in self.clips_plan else "clips"
        extracted_clips = self.run_front_plan(
            context,
            front_target,
            progress_desc,
            no_events_message,
            resume_completed=resume_completed,
        )

        if target_stage in self.clips_plan:
            return extracted_clips

        self.run_tail_plan(context, extracted_clips, resume_completed)
        return self.stages.results.get(FINAL_VIDEO)
