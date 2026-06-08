"""
Task Manager for handling video processing tasks.
Manages a single task at a time with process isolation.
Includes progress tracking for UI display.
"""
import os
import time
import threading
import multiprocessing
from queue import Empty
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

from src.tools.dashboard.progress import PIPELINE_STAGES, make_output_file
from src.tools.dashboard.worker import run_processing_task as _run_processing_task


class TaskStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    return make_output_file(path, label, file_type)


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
