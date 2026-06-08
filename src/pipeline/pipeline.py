import os
import time
from typing import Callable, Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger
from src.utils.progress import create_progress_bar
from src.utils.temp_manager import temp_manager
from src.utils.performance_profiler import get_profiler
from src.video.video_info import VideoInfo
from src.video.frame_extractor import FrameExtractor
from src.ai.model_manager import ModelManager
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.kill_detector import KillDetector
from src.clip.clip_extractor import ClipExtractor
from src.video.video_joiner import VideoJoiner
from src.audio.audio_mixer import AudioMixer
from src.report.report_generator import ReportGenerator
from src.history.history_manager import HistoryManager
from src.pipeline.checkpoint import CheckpointData, CheckpointStore
from src.pipeline.context import PipelineContext
from src.pipeline.post_run import emit_performance_profile
from src.pipeline.results import (
    CLIPS,
    DEBUG_VIDEO,
    DETECTION_JSON,
    EVENTS,
    FINAL_VIDEO,
    FRAMES,
    JOINED_VIDEO,
    PipelineRunResult,
    REPORT_PATH,
    VIDEO_INFO,
)
from src.pipeline.stages.audio_stage import run_audio_stage
from src.pipeline.stages.base import StageResult
from src.pipeline.stages.cleanup_stage import run_cleanup_stage
from src.pipeline.stages.detection_stage import run_detection_stage
from src.pipeline.stages.history_stage import run_history_stage
from src.pipeline.stages.join_stage import run_join_stage
from src.pipeline.stages.report_stage import run_report_stage
from src.pipeline.runner import PipelineRunner, PipelineStageContract
from src.pipeline.stage_registry import ArtifactStore, StageRegistry
from src.config.fingerprint import (
    compute_config_fingerprints,
    compute_path_hash,
    get_earliest_invalidation_stage,
)
from src.config.settings import AppSettings

logger = get_logger(__name__)

# Checkpoint format version for future compatibility
CHECKPOINT_VERSION = 2
FULL_PLAN = ["metadata", "frames", "detection", "clips", "join", "audio", "report", "history", "cleanup"]
CLIPS_PLAN = ["metadata", "frames", "detection", "clips"]
profiler = get_profiler()

class StageStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

@dataclass
class PipelineStage:
    name: str
    status: StageStatus = StageStatus.PENDING
    start_time: float = 0
    end_time: float = 0
    duration: float = 0
    error: Optional[str] = None

class Pipeline:
    """
    Main orchestration class for the FPS Video Snap processing flow.
    """

    def __init__(self, config: Dict[str, Any], progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.config = config
        self.settings = AppSettings.from_config(config)
        self.progress_callback = progress_callback
        self.logger = logger
        self.stage_status_cls = StageStatus
        self.stages: Dict[str, PipelineStage] = {}
        self.results: Dict[str, Any] = {}
        self.checkpoint_file = ""
        
        # Incremental rebuild support
        self._video_path: str = ""
        self._fingerprints: Dict[str, str] = {}
        self._loaded_fingerprints: Dict[str, str] = {}
        self.stage_registry = StageRegistry()
        
        # Initialize stages
        for name in self.stage_registry.stage_names:
            self.stages[name] = PipelineStage(name=name)
        self.runner = PipelineRunner(self._build_stage_contract(), CLIPS_PLAN)

        # Components
        self.temp_dir = temp_manager.create_temp_dir("pipeline_")
        self.video_info: Optional[VideoInfo] = None
        self.model_manager = ModelManager(
            self.settings.detection.model_path,
            allow_model_download=self.settings.ai.allow_model_download,
        )
        self.checkpoint_store = CheckpointStore(CHECKPOINT_VERSION)

    def _build_stage_contract(self) -> PipelineStageContract:
        return PipelineStageContract(
            results=self.results,
            logger=self.logger,
            stage_completed=self._stage_completed,
            mark_stage_pending=self._mark_stage_pending,
            run_metadata=self._run_metadata_stage,
            run_frames=self._run_frames_stage,
            run_detection=self._run_detection_stage,
            run_clips=self._run_clips_stage,
            run_join=self._run_join_plan_stage,
            run_audio=self._run_audio_plan_stage,
            run_report=self._run_report_stage,
            run_history=self._run_history_stage,
            run_cleanup=self._run_cleanup_stage,
        )

    def _load_detection_templates(self, opencv_matcher: OpenCVMatcher) -> int:
        """
        Load templates from all supported detection config locations.
        Supports both detection.template_dir and detection.templates.*.path.
        """
        detection_cfg = self.config.get("detection", {})
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        loaded_count = opencv_matcher.load_templates_from_config(detection_cfg, project_root=project_root)
        logger.info(f"Loaded {len(opencv_matcher.templates)} templates for detection ({loaded_count} new)")
        return loaded_count
        
    def _update_stage(self, name: str, status: StageStatus, error: str = None):
        stage = self.stages[name]
        stage.status = status
        if status == StageStatus.RUNNING:
            stage.start_time = time.time()
            logger.info(f"--- Starting Stage: [bold cyan]{name.upper()}[/bold cyan] ---")
        elif status in [StageStatus.SUCCESS, StageStatus.FAILED, StageStatus.SKIPPED]:
            stage.end_time = time.time()
            stage.duration = stage.end_time - stage.start_time
            stage.error = error
            color = "green" if status == StageStatus.SUCCESS else "red" if status == StageStatus.FAILED else "yellow"
            logger.info(
                f"--- Stage {name.upper()} finished: "
                f"[{color}]{status.value}[/{color}] ({stage.duration:.2f}s) ---"
            )
            self._save_checkpoint()

    def _save_checkpoint(self):
        self.checkpoint_store.save(
            self.checkpoint_file,
            self._video_path,
            self._fingerprints,
            self.stages,
            self.results,
            self.temp_dir,
        )

    def _load_checkpoint(self, checkpoint_path: str, current_video_path: str) -> bool:
        """
        Load checkpoint data and validate against current video path.
        
        Returns True if checkpoint was loaded successfully and is valid for resume.
        Returns False if checkpoint doesn't exist, is invalid, or belongs to different video.
        """
        checkpoint = self.checkpoint_store.load(checkpoint_path, current_video_path)
        if checkpoint is None:
            return False

        self._apply_checkpoint(checkpoint)
        invalid_stage = self.checkpoint_store.get_invalid_stage(checkpoint)
        if invalid_stage:
            logger.info(f"Checkpoint artifacts missing or invalid, invalidating from stage: {invalid_stage}")
            self._invalidate_from_stage(invalid_stage)

        logger.info(f"Resumed from checkpoint: {checkpoint_path}")
        return True

    def _apply_checkpoint(self, checkpoint: CheckpointData) -> None:
        for name, s_data in checkpoint.stages.items():
            if name in self.stages:
                self.stages[name].status = StageStatus(s_data["status"])
                self.stages[name].duration = s_data["duration"]

        self.results = checkpoint.results
        self.temp_dir = checkpoint.temp_dir or self.temp_dir
        self._loaded_fingerprints = checkpoint.fingerprints

    def _invalidate_from_stage(self, from_stage: str):
        """
        Invalidate a stage and all subsequent stages due to config change.
        
        This resets the stage status to PENDING, clears associated results,
        and removes old artifacts from disk so they will be re-generated.
        """
        stages_to_invalidate = self.stage_registry.stages_to_invalidate(from_stage)
        
        for stage_name in stages_to_invalidate:
            if stage_name in self.stages:
                self.stages[stage_name].status = StageStatus.PENDING
                self.stages[stage_name].duration = 0
                self.stages[stage_name].error = None
                logger.debug(f"Invalidated stage: {stage_name}")
        
        for key in self.stage_registry.result_keys_to_clear(stages_to_invalidate):
            if key in self.results:
                del self.results[key]
                logger.debug(f"Cleared result key: {key}")
        
        ArtifactStore(self.temp_dir).remove_stage_artifacts(stages_to_invalidate)

    def _build_context(self, video_path: str, base_name: str) -> PipelineContext:
        return PipelineContext(
            config=self.config,
            video_path=video_path,
            base_name=base_name,
            temp_dir=self.temp_dir,
            checkpoint_file=self.checkpoint_file,
            results=self.results,
            progress_callback=self.progress_callback,
        )

    def _prepare_run(self, video_path: str, checkpoint_path: str = None) -> Tuple[str, str, bool]:
        video_path = os.path.abspath(video_path)
        base_name = os.path.splitext(os.path.basename(video_path))[0]

        self._video_path = video_path
        self._fingerprints = compute_config_fingerprints(self.config)

        checkpoint_dir = self.config.get("global", {}).get("temp_dir", "temp")
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir, exist_ok=True)

        path_hash = compute_path_hash(video_path)
        self.checkpoint_file = checkpoint_path or os.path.join(
            checkpoint_dir, f"checkpoint_{base_name}_{path_hash}.json"
        )

        checkpoint_loaded = False
        self._loaded_fingerprints = {}
        if os.path.exists(self.checkpoint_file):
            checkpoint_loaded = self._load_checkpoint(self.checkpoint_file, video_path)

            if checkpoint_loaded and self._loaded_fingerprints:
                invalidate_from = get_earliest_invalidation_stage(
                    self._loaded_fingerprints, self._fingerprints
                )
                if invalidate_from:
                    logger.info(f"Config changed, invalidating from stage: {invalidate_from}")
                    self._invalidate_from_stage(invalidate_from)

        return video_path, base_name, checkpoint_loaded

    def _build_run_result(
        self,
        success: bool,
        mode: str,
        video_path: str,
        error: Optional[str] = None,
        failed_stage: Optional[str] = None,
    ) -> PipelineRunResult:
        return PipelineRunResult(
            success=success,
            mode=mode,
            video_path=video_path,
            clips=self.results.get(CLIPS, []),
            final_video=self.results.get(FINAL_VIDEO),
            report_path=self.results.get(REPORT_PATH),
            failed_stage=failed_stage,
            error=error,
        )

    def _stage_completed(self, stage_name: str, resume_completed: bool) -> bool:
        return resume_completed and self.stages[stage_name].status == StageStatus.SUCCESS

    def _mark_stage_pending(self, stage_name: str) -> None:
        self.stages[stage_name].status = StageStatus.PENDING

    def _run_metadata_stage(self, context: PipelineContext, resume_completed: bool) -> None:
        if self._stage_completed("metadata", resume_completed):
            return

        self._update_stage("metadata", StageStatus.RUNNING)
        self.video_info = VideoInfo(
            context.video_path,
            ffprobe_path=self.settings.video.ffprobe_path,
        )
        self.results[VIDEO_INFO] = {
            "path": context.video_path,
            "duration": self.video_info.duration,
            "resolution": f"{self.video_info.width}x{self.video_info.height}",
            "fps": self.video_info.fps,
        }
        self._update_stage("metadata", StageStatus.SUCCESS)

    def _run_frames_stage(self, context: PipelineContext, resume_completed: bool) -> List[str]:
        if self._stage_completed("frames", resume_completed):
            return self.results.get(FRAMES, [])

        frame_dir = os.path.join(self.temp_dir, "frames")
        self._update_stage("frames", StageStatus.RUNNING)
        profiler.start("stage_frame_extraction")
        extractor = FrameExtractor(
            ffmpeg_path=self.settings.video.ffmpeg_path,
            ffprobe_path=self.settings.video.ffprobe_path,
            hwaccel=self.settings.video.hwaccel,
            mode=self.settings.video.frame_extraction_mode,
        )
        interval = self.settings.video.frame_interval_ms
        frames = extractor.extract_frames(context.video_path, frame_dir, interval_ms=interval)
        self.results[FRAMES] = frames
        profiler.end("stage_frame_extraction")
        self._update_stage("frames", StageStatus.SUCCESS)
        return frames

    def _run_detection_stage(
        self,
        context: PipelineContext,
        frames: List[str],
        progress_desc: str,
        resume_completed: bool,
    ) -> List[Dict[str, Any]]:
        if self._stage_completed("detection", resume_completed):
            return self.results.get(EVENTS, [])

        self._update_stage("detection", StageStatus.RUNNING)
        detection_result = run_detection_stage(
            context,
            frames,
            self.model_manager,
            self._load_detection_templates,
            progress_desc=progress_desc,
            yolo_detector_cls=YoloDetector,
            opencv_matcher_cls=OpenCVMatcher,
            kill_detector_cls=KillDetector,
            progress_factory=create_progress_bar,
        )

        detected_events = detection_result.events
        self.results[EVENTS] = detected_events
        self.results[DETECTION_JSON] = detection_result.detection_json_path
        if detection_result.debug_video_path:
            self.results[DEBUG_VIDEO] = detection_result.debug_video_path
        self._update_stage("detection", StageStatus.SUCCESS)
        return detected_events

    def _run_clips_stage(
        self,
        context: PipelineContext,
        detected_events: List[Dict[str, Any]],
        no_events_message: str,
        resume_completed: bool,
    ) -> List[Dict[str, Any]]:
        if self._stage_completed("clips", resume_completed):
            return self.results.get(CLIPS, [])

        clip_dir = os.path.join(self.temp_dir, "clips")
        if not detected_events:
            logger.warning(no_events_message)
            self._update_stage("clips", StageStatus.SKIPPED)
            self.results[CLIPS] = []
            return []

        self._update_stage("clips", StageStatus.RUNNING)
        clip_extractor = ClipExtractor(self.config)

        detection_json = self.results.get(DETECTION_JSON)
        if detection_json and os.path.exists(detection_json):
            extracted_clips = clip_extractor.extract_from_json(context.video_path, detection_json, clip_dir)
        else:
            logger.warning("Detection JSON not found, falling back to in-memory events")
            extracted_clips = clip_extractor.extract_clips(context.video_path, detected_events, clip_dir)

        self.results[CLIPS] = extracted_clips
        self._update_stage("clips", StageStatus.SUCCESS)
        return extracted_clips

    def _run_stage_result(self, stage_name: str, func, *args, **kwargs) -> StageResult:
        self._update_stage(stage_name, StageStatus.RUNNING)
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self._update_stage(stage_name, StageStatus.FAILED, str(exc))
            raise

        self.results.update(result.values)
        self._update_stage(stage_name, StageStatus.SKIPPED if result.skipped else StageStatus.SUCCESS)
        return result

    def _run_join_plan_stage(
        self,
        context: PipelineContext,
        extracted_clips: List[Dict[str, Any]],
        resume_completed: bool,
    ) -> Optional[str]:
        if self._stage_completed("join", resume_completed):
            return self.results.get(JOINED_VIDEO)

        result = self._run_stage_result(
            "join",
            run_join_stage,
            context,
            extracted_clips,
            video_joiner_cls=VideoJoiner,
        )
        return result.values.get(JOINED_VIDEO)

    def _base_final_video_path(self, context: PipelineContext) -> str:
        output_dir = self.config.get("global", {}).get("output_dir", "output")
        return os.path.join(output_dir, f"{context.base_name}_highlights.mp4")

    def _run_audio_plan_stage(
        self,
        context: PipelineContext,
        joined_video: Optional[str],
        resume_completed: bool,
    ) -> Optional[str]:
        base_final_path = self._base_final_video_path(context)
        if self._stage_completed("audio", resume_completed):
            saved_final_path = self.results.get(FINAL_VIDEO)
            if saved_final_path and os.path.exists(saved_final_path):
                return saved_final_path
            if os.path.exists(base_final_path):
                self.results[FINAL_VIDEO] = base_final_path
                return base_final_path

        result = self._run_stage_result(
            "audio",
            run_audio_stage,
            context,
            joined_video,
            audio_mixer_cls=AudioMixer,
        )
        return result.values.get(FINAL_VIDEO)

    def _run_report_stage(self, context: PipelineContext) -> StageResult:
        return self._run_stage_result(
            "report",
            run_report_stage,
            context,
            report_generator_cls=ReportGenerator,
        )

    def _run_history_stage(self, context: PipelineContext) -> StageResult:
        return self._run_stage_result(
            "history",
            run_history_stage,
            context,
            history_manager_cls=HistoryManager,
        )

    def _run_cleanup_stage(self, context: PipelineContext) -> StageResult:
        return self._run_stage_result("cleanup", run_cleanup_stage, context)

    def _run_plan(
        self,
        context: PipelineContext,
        plan: List[str],
        progress_desc: str,
        no_events_message: str,
        resume_completed: bool,
    ) -> Any:
        return self.runner.run_plan(
            context,
            plan,
            progress_desc,
            no_events_message,
            resume_completed=resume_completed,
        )

    def _mark_current_stage_failed(self, error: str) -> None:
        failed_stage = self._get_current_stage()
        if failed_stage in self.stages and self.stages[failed_stage].status == StageStatus.RUNNING:
            self._update_stage(failed_stage, StageStatus.FAILED, error)

    def run_full_result(self, video_path: str, checkpoint_path: str = None) -> PipelineRunResult:
        """
        Runs the full pipeline for a single video and returns a structured result.
        """
        video_path, base_name, _checkpoint_loaded = self._prepare_run(video_path, checkpoint_path)

        try:
            context = self._build_context(video_path, base_name)
            self._run_plan(
                context,
                FULL_PLAN,
                progress_desc="Detecting Kills",
                no_events_message="No kills detected. Skipping clip extraction.",
                resume_completed=True,
            )

            emit_performance_profile(self.config)

            logger.info(f"[bold green]Pipeline completed successfully for {video_path}[/bold green]")
            return self._build_run_result(True, "full", video_path)

        except Exception as e:
            failed_stage = self._get_current_stage()
            self._mark_current_stage_failed(str(e))
            logger.error(f"Pipeline failed at stage {failed_stage}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            emit_performance_profile(self.config, save_to_history=False)
            
            return self._build_run_result(False, "full", video_path, error=str(e), failed_stage=failed_stage)

    def run(self, video_path: str, checkpoint_path: str = None) -> bool:
        """
        Runs the full pipeline for a single video.
        """
        return self.run_full_result(video_path, checkpoint_path).success

    def run_until_clips_result(self, video_path: str, checkpoint_path: str = None) -> PipelineRunResult:
        """
        Runs the pipeline only until clips extraction and returns a structured result.
        """
        video_path, base_name, _checkpoint_loaded = self._prepare_run(video_path, checkpoint_path)

        try:
            context = self._build_context(video_path, base_name)
            extracted_clips = self._run_plan(
                context,
                CLIPS_PLAN,
                progress_desc=f"Detecting [{base_name}]",
                no_events_message=f"{base_name}: No kills detected. Skipping clip extraction.",
                resume_completed=True,
            )
            
            logger.info(f"[bold green]{base_name}:[/bold green] Extracted {len(extracted_clips)} clips")
            return self._build_run_result(True, "clips", video_path)

        except Exception as e:
            failed_stage = self._get_current_stage()
            self._mark_current_stage_failed(str(e))
            logger.error(f"Pipeline failed for {video_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return self._build_run_result(False, "clips", video_path, error=str(e), failed_stage=failed_stage)

    def run_until_clips(self, video_path: str) -> List[Dict[str, Any]]:
        """
        Runs the pipeline only until clips extraction (skips join/audio/report).
        Used for multi-video merge mode where clips are collected and joined later.

        Returns:
            List of extracted clip metadata dicts with 'path' field.
        """
        return self.run_until_clips_result(video_path).clips

    def _get_current_stage(self) -> str:
        for name, stage in self.stages.items():
            if stage.status == StageStatus.RUNNING:
                return name
        return "unknown"

    def get_summary(self) -> str:
        summary = "\n[bold]Pipeline Execution Summary:[/bold]\n"
        summary += f"{'Stage':<15} | {'Status':<10} | {'Duration':<10}\n"
        summary += "-" * 45 + "\n"
        for name, stage in self.stages.items():
            color = (
                "green"
                if stage.status == StageStatus.SUCCESS
                else "red"
                if stage.status == StageStatus.FAILED
                else "yellow"
            )
            summary += f"{name:<15} | [{color}]{stage.status.value:<10}[/{color}] | {stage.duration:>8.2f}s\n"
        return summary
