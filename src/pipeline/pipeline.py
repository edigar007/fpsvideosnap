import os
import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
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
from src.ai.timestamp_recorder import TimestampRecorder
from src.clip.clip_extractor import ClipExtractor
from src.video.video_joiner import VideoJoiner
from src.audio.audio_mixer import AudioMixer
from src.report.report_generator import ReportGenerator
from src.history.history_manager import HistoryManager
from src.debug.detection_debugger import DetectionDebugger
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
            logger.info(f"--- Stage {name.upper()} finished: [{color}]{status.value}[/{color}] ({stage.duration:.2f}s) ---")
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
                logger.info(f"Checkpoint version mismatch (v{checkpoint_version} < v{CHECKPOINT_VERSION}), starting fresh run")
                return False
            
            # Validate video_path matches - different video should not resume
            saved_video_path = data.get("video_path", "")
            if saved_video_path and saved_video_path != current_video_path:
                logger.info(f"Checkpoint belongs to different video, starting fresh run")
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
            # 1. Metadata
            if self.stages["metadata"].status != StageStatus.SUCCESS:
                self._update_stage("metadata", StageStatus.RUNNING)
                self.video_info = VideoInfo(video_path)
                self.results["video_info"] = {
                    "path": video_path,
                    "duration": self.video_info.duration,
                    "resolution": f"{self.video_info.width}x{self.video_info.height}",
                    "fps": self.video_info.fps
                }
                self._update_stage("metadata", StageStatus.SUCCESS)
            
            # 2. Frame Extraction
            frame_dir = os.path.join(self.temp_dir, "frames")
            if self.stages["frames"].status != StageStatus.SUCCESS:
                self._update_stage("frames", StageStatus.RUNNING)
                profiler.start('stage_frame_extraction')
                extractor = FrameExtractor(
                    ffmpeg_path=self.config.get("video", {}).get("ffmpeg_path", "ffmpeg"),
                    hwaccel=self.config.get("video", {}).get("hwaccel", "cuda"),
                    mode=self.config.get("video", {}).get("frame_extraction_mode", "bulk"),
                )
                interval = self.config.get("video", {}).get("frame_interval_ms", 1000)
                frames = extractor.extract_frames(video_path, frame_dir, interval_ms=interval)
                self.results["frames"] = frames
                profiler.end('stage_frame_extraction')
                self._update_stage("frames", StageStatus.SUCCESS)
            else:
                frames = self.results.get("frames", [])

            # 3. Kill Detection
            if self.stages["detection"].status != StageStatus.SUCCESS:
                self._update_stage("detection", StageStatus.RUNNING)
                profiler.start('stage_detection_total')
                
                # Setup AI components
                profiler.start('stage_detection_setup')
                model_dir = self.config.get("ai", {}).get("model_dir", "models")
                model_path = os.path.join(model_dir, "yolov8n.pt")
                self.model_manager.model_path = model_path
                yolo_model = self.model_manager.load_model()
                
                batch_size = self.config.get("ai", {}).get("batch_size", 16)
                yolo_detector = YoloDetector(
                    yolo_model, 
                    batch_size=batch_size
                )
                opencv_matcher = OpenCVMatcher(self.config)
                
                # TASK-005: Load templates before batch processing
                template_dir = self.config.get("detection", {}).get("template_dir", "")
                if template_dir and os.path.exists(template_dir):
                    opencv_matcher.load_templates(template_dir)
                    logger.info(f"Loaded {len(opencv_matcher.templates)} templates from {template_dir}")
                
                kill_detector = KillDetector(yolo_detector, opencv_matcher, self.config)
                profiler.end('stage_detection_setup')
                
                # Debug: Log detection configuration
                detection_cfg = self.config.get('detection', {})
                logger.debug(f"KillDetector initialized with:")
                logger.debug(f"  Confidence threshold: {detection_cfg.get('confidence_threshold', 0.5)}")
                logger.debug(f"  ROI: {detection_cfg.get('killfeed_roi', [0, 0, 1, 1])}")
                logger.debug(f"  Colors: {list(detection_cfg.get('colors', {}).keys())}")
                logger.debug(f"  OCR enabled: {detection_cfg.get('ocr', {}).get('enabled', False)}")
                logger.debug(f"  Prefilter threshold: {detection_cfg.get('prefilter', {}).get('color_threshold', 0.01)}")
                
                # TASK-004: Setup TimestampRecorder to persist detection events
                history_dir = self.config.get("global", {}).get("history_dir", "history")
                run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                run_dir = os.path.join(history_dir, f"run_{run_timestamp}")
                os.makedirs(run_dir, exist_ok=True)
                
                detection_json_path = os.path.join(run_dir, "detections.json")
                timestamp_recorder = TimestampRecorder(detection_json_path)
                
                detected_events = []
                import cv2
                
                pbar = create_progress_bar(total=len(frames), desc="Detecting Kills")
                
                # Process in large chunks to avoid OOM but utilize batching
                # Chunk size should be a multiple of batch_size
                # 优化：增加 chunk_size 以减少批次数量，提高 GPU 利用率
                chunk_size = 256 
                
                profiler.start('stage_detection_processing')
                for i in range(0, len(frames), chunk_size):
                    chunk_paths = frames[i:i + chunk_size]
                    chunk_frames = []
                    chunk_timestamps = []
                    
                    # 读取帧计时
                    profiler.start('stage_detection_read_frames')
                    for frame_path in chunk_paths:
                        frame = cv2.imread(frame_path)
                        if frame is not None:
                            chunk_frames.append(frame)
                            try:
                                ts_str = os.path.basename(frame_path).split('_')[1].split('.')[0]
                                chunk_timestamps.append(int(ts_str))
                            except:
                                chunk_timestamps.append(0)
                        else:
                            logger.warning(f"Failed to read frame: {frame_path}")
                    profiler.end('stage_detection_read_frames')

                    if chunk_frames:
                        batch_events = kill_detector.process_video_batch(chunk_frames, chunk_timestamps)
                        detected_events.extend(batch_events)
                        
                        # Debug: Log detection results for this batch
                        if len(batch_events) > 0:
                            logger.debug(f"Batch {i//chunk_size + 1}: Detected {len(batch_events)} events")
                            for event in batch_events[:3]:  # Log first 3 events
                                logger.debug(f"  Event: ts={event.get('timestamp_ms')}ms, conf={event.get('confidence', 0):.3f}")
                        
                        # TASK-004: Stream each event to TimestampRecorder
                        profiler.start('stage_detection_record_events')
                        for event in batch_events:
                            timestamp_recorder.record_event(
                                timestamp_ms=event.get("timestamp_ms", 0),
                                event_type="kill",
                                confidence=event.get("confidence", 0.0),
                                meta={
                                    "signals": event.get("signals", {}),
                                    "frame_path": event.get("frame_path", "")
                                }
                            )
                        profiler.end('stage_detection_record_events')
                    
                    pbar.update(len(chunk_paths))
                
                profiler.end('stage_detection_processing')    
                pbar.close()
                
                # TASK-004: Save detection events to JSON
                profiler.start('stage_detection_save_results')
                timestamp_recorder.save()
                logger.info(f"Detection events saved to {detection_json_path}")
                profiler.end('stage_detection_save_results')
                
                profiler.end('stage_detection_total')
                
                # Debug: Log final detection statistics
                logger.info(f"[bold]Detection Summary:[/bold]")
                logger.info(f"  Total frames processed: {len(frames)}")
                logger.info(f"  Total events detected: {len(detected_events)}")
                if len(detected_events) > 0:
                    avg_conf = sum(e.get('confidence', 0) for e in detected_events) / len(detected_events)
                    logger.info(f"  Average confidence: {avg_conf:.3f}")
                    logger.info(f"  First event: ts={detected_events[0].get('timestamp_ms')}ms, conf={detected_events[0].get('confidence', 0):.3f}")
                    logger.info(f"  Last event: ts={detected_events[-1].get('timestamp_ms')}ms, conf={detected_events[-1].get('confidence', 0):.3f}")
                
                self.results["events"] = detected_events
                self.results["detection_json"] = detection_json_path
                self._update_stage("detection", StageStatus.SUCCESS)

                # --- Visual Debug Logic (Phase 5) ---
                if self.config.get("global", {}).get("debug_visual", False):
                    debug_viz_dir = os.path.join(self.temp_dir, "debug_viz")
                    os.makedirs(debug_viz_dir, exist_ok=True)
                    debugger = DetectionDebugger(self.config)
                    
                    # 1. Save frame-by-frame evidence for detected kills
                    for i, event in enumerate(detected_events):
                        ts = event.get("timestamp_ms", 0)
                        # We need the frame to save it. For now, we search frames by timestamp.
                        # This is a bit inefficient to reload, but keeps memory usage low.
                        for f_path in frames:
                            if f"_{ts}." in f_path:
                                frame = cv2.imread(f_path)
                                if frame is not None:
                                    debug_path = os.path.join(debug_viz_dir, f"kill_{ts}_debug.jpg")
                                    debugger.save_debug_frame(frame, event, debug_path)
                                break
                    
                    # 2. Generate full debug overlay video (Optional but requested)
                    debug_video_path = os.path.join(debug_viz_dir, "detection_debug.mp4")
                    debugger.generate_debug_overlay(video_path, detected_events, debug_video_path)
                    self.results["debug_video"] = debug_video_path
                    logger.info(f"Visual debug evidence saved to {debug_viz_dir}")

                    # 显式释放 OCR 资源（Windows 下可能包含子进程 PaddleOCR worker）
                    try:
                        if getattr(kill_detector, "ocr", None) is not None:
                            kill_detector.ocr.close()
                    except Exception:
                        pass
                # -----------------------------------
                
            else:
                detected_events = self.results.get("events", [])

            # 4. Clip Extraction
            clip_dir = os.path.join(self.temp_dir, "clips")
            extracted_clips = []
            if self.stages["clips"].status != StageStatus.SUCCESS:
                if not detected_events:
                    logger.warning("No kills detected. Skipping clip extraction.")
                    self._update_stage("clips", StageStatus.SKIPPED)
                    self.results["clips"] = []
                else:
                    self._update_stage("clips", StageStatus.RUNNING)
                    clip_extractor = ClipExtractor(self.config)
                    
                    # TASK-004: Extract clips from persisted JSON instead of in-memory events
                    detection_json = self.results.get("detection_json")
                    if detection_json and os.path.exists(detection_json):
                        extracted_clips = clip_extractor.extract_from_json(video_path, detection_json, clip_dir)
                    else:
                        # Fallback to in-memory events for backward compatibility
                        logger.warning("Detection JSON not found, falling back to in-memory events")
                        extracted_clips = clip_extractor.extract_clips(video_path, detected_events, clip_dir)
                    
                    self.results["clips"] = extracted_clips
                    self._update_stage("clips", StageStatus.SUCCESS)
            else:
                extracted_clips = self.results.get("clips", [])

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
                            raise RuntimeError(f"Clip metadata missing path field")
                        
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
                    os.remove(self.checkpoint_file)
                self._update_stage("cleanup", StageStatus.SUCCESS)

            # 10. 打印性能分析报告
            profiler.print_summary()
            
            # 保存性能分析数据到文件
            history_dir = self.config.get("global", {}).get("history_dir", "history")
            run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            perf_file = os.path.join(history_dir, f"performance_{run_timestamp}.json")
            profiler.save_to_file(perf_file)

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
            # 1. Metadata
            self._update_stage("metadata", StageStatus.RUNNING)
            self.video_info = VideoInfo(video_path)
            self.results["video_info"] = {
                "path": video_path,
                "duration": self.video_info.duration,
                "resolution": f"{self.video_info.width}x{self.video_info.height}",
                "fps": self.video_info.fps
            }
            self._update_stage("metadata", StageStatus.SUCCESS)
            
            # 2. Frame Extraction
            frame_dir = os.path.join(self.temp_dir, "frames")
            self._update_stage("frames", StageStatus.RUNNING)
            profiler.start('stage_frame_extraction')
            extractor = FrameExtractor(
                ffmpeg_path=self.config.get("video", {}).get("ffmpeg_path", "ffmpeg"),
                hwaccel=self.config.get("video", {}).get("hwaccel", "cuda"),
                mode=self.config.get("video", {}).get("frame_extraction_mode", "bulk"),
            )
            interval = self.config.get("video", {}).get("frame_interval_ms", 1000)
            frames = extractor.extract_frames(video_path, frame_dir, interval_ms=interval)
            self.results["frames"] = frames
            profiler.end('stage_frame_extraction')
            self._update_stage("frames", StageStatus.SUCCESS)

            # 3. Kill Detection
            self._update_stage("detection", StageStatus.RUNNING)
            profiler.start('stage_detection_total')
            
            # Setup AI components
            profiler.start('stage_detection_setup')
            model_dir = self.config.get("ai", {}).get("model_dir", "models")
            model_path = os.path.join(model_dir, "yolov8n.pt")
            self.model_manager.model_path = model_path
            yolo_model = self.model_manager.load_model()
            
            batch_size = self.config.get("ai", {}).get("batch_size", 16)
            yolo_detector = YoloDetector(yolo_model, batch_size=batch_size)
            opencv_matcher = OpenCVMatcher(self.config)
            
            template_dir = self.config.get("detection", {}).get("template_dir", "")
            if template_dir and os.path.exists(template_dir):
                opencv_matcher.load_templates(template_dir)
            
            kill_detector = KillDetector(yolo_detector, opencv_matcher, self.config)
            profiler.end('stage_detection_setup')
            
            # Setup TimestampRecorder
            history_dir = self.config.get("global", {}).get("history_dir", "history")
            run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_dir = os.path.join(history_dir, f"run_{run_timestamp}")
            os.makedirs(run_dir, exist_ok=True)
            
            detection_json_path = os.path.join(run_dir, "detections.json")
            timestamp_recorder = TimestampRecorder(detection_json_path)
            
            detected_events = []
            import cv2
            
            pbar = create_progress_bar(total=len(frames), desc=f"Detecting [{base_name}]")
            chunk_size = 256
            
            profiler.start('stage_detection_processing')
            for i in range(0, len(frames), chunk_size):
                chunk_paths = frames[i:i + chunk_size]
                chunk_frames = []
                chunk_timestamps = []
                
                profiler.start('stage_detection_read_frames')
                for frame_path in chunk_paths:
                    frame = cv2.imread(frame_path)
                    if frame is not None:
                        chunk_frames.append(frame)
                        try:
                            ts_str = os.path.basename(frame_path).split('_')[1].split('.')[0]
                            chunk_timestamps.append(int(ts_str))
                        except:
                            chunk_timestamps.append(0)
                profiler.end('stage_detection_read_frames')

                if chunk_frames:
                    batch_events = kill_detector.process_video_batch(chunk_frames, chunk_timestamps)
                    detected_events.extend(batch_events)
                    
                    profiler.start('stage_detection_record_events')
                    for event in batch_events:
                        timestamp_recorder.record_event(
                            timestamp_ms=event.get("timestamp_ms", 0),
                            event_type="kill",
                            confidence=event.get("confidence", 0.0),
                            meta={"signals": event.get("signals", {})}
                        )
                    profiler.end('stage_detection_record_events')
                
                pbar.update(len(chunk_paths))
            
            profiler.end('stage_detection_processing')
            pbar.close()
            
            timestamp_recorder.save()
            profiler.end('stage_detection_total')
            
            logger.info(f"[bold]{base_name}:[/bold] Detected {len(detected_events)} events")
            
            self.results["events"] = detected_events
            self.results["detection_json"] = detection_json_path
            self._update_stage("detection", StageStatus.SUCCESS)
            
            # Release OCR resources
            try:
                if getattr(kill_detector, "ocr", None) is not None:
                    kill_detector.ocr.close()
            except Exception:
                pass

            # 4. Clip Extraction
            clip_dir = os.path.join(self.temp_dir, "clips")
            extracted_clips = []
            if not detected_events:
                logger.warning(f"{base_name}: No kills detected. Skipping clip extraction.")
                self._update_stage("clips", StageStatus.SKIPPED)
                self.results["clips"] = []
            else:
                self._update_stage("clips", StageStatus.RUNNING)
                clip_extractor = ClipExtractor(self.config)
                
                detection_json = self.results.get("detection_json")
                if detection_json and os.path.exists(detection_json):
                    extracted_clips = clip_extractor.extract_from_json(video_path, detection_json, clip_dir)
                else:
                    extracted_clips = clip_extractor.extract_clips(video_path, detected_events, clip_dir)
                
                self.results["clips"] = extracted_clips
                self._update_stage("clips", StageStatus.SUCCESS)
            
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
            color = "green" if stage.status == StageStatus.SUCCESS else "red" if stage.status == StageStatus.FAILED else "yellow"
            summary += f"{name:<15} | [{color}]{stage.status.value:<10}[/{color}] | {stage.duration:>8.2f}s\n"
        return summary
