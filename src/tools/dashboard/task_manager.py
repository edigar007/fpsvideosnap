"""
Task Manager for handling video processing tasks.
Manages a single task at a time with process isolation.
Includes progress tracking for UI display.
"""
import os
import sys
import time
import threading
import multiprocessing
from queue import Queue, Empty
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field


class TaskStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Pipeline stages for progress display
PIPELINE_STAGES = [
    ("metadata", "视频元数据"),
    ("frames", "帧提取"),
    ("detection", "击杀检测"),
    ("clips", "片段提取"),
    ("join", "视频拼接"),
    ("audio", "音频混合"),
]


@dataclass
class ProgressInfo:
    """Progress information for a processing task."""
    current_video: str = ""
    current_video_index: int = 0
    total_videos: int = 0
    current_stage: str = ""
    stages: Dict[str, str] = field(default_factory=dict)  # stage_name -> status
    detection_progress: int = 0  # frames processed
    detection_total: int = 0  # total frames
    detected_kills: int = 0
    extracted_clips: int = 0


@dataclass
class TaskInfo:
    """Information about a processing task."""
    status: TaskStatus = TaskStatus.IDLE
    videos: List[str] = field(default_factory=list)
    game: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    progress: ProgressInfo = field(default_factory=ProgressInfo)


def _make_output_file(path: Optional[str], label: str, file_type: str) -> Optional[Dict[str, Any]]:
    """Build output file metadata for dashboard display."""
    if not path:
        return None

    abs_path = os.path.abspath(path)
    item = {
        "path": abs_path,
        "name": os.path.basename(abs_path),
        "label": label,
        "type": file_type,
        "exists": os.path.exists(abs_path),
    }

    if item["exists"]:
        try:
            item["size"] = os.path.getsize(abs_path)
        except OSError:
            pass

    return item


def _run_processing_task(
    videos: List[str],
    game: str,
    progress_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
    cancel_event: multiprocessing.Event
):
    """
    Worker function that runs in a separate process.
    Executes the video processing pipeline with progress reporting.
    """
    import logging
    from queue import Full
    
    def send_progress(progress_data: dict):
        """Send progress update to main process."""
        try:
            progress_queue.put_nowait({"type": "progress", **progress_data})
        except Full:
            pass
    
    def send_error(message: str):
        """Send error message to main process."""
        try:
            progress_queue.put_nowait({
                "type": "error",
                "message": message,
                "time": time.strftime("%H:%M:%S")
            })
        except Full:
            pass
    
    # Custom log handler to capture errors only
    class ErrorLogHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                try:
                    progress_queue.put_nowait({
                        "type": "error",
                        "level": record.levelname,
                        "message": self.format(record),
                        "time": time.strftime("%H:%M:%S")
                    })
                except Full:
                    pass
    
    # Configure logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []
    
    handler = ErrorLogHandler()
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(handler)
    
    fps_logger = logging.getLogger("fps_video_snap")
    fps_logger.setLevel(logging.DEBUG)
    fps_logger.handlers = []
    fps_logger.addHandler(handler)
    
    logger = logging.getLogger("fps_video_snap.dashboard.worker")
    
    try:
        # Initialize progress
        send_progress({
            "current_video": "",
            "current_video_index": 0,
            "total_videos": len(videos),
            "current_stage": "initializing",
            "stages": {s[0]: "pending" for s in PIPELINE_STAGES},
            "detection_progress": 0,
            "detection_total": 0,
            "detected_kills": 0,
            "extracted_clips": 0
        })
        
        if cancel_event.is_set():
            result_queue.put({"success": False, "error": "Cancelled"})
            return
        
        # Import processing modules
        from src.config.config_loader import get_config
        from src.pipeline.pipeline import Pipeline, StageStatus
        
        # Load configuration
        send_progress({"current_stage": "loading_config"})
        config = get_config(game_name=game)
        
        if cancel_event.is_set():
            result_queue.put({"success": False, "error": "Cancelled"})
            return
        
        # Process each video
        all_clips = []
        output_files = []
        
        for video_idx, video_path in enumerate(videos):
            if cancel_event.is_set():
                result_queue.put({"success": False, "error": "Cancelled"})
                return
            
            video_name = os.path.basename(video_path)
            
            # Reset stages for this video
            send_progress({
                "current_video": video_name,
                "current_video_index": video_idx + 1,
                "total_videos": len(videos),
                "current_stage": "metadata",
                "stages": {s[0]: "pending" for s in PIPELINE_STAGES},
                "detection_progress": 0,
                "detection_total": 0,
                "detected_kills": 0,
                "extracted_clips": 0
            })
            
            # Create pipeline for this video
            pipeline = Pipeline(config)
            
            # Start monitoring thread for this pipeline
            stop_monitor = threading.Event()
            
            def monitor_pipeline():
                last_frame_count = 0
                while not stop_monitor.is_set():
                    try:
                        # Get stage statuses
                        stage_statuses = {}
                        current_stage = ""
                        for stage_name, _ in PIPELINE_STAGES:
                            if stage_name in pipeline.stages:
                                status = pipeline.stages[stage_name].status
                                if status == StageStatus.SUCCESS:
                                    stage_statuses[stage_name] = "success"
                                elif status == StageStatus.RUNNING:
                                    stage_statuses[stage_name] = "running"
                                    current_stage = stage_name
                                elif status == StageStatus.FAILED:
                                    stage_statuses[stage_name] = "failed"
                                elif status == StageStatus.SKIPPED:
                                    stage_statuses[stage_name] = "skipped"
                                else:
                                    stage_statuses[stage_name] = "pending"
                        
                        # Get metrics from pipeline results
                        frames = pipeline.results.get("frames", [])
                        events = pipeline.results.get("events", [])
                        clips = pipeline.results.get("clips", [])
                        
                        detection_total = len(frames) if frames else 0
                        detection_progress = 0
                        
                        # Estimate detection progress
                        if current_stage == "detection" and detection_total > 0:
                            # Use a simple time-based estimate
                            stage = pipeline.stages.get("detection")
                            if stage and stage.start_time > 0:
                                elapsed = time.time() - stage.start_time
                                # Rough estimate: 100 frames per second on GPU
                                estimated = min(int(elapsed * 100), detection_total - 1)
                                detection_progress = max(estimated, last_frame_count)
                                last_frame_count = detection_progress
                        elif stage_statuses.get("detection") == "success":
                            detection_progress = detection_total
                        
                        send_progress({
                            "current_video": video_name,
                            "current_video_index": video_idx + 1,
                            "total_videos": len(videos),
                            "current_stage": current_stage,
                            "stages": stage_statuses,
                            "detection_progress": detection_progress,
                            "detection_total": detection_total,
                            "detected_kills": len(events),
                            "extracted_clips": len(clips)
                        })
                    except Exception:
                        pass
                    
                    time.sleep(0.5)
            
            monitor_thread = threading.Thread(target=monitor_pipeline, daemon=True)
            monitor_thread.start()
            
            try:
                # Run pipeline until clips (for multi-video support)
                if len(videos) > 1:
                    clips = pipeline.run_until_clips(video_path)
                else:
                    success = pipeline.run(video_path)
                    clips = pipeline.results.get("clips", [])
                
                all_clips.extend(clips)
                final_video = pipeline.results.get("final_video")
                report_path = pipeline.results.get("report_path")
                output_video = _make_output_file(final_video, f"{video_name} 高光视频", "video")
                output_report = _make_output_file(report_path, f"{video_name} 报告", "report")
                for output_file in [output_video, output_report]:
                    if output_file:
                        output_files.append(output_file)
                
                # Final progress update for this video
                send_progress({
                    "current_video": video_name,
                    "current_video_index": video_idx + 1,
                    "total_videos": len(videos),
                    "current_stage": "completed",
                    "stages": {s[0]: "success" for s in PIPELINE_STAGES},
                    "detection_progress": len(pipeline.results.get("frames", [])),
                    "detection_total": len(pipeline.results.get("frames", [])),
                    "detected_kills": len(pipeline.results.get("events", [])),
                    "extracted_clips": len(clips)
                })
                
            finally:
                stop_monitor.set()
                monitor_thread.join(timeout=1)
        
        # Multi-video merge if needed
        if len(videos) > 1 and all_clips:
            send_progress({
                "current_video": "合并所有片段...",
                "current_video_index": len(videos),
                "total_videos": len(videos),
                "current_stage": "merging",
                "stages": {s[0]: "success" for s in PIPELINE_STAGES},
                "detection_progress": 100,
                "detection_total": 100,
                "detected_kills": len(all_clips),
                "extracted_clips": len(all_clips)
            })
            
            from src.video.video_joiner import VideoJoiner
            from src.audio.audio_mixer import AudioMixer
            from datetime import datetime
            
            output_dir = config.get("global", {}).get("output_dir", "output")
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            merged_path = os.path.join(output_dir, f"combined_temp_{timestamp}.mp4")
            final_path = os.path.join(output_dir, f"combined_highlights_{timestamp}.mp4")
            
            joiner = VideoJoiner(config)
            clip_paths = [c.get("path") or c.get("output_path") for c in all_clips if c.get("path") or c.get("output_path")]
            
            if joiner.join_clips(clip_paths, merged_path):
                mixer = AudioMixer(config)
                result_path = mixer.mix_audio(merged_path, final_path)
                
                if result_path == merged_path:
                    import shutil
                    shutil.copy2(merged_path, final_path)
                
                keep_intermediates = bool(config.get("global", {}).get("debug", False)) or bool(
                    config.get("video", {}).get("join_fix", {}).get("keep_intermediates", False)
                )
                if os.path.exists(merged_path) and merged_path != final_path and not keep_intermediates:
                    os.remove(merged_path)

                output_file = _make_output_file(final_path, "合并高光视频", "video")
                if output_file:
                    output_files.append(output_file)
        
        result_queue.put({
            "success": True,
            "total_clips": len(all_clips),
            "videos_processed": len(videos),
            "output_files": output_files,
            "message": "Processing completed successfully"
        })
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        send_error(error_msg)
        result_queue.put({
            "success": False,
            "error": error_msg
        })


class TaskManager:
    """
    Manages a single video processing task.
    Uses multiprocessing for isolation.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.task_info = TaskInfo()
        self.process: Optional[multiprocessing.Process] = None
        self.progress_queue: Optional[multiprocessing.Queue] = None
        self.result_queue: Optional[multiprocessing.Queue] = None
        self.cancel_event: Optional[multiprocessing.Event] = None
        self._error_buffer: List[Dict] = []
        self._max_error_buffer = 50
        self._monitor_thread: Optional[threading.Thread] = None
    
    def start_task(self, videos: List[str], game: str) -> Dict[str, Any]:
        """Start a new processing task."""
        if self.task_info.status == TaskStatus.RUNNING:
            return {
                "success": False,
                "error": "A task is already running. Cancel it first."
            }
        
        if not videos:
            return {"success": False, "error": "No videos provided"}
        
        missing = [v for v in videos if not os.path.exists(v)]
        if missing:
            return {"success": False, "error": f"Files not found: {missing}"}
        
        # Reset state
        self._error_buffer = []
        self.task_info = TaskInfo(
            status=TaskStatus.RUNNING,
            videos=videos,
            game=game,
            start_time=time.time(),
            progress=ProgressInfo(
                total_videos=len(videos),
                stages={s[0]: "pending" for s in PIPELINE_STAGES}
            )
        )
        
        # Create queues and event
        self.progress_queue = multiprocessing.Queue(maxsize=1000)
        self.result_queue = multiprocessing.Queue()
        self.cancel_event = multiprocessing.Event()
        
        # Start worker process
        self.process = multiprocessing.Process(
            target=_run_processing_task,
            args=(videos, game, self.progress_queue, self.result_queue, self.cancel_event),
            daemon=True
        )
        self.process.start()
        
        # Start monitor thread
        self._monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
        self._monitor_thread.start()
        
        return {"success": True, "message": "Task started"}
    
    def _monitor_process(self):
        """Monitor the worker process and collect results."""
        if self.process is None:
            return
        
        while self.process.is_alive():
            self._drain_progress_queue()
            time.sleep(0.2)
        
        self._drain_progress_queue()
        
        try:
            result = self.result_queue.get_nowait()
            self.task_info.result = result
            
            if result.get("success"):
                self.task_info.status = TaskStatus.COMPLETED
            else:
                self.task_info.status = TaskStatus.FAILED
                self.task_info.error = result.get("error")
        except Empty:
            if self.cancel_event and self.cancel_event.is_set():
                self.task_info.status = TaskStatus.CANCELLED
            else:
                self.task_info.status = TaskStatus.FAILED
                self.task_info.error = "Process ended unexpectedly"
        
        self.task_info.end_time = time.time()
    
    def _drain_progress_queue(self):
        """Drain the progress queue and update task info."""
        if not self.progress_queue:
            return
        
        while True:
            try:
                msg = self.progress_queue.get_nowait()
                msg_type = msg.get("type", "")
                
                if msg_type == "progress":
                    progress = self.task_info.progress
                    progress.current_video = msg.get("current_video", progress.current_video)
                    progress.current_video_index = msg.get("current_video_index", progress.current_video_index)
                    progress.total_videos = msg.get("total_videos", progress.total_videos)
                    progress.current_stage = msg.get("current_stage", progress.current_stage)
                    progress.stages = msg.get("stages", progress.stages)
                    progress.detection_progress = msg.get("detection_progress", progress.detection_progress)
                    progress.detection_total = msg.get("detection_total", progress.detection_total)
                    progress.detected_kills = msg.get("detected_kills", progress.detected_kills)
                    progress.extracted_clips = msg.get("extracted_clips", progress.extracted_clips)
                    
                elif msg_type == "error":
                    self._error_buffer.append({
                        "level": msg.get("level", "ERROR"),
                        "message": msg.get("message", ""),
                        "time": msg.get("time", "")
                    })
                    if len(self._error_buffer) > self._max_error_buffer:
                        self._error_buffer = self._error_buffer[-self._max_error_buffer:]
                        
            except Empty:
                break
    
    def cancel_task(self) -> Dict[str, Any]:
        """Cancel the currently running task."""
        if self.task_info.status != TaskStatus.RUNNING:
            return {"success": False, "error": "No task is running"}
        
        if self.cancel_event:
            self.cancel_event.set()
        
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
        
        self.task_info.status = TaskStatus.CANCELLED
        self.task_info.end_time = time.time()
        
        return {"success": True, "message": "Task cancelled"}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current task status with progress."""
        self._drain_progress_queue()
        
        progress = self.task_info.progress
        
        status = {
            "status": self.task_info.status.value,
            "videos": self.task_info.videos,
            "game": self.task_info.game,
            "progress": {
                "current_video": progress.current_video,
                "current_video_index": progress.current_video_index,
                "total_videos": progress.total_videos,
                "current_stage": progress.current_stage,
                "stages": progress.stages,
                "detection_progress": progress.detection_progress,
                "detection_total": progress.detection_total,
                "detected_kills": progress.detected_kills,
                "extracted_clips": progress.extracted_clips,
            }
        }
        
        if self.task_info.start_time:
            status["start_time"] = self.task_info.start_time
            status["elapsed"] = time.time() - self.task_info.start_time
        
        if self.task_info.end_time:
            status["end_time"] = self.task_info.end_time
            status["duration"] = self.task_info.end_time - (self.task_info.start_time or self.task_info.end_time)
        
        if self.task_info.error:
            status["error"] = self.task_info.error
        
        if self.task_info.result:
            status["result"] = self.task_info.result
        
        return status
    
    def get_errors(self, since_index: int = 0) -> List[Dict]:
        """Get error logs since a specific index."""
        self._drain_progress_queue()
        return self._error_buffer[since_index:]
    
    def clear(self):
        """Clear task state for new task."""
        if self.task_info.status == TaskStatus.RUNNING:
            self.cancel_task()
        
        self.task_info = TaskInfo()
        self._error_buffer = []
        self.process = None
        self.progress_queue = None
        self.result_queue = None
        self.cancel_event = None


# Global instance
task_manager = TaskManager()
