from typing import Any, List

from src.pipeline.results import FINAL_VIDEO, VIDEO_INFO


class PipelineRunner:
    """Execute pipeline plans while Pipeline owns concrete stage implementations."""

    def __init__(self, pipeline, clips_plan: List[str]):
        self.pipeline = pipeline
        self.clips_plan = clips_plan

    def run_front_plan(
        self,
        context,
        target_stage: str,
        progress_desc: str,
        no_events_message: str,
        resume_completed: bool = True,
    ) -> Any:
        self.pipeline._run_metadata_stage(context, resume_completed)
        if target_stage == "metadata":
            return self.pipeline.results.get(VIDEO_INFO, {})

        frames = self.pipeline._run_frames_stage(context, resume_completed)
        if target_stage == "frames":
            return frames

        detected_events = self.pipeline._run_detection_stage(context, frames, progress_desc, resume_completed)
        if target_stage == "detection":
            return detected_events

        extracted_clips = self.pipeline._run_clips_stage(
            context,
            detected_events,
            no_events_message,
            resume_completed,
        )
        if target_stage == "clips":
            return extracted_clips

        raise ValueError(f"Unknown target stage: {target_stage}")

    def run_tail_plan(self, context, extracted_clips, resume_completed: bool) -> None:
        joined_video = self.pipeline._run_join_plan_stage(context, extracted_clips, resume_completed)

        final_video = self.pipeline._run_audio_plan_stage(context, joined_video, resume_completed)
        if final_video is None and extracted_clips:
            self.pipeline.logger.info("Joined video missing, re-running join stage for chain fallback")
            self.pipeline.stages["join"].status = self.pipeline.stage_status_cls.PENDING
            joined_video = self.pipeline._run_join_plan_stage(context, extracted_clips, resume_completed=False)
            self.pipeline._run_audio_plan_stage(context, joined_video, resume_completed=False)

        if not self.pipeline._stage_completed("report", resume_completed):
            self.pipeline._run_report_stage(context)

        if not self.pipeline._stage_completed("history", resume_completed):
            self.pipeline._run_history_stage(context)

        if not self.pipeline._stage_completed("cleanup", resume_completed):
            self.pipeline._run_cleanup_stage(context)

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

        if target_stage == "clips":
            return extracted_clips

        self.run_tail_plan(context, extracted_clips, resume_completed)
        return self.pipeline.results.get(FINAL_VIDEO)

