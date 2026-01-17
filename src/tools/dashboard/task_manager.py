"""
Task Manager for handling video processing tasks.
Manages a single task at a time with process isolation.
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


def _run_processing_task(
    videos: List[str],
    game: str,
    log_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
    cancel_event: multiprocessing.Event
):
    """
    Worker function that runs in a separate process.
    Executes the video processing pipeline.
    """
    import logging
    from queue import Full
    
    # Setup custom handler to capture logs
    class ProcessQueueHandler(logging.Handler):
        def __init__(self, queue):
            super().__init__()
            self.queue = queue
            
        def emit(self, record):
            try:
                log_entry = {
                    "level": record.levelname,
                    "message": self.format(record),
                    "time": time.strftime("%H:%M:%S", time.localtime(record.created)),
                }
                self.queue.put_nowait(log_entry)
            except Full:
                pass
            except Exception:
                pass
    
    # Configure root logger for this process
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers and add our queue handler
    root_logger.handlers = []
    queue_handler = ProcessQueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    queue_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(queue_handler)
    
    # Also configure fps_video_snap logger
    fps_logger = logging.getLogger("fps_video_snap")
    fps_logger.setLevel(logging.DEBUG)
    fps_logger.handlers = []
    fps_logger.addHandler(queue_handler)
    
    logger = logging.getLogger("fps_video_snap.dashboard.worker")
    
    try:
        logger.info(f"[bold blue]Starting processing task...[/bold blue]")
        logger.info(f"Game: {game}")
        logger.info(f"Videos: {len(videos)} file(s)")
        
        # Check for cancellation
        if cancel_event.is_set():
            logger.warning("Task cancelled before starting")
            result_queue.put({"success": False, "error": "Cancelled"})
            return
        
        # Import here to avoid loading heavy modules in main process
        from src.config.config_loader import get_config
        from src.pipeline.batch_processor import BatchProcessor
        
        # Load configuration
        logger.info(f"Loading configuration for game: [yellow]{game}[/yellow]")
        config = get_config(game_name=game)
        
        # Check for cancellation
        if cancel_event.is_set():
            logger.warning("Task cancelled after config load")
            result_queue.put({"success": False, "error": "Cancelled"})
            return
        
        # Create processor and run
        processor = BatchProcessor(config)
        results = processor.process(videos)
        
        # Check results
        if not results:
            logger.warning("No videos were processed.")
            result_queue.put({"success": True, "results": [], "message": "No videos processed"})
            return
        
        # Find merged result or count successes
        merged_result = next((r for r in results if r.get("path") == "MERGED"), None)
        
        if merged_result:
            logger.info(f"[bold green]Multi-video merge complete![/bold green]")
            logger.info(f"  Source videos: {merged_result.get('source_videos', 0)}")
            logger.info(f"  Total clips: {merged_result.get('total_clips', 0)}")
            logger.info(f"  Output: [cyan]{merged_result.get('final_video')}[/cyan]")
        else:
            success_count = sum(1 for r in results if r.get('success'))
            logger.info(f"[bold green]Processing finished![/bold green]")
            logger.info(f"Successfully processed: [green]{success_count}/{len(results)}[/green]")
        
        result_queue.put({
            "success": True,
            "results": results,
            "message": "Processing completed successfully"
        })
        
    except Exception as e:
        logger.exception(f"[red]Processing failed: {e}[/red]")
        result_queue.put({
            "success": False,
            "error": str(e)
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
        self.log_queue: Optional[multiprocessing.Queue] = None
        self.result_queue: Optional[multiprocessing.Queue] = None
        self.cancel_event: Optional[multiprocessing.Event] = None
        self._log_buffer: List[Dict] = []
        self._max_log_buffer = 1000
        self._monitor_thread: Optional[threading.Thread] = None
    
    def start_task(self, videos: List[str], game: str) -> Dict[str, Any]:
        """
        Start a new processing task.
        
        Args:
            videos: List of video file paths
            game: Game name for configuration
            
        Returns:
            Dict with status and message
        """
        if self.task_info.status == TaskStatus.RUNNING:
            return {
                "success": False,
                "error": "A task is already running. Cancel it first."
            }
        
        # Validate inputs
        if not videos:
            return {"success": False, "error": "No videos provided"}
        
        # Verify files exist
        missing = [v for v in videos if not os.path.exists(v)]
        if missing:
            return {"success": False, "error": f"Files not found: {missing}"}
        
        # Reset state
        self._log_buffer = []
        self.task_info = TaskInfo(
            status=TaskStatus.RUNNING,
            videos=videos,
            game=game,
            start_time=time.time()
        )
        
        # Create queues and event
        self.log_queue = multiprocessing.Queue(maxsize=10000)
        self.result_queue = multiprocessing.Queue()
        self.cancel_event = multiprocessing.Event()
        
        # Start worker process
        self.process = multiprocessing.Process(
            target=_run_processing_task,
            args=(videos, game, self.log_queue, self.result_queue, self.cancel_event),
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
            
        self.process.join()
        
        # Collect result
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
        """Get current task status."""
        # Drain log queue to buffer
        self._drain_log_queue()
        
        status = {
            "status": self.task_info.status.value,
            "videos": self.task_info.videos,
            "game": self.task_info.game,
        }
        
        if self.task_info.start_time:
            status["start_time"] = self.task_info.start_time
            status["elapsed"] = time.time() - self.task_info.start_time
        
        if self.task_info.end_time:
            status["end_time"] = self.task_info.end_time
            status["duration"] = self.task_info.end_time - self.task_info.start_time
        
        if self.task_info.error:
            status["error"] = self.task_info.error
        
        if self.task_info.result:
            status["result"] = self.task_info.result
        
        return status
    
    def get_logs(self, since_index: int = 0) -> List[Dict]:
        """
        Get logs since a specific index.
        
        Args:
            since_index: Return logs after this index
            
        Returns:
            List of log entries
        """
        self._drain_log_queue()
        return self._log_buffer[since_index:]
    
    def _drain_log_queue(self):
        """Drain the log queue into the buffer."""
        if not self.log_queue:
            return
            
        while True:
            try:
                log_entry = self.log_queue.get_nowait()
                self._log_buffer.append(log_entry)
                
                # Trim buffer if too large
                if len(self._log_buffer) > self._max_log_buffer:
                    self._log_buffer = self._log_buffer[-self._max_log_buffer:]
            except Empty:
                break
    
    def log_stream(self):
        """
        Generator for SSE log streaming.
        Yields log entries as they arrive.
        """
        last_index = 0
        
        while self.task_info.status == TaskStatus.RUNNING:
            logs = self.get_logs(last_index)
            for log in logs:
                yield log
                last_index += 1
            time.sleep(0.1)
        
        # Final drain
        logs = self.get_logs(last_index)
        for log in logs:
            yield log
    
    def clear(self):
        """Clear task state for new task."""
        if self.task_info.status == TaskStatus.RUNNING:
            self.cancel_task()
        
        self.task_info = TaskInfo()
        self._log_buffer = []
        self.process = None
        self.log_queue = None
        self.result_queue = None
        self.cancel_event = None


# Global instance
task_manager = TaskManager()
