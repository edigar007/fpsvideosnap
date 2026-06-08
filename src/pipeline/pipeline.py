import os
import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

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
from src.pipeline.context import PipelineContext
from src.pipeline.stages.detection_stage import run_detection_stage
from src.config.fingerprint import (
    compute_config_fingerprints,
    compute_path_hash,
    get_earliest_invalidation_stage,
    get_stages_to_invalidate,
    get_unique_output_path,
)

logger = get_logger(__name__)

# Checkpoint format version for future compatibility
CHECKPOINT_VERSION = 2
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

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.stages: Dict[str, PipelineStage] = {}
        self.results: Dict[str, Any] = {}
        self.checkpoint_file = ""
        
        # Incremental rebuild support
        self._video_path: str = ""
        self._fingerprints: Dict[str, str] = {}
        self._loaded_fingerprints: Dict[str, str] = {}
        
        # Initialize stages
        stage_names = [
            "metadata", "frames", "detection", "clips", 
            "join", "audio", "report", "history", "cleanup"
        ]
        for name in stage_names:
            self.stages[name] = PipelineStage(name=name)

        # Components
        self.temp_dir = temp_manager.create_temp_dir("pipeline_")
        self.video_info: Optional[VideoInfo] = None
        self.model_manager = ModelManager(config.get("ai", {}).get("model_dir", "models"))

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
        if not self.checkpoint_file:
            return
        
        checkpoint_data = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "video_path": self._video_path,
            "fingerprints": self._fingerprints,
            "stages": {name: {"status": s.status.value, "duration": s.duration} for name, s in self.stages.items()},
            "results": self.results,
            "temp_dir": self.temp_dir,
            "timestamp": datetime.now().isoformat()
        }
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def _load_checkpoint(self, checkpoint_path: str, current_video_path: str) -> bool:
        """
        Load checkpoint data and validate against current video path.
        
        Returns True if checkpoint was loaded successfully and is valid for resume.
        Returns False if checkpoint doesn't exist, is invalid, or belongs to different video.
        """
        if not os.path.exists(checkpoint_path):
            return False
            
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check checkpoint version - old format without version should be treated as fresh run
            checkpoint_version = data.get("checkpoint_version", 1)
            if checkpoint_version < CHECKPOINT_VERSION:
                logger.info(
                    f"Checkpoint version mismatch (v{checkpoint_version} < v{CHECKPOINT_VERSION}), "
                    "starting fresh run"
                )
                return False
            
            # Validate video_path matches - different video should not resume
            saved_video_path = data.get("video_path", "")
            if saved_video_path and saved_video_path != current_video_path:
                logger.info("Checkpoint belongs to different video, starting fresh run")
                return False
                
            # Load stages
            for name, s_data in data.get("stages", {}).items():
                if name in self.stages:
                    self.stages[name].status = StageStatus(s_data["status"])
                    self.stages[name].duration = s_data["duration"]
            
            self.results = data.get("results", {})
            self.temp_dir = data.get("temp_dir", self.temp_dir)
            self._loaded_fingerprints = data.get("fingerprints", {})
            
            logger.info(f"Resumed from checkpoint: {checkpoint_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return False

    def _invalidate_from_stage(self, from_stage: str):
        """
        Invalidate a stage and all subsequent stages due to config change.
        
        This resets the stage status to PENDING, clears associated results,
        and removes old artifacts from disk so they will be re-generated.
        """
        import shutil
        
        stages_to_invalidate = get_stages_to_invalidate(from_stage)
        
        for stage_name in stages_to_invalidate:
            if stage_name in self.stages:
                self.stages[stage_name].status = StageStatus.PENDING
                self.stages[stage_name].duration = 0
                self.stages[stage_name].error = None
                logger.debug(f"Invalidated stage: {stage_name}")
        
        # Clear results for invalidated stages
        result_keys_to_clear = {
            "frames": ["frames"],
            "detection": ["events", "detection_json"],
            "clips": ["clips"],
            "join": ["joined_video"],
            "audio": ["final_video"],
            "report": ["report_path"],
        }
        
        for stage_name in stages_to_invalidate:
            for key in result_keys_to_clear.get(stage_name, []):
                if key in self.results:
                    del self.results[key]
                    logger.debug(f"Cleared result key: {key}")
        
        # Clean up artifact directories/files on disk
        if self.temp_dir:
            artifact_paths = {
                "frames": os.path.join(self.temp_dir, "frames"),
                "clips": os.path.join(self.temp_dir, "clips"),
                "join": os.path.join(self.temp_dir, "joined_no_audio.mp4"),
            }
            
            for stage_name in stages_to_invalidate:
                path = artifact_paths.get(stage_name)
                if path and os.path.exists(path):
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                            logger.debug(f"Removed artifact directory: {path}")
                        else:
                            os.remove(path)
                            logger.debug(f"Removed artifact file: {path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove artifact {path}: {e}")

    def _build_context(self, video_path: str, base_name: str) -> PipelineContext:
        return PipelineContext(
            config=self.config,
            video_path=video_path,
            base_name=base_name,
            temp_dir=self.temp_dir,
            checkpoint_file=self.checkpoint_file,
            results=self.results,
        )

    def _stage_completed(self, stage_name: str, resume_completed: bool) -> bool:
        return resume_completed and self.stages[stage_name].status == StageStatus.SUCCESS

    def _run_metadata_stage(self, context: PipelineContext, resume_completed: bool) -> None:
        if self._stage_completed("metadata", resume_completed):
            return

        self._update_stage("metadata", StageStatus.RUNNING)
        self.video_info = VideoInfo(context.video_path)
        self.results["video_info"] = {
            "path": context.video_path,
            "duration": self.video_info.duration,
            "resolution": f"{self.video_info.width}x{self.video_info.height}",
            "fps": self.video_info.fps,
        }
        self._update_stage("metadata", StageStatus.SUCCESS)

    def _run_frames_stage(self, context: PipelineContext, resume_completed: bool) -> List[str]:
        if self._stage_completed("frames", resume_completed):
            return self.results.get("frames", [])

        frame_dir = os.path.join(self.temp_dir, "frames")
        self._update_stage("frames", StageStatus.RUNNING)
        profiler.start("stage_frame_extraction")
        extractor = FrameExtractor(
            ffmpeg_path=self.config.get("video", {}).get("ffmpeg_path", "ffmpeg"),
            hwaccel=self.config.get("video", {}).get("hwaccel", "cuda"),
            mode=self.config.get("video", {}).get("frame_extraction_mode", "bulk"),
        )
        interval = self.config.get("video", {}).get("frame_interval_ms", 1000)
        frames = extractor.extract_frames(context.video_path, frame_dir, interval_ms=interval)
        self.results["frames"] = frames
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
            return self.results.get("events", [])

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
        self.results["events"] = detected_events
        self.results["detection_json"] = detection_result.detection_json_path
        if detection_result.debug_video_path:
            self.results["debug_video"] = detection_result.debug_video_path
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
            return self.results.get("clips", [])

        clip_dir = os.path.join(self.temp_dir, "clips")
        if not detected_events:
            logger.warning(no_events_message)
            self._update_stage("clips", StageStatus.SKIPPED)
            self.results["clips"] = []
            return []

        self._update_stage("clips", StageStatus.RUNNING)
        clip_extractor = ClipExtractor(self.config)

        detection_json = self.results.get("detection_json")
        if detection_json and os.path.exists(detection_json):
            extracted_clips = clip_extractor.extract_from_json(context.video_path, detection_json, clip_dir)
        else:
            logger.warning("Detection JSON not found, falling back to in-memory events")
            extracted_clips = clip_extractor.extract_clips(context.video_path, detected_events, clip_dir)

        self.results["clips"] = extracted_clips
        self._update_stage("clips", StageStatus.SUCCESS)
        return extracted_clips

    def _run_to_stage(
        self,
        context: PipelineContext,
        target_stage: str,
        progress_desc: str,
        no_events_message: str,
        resume_completed: bool = True,
    ) -> Any:
        self._run_metadata_stage(context, resume_completed)
        if target_stage == "metadata":
            return self.results.get("video_info", {})

        frames = self._run_frames_stage(context, resume_completed)
        if target_stage == "frames":
            return frames

        detected_events = self._run_detection_stage(context, frames, progress_desc, resume_completed)
        if target_stage == "detection":
            return detected_events

        extracted_clips = self._run_clips_stage(context, detected_events, no_events_message, resume_completed)
        if target_stage == "clips":
            return extracted_clips

        raise ValueError(f"Unknown target stage: {target_stage}")

    def run(self, video_path: str, checkpoint_path: str = None) -> bool:
        """
        Runs the full pipeline for a single video.
        """
        video_path = os.path.abspath(video_path)
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        
        # Store video path for checkpoint
        self._video_path = video_path
        
        # Compute current config fingerprints
        self._fingerprints = compute_config_fingerprints(self.config)
        
        # Ensure temp directory exists for checkpoints
        checkpoint_dir = self.config.get("global", {}).get("temp_dir", "temp")
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir, exist_ok=True)
        
        # Include path hash in checkpoint filename to avoid conflicts with same-named videos
        path_hash = compute_path_hash(video_path)
        self.checkpoint_file = checkpoint_path or os.path.join(
            checkpoint_dir, f"checkpoint_{base_name}_{path_hash}.json"
        )
        
        # Try to resume if checkpoint exists
        checkpoint_loaded = False
        if os.path.exists(self.checkpoint_file):
            checkpoint_loaded = self._load_checkpoint(self.checkpoint_file, video_path)
            
            # If checkpoint loaded, check for config changes and invalidate if needed
            if checkpoint_loaded and self._loaded_fingerprints:
                invalidate_from = get_earliest_invalidation_stage(
                    self._loaded_fingerprints, self._fingerprints
                )
                if invalidate_from:
                    logger.info(f"Config changed, invalidating from stage: {invalidate_from}")
                    self._invalidate_from_stage(invalidate_from)

        try:
            context = self._build_context(video_path, base_name)
            extracted_clips = self._run_to_stage(
                context,
                target_stage="clips",
                progress_desc="Detecting Kills",
                no_events_message="No kills detected. Skipping clip extraction.",
                resume_completed=True,
            )

            # 5. Join Clips
            joined_video = None
            if self.stages["join"].status != StageStatus.SUCCESS:
                if not extracted_clips:
                    self._update_stage("join", StageStatus.SKIPPED)
                else:
                    self._update_stage("join", StageStatus.RUNNING)
                    joined_video = os.path.join(self.temp_dir, "joined_no_audio.mp4")
                    joiner = VideoJoiner(self.config)
                    
                    # TASK-002: Validate clip paths and handle missing files
                    clip_paths = []
                    for clip in extracted_clips:
                        # Read 'path' field, fallback to 'output_path' for backward compatibility
                        clip_path = clip.get("path") or clip.get("output_path")
                        if not clip_path:
                            logger.error(f"Clip {clip.get('id', 'unknown')} missing path field")
                            raise RuntimeError("Clip metadata missing path field")
                        
                        if not os.path.exists(clip_path):
                            logger.error(f"Clip file not found: {clip_path}")
                            raise FileNotFoundError(f"Clip file not found: {clip_path}")
                        
                        clip_paths.append(clip_path)
                    
                    if joiner.join_clips(clip_paths, joined_video):
                        self.results["joined_video"] = joined_video
                        self._update_stage("join", StageStatus.SUCCESS)
                    else:
                        raise RuntimeError("Failed to join clips.")
            else:
                joined_video = self.results.get("joined_video")

            # 6. Audio Mixing
            final_video_name = f"{base_name}_highlights.mp4"
            output_dir = self.config.get("global", {}).get("output_dir", "output")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            base_final_path = os.path.join(output_dir, final_video_name)
            
            # Check if final_video exists - if not, we need to rebuild
            final_video_exists = os.path.exists(base_final_path)
            need_audio_mixing = (self.stages["audio"].status != StageStatus.SUCCESS) or not final_video_exists
            
            # Determine final output path: use unique path only when actually re-running audio
            if need_audio_mixing and final_video_exists:
                # Config changed or rebuild needed, but file exists -> use suffix _1, _2, etc.
                final_video_path = get_unique_output_path(base_final_path)
                logger.info(f"Output file exists, using unique path: {final_video_path}")
            else:
                final_video_path = base_final_path
            
            if need_audio_mixing:
                # Chain fallback: if joined_video is missing, try to rebuild from earlier stages
                if not joined_video or not os.path.exists(joined_video):
                    # Check if we can rebuild join stage
                    if extracted_clips:
                        logger.info("Joined video missing, re-running join stage for chain fallback")
                        self.stages["join"].status = StageStatus.PENDING
                        # Re-run join
                        self._update_stage("join", StageStatus.RUNNING)
                        joined_video = os.path.join(self.temp_dir, "joined_no_audio.mp4")
                        joiner = VideoJoiner(self.config)
                        clip_paths = []
                        for clip in extracted_clips:
                            clip_path = clip.get("path") or clip.get("output_path")
                            if clip_path and os.path.exists(clip_path):
                                clip_paths.append(clip_path)
                        
                        if clip_paths and joiner.join_clips(clip_paths, joined_video):
                            self.results["joined_video"] = joined_video
                            self._update_stage("join", StageStatus.SUCCESS)
                        else:
                            logger.warning("Chain fallback failed: could not join clips")
                            self._update_stage("audio", StageStatus.SKIPPED)
                            joined_video = None
                    else:
                        logger.warning("Cannot rebuild: no clips available for chain fallback")
                        self._update_stage("audio", StageStatus.SKIPPED)
                        
                if joined_video and os.path.exists(joined_video):
                    self._update_stage("audio", StageStatus.RUNNING)
                    mixer = AudioMixer(self.config)
                    result_path = mixer.mix_audio(joined_video, final_video_path)
                    # If mixer skipped (no music), it returns joined_video
                    if result_path == joined_video:
                        import shutil
                        shutil.copy2(joined_video, final_video_path)
                    
                    self.results["final_video"] = final_video_path
                    self._update_stage("audio", StageStatus.SUCCESS)
            else:
                # Resume from checkpoint, final_video already exists
                self.results["final_video"] = final_video_path

            # 7. Report Generation
            if self.stages["report"].status != StageStatus.SUCCESS:
                self._update_stage("report", StageStatus.RUNNING)
                report_gen = ReportGenerator(output_dir)
                report_path = report_gen.generate(
                    self.results.get("video_info", {}),
                    self.results.get("clips", []),
                    self.config
                )
                self.results["report_path"] = report_path
                self._update_stage("report", StageStatus.SUCCESS)

            # 8. History
            if self.stages["history"].status != StageStatus.SUCCESS:
                self._update_stage("history", StageStatus.RUNNING)
                history_dir = self.config.get("global", {}).get("history_dir", "history")
                history_mgr = HistoryManager(history_dir)
                history_mgr.save_run(self.config, self.results.get("clips", []))
                self._update_stage("history", StageStatus.SUCCESS)

            # 9. Cleanup
            if self.stages["cleanup"].status != StageStatus.SUCCESS:
                self._update_stage("cleanup", StageStatus.RUNNING)
                keep_intermediates = bool(self.config.get("global", {}).get("debug", False)) or bool(
                    self.config.get("video", {}).get("join_fix", {}).get("keep_intermediates", False)
                )
                if not keep_intermediates:
                    temp_manager.clean_all()
                if os.path.exists(self.checkpoint_file):
                    try:
                        os.remove(self.checkpoint_file)
                    except FileNotFoundError:
                        pass
                self._update_stage("cleanup", StageStatus.SUCCESS)

            # 10. 打印性能分析报告
            profiler.print_summary()
            
            # 保存性能分析数据到文件
            history_dir = self.config.get("global", {}).get("history_dir", "history")
            run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            perf_file = os.path.join(history_dir, f"performance_{run_timestamp}.json")
            try:
                os.makedirs(history_dir, exist_ok=True)
                profiler.save_to_file(perf_file)
            except OSError as e:
                logger.warning(f"Failed to save performance profile: {e}")

            logger.info(f"[bold green]Pipeline completed successfully for {video_path}[/bold green]")
            return True

        except Exception as e:
            logger.error(f"Pipeline failed at stage {self._get_current_stage()}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # 即使失败也打印性能报告（帮助调试）
            profiler.print_summary()
            
            return False

    def run_until_clips(self, video_path: str) -> List[Dict[str, Any]]:
        """
        Runs the pipeline only until clips extraction (skips join/audio/report).
        Used for multi-video merge mode where clips are collected and joined later.
        
        Returns:
            List of extracted clip metadata dicts with 'path' field.
        """
        video_path = os.path.abspath(video_path)
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        
        # Ensure temp directory exists
        checkpoint_dir = self.config.get("global", {}).get("temp_dir", "temp")
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir, exist_ok=True)
        
        self.checkpoint_file = os.path.join(checkpoint_dir, f"checkpoint_{base_name}.json")
        
        try:
            context = self._build_context(video_path, base_name)
            extracted_clips = self._run_to_stage(
                context,
                target_stage="clips",
                progress_desc=f"Detecting [{base_name}]",
                no_events_message=f"{base_name}: No kills detected. Skipping clip extraction.",
                resume_completed=False,
            )
            
            logger.info(f"[bold green]{base_name}:[/bold green] Extracted {len(extracted_clips)} clips")
            return extracted_clips

        except Exception as e:
            logger.error(f"Pipeline failed for {video_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

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
