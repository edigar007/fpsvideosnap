"""
Custom logging handler that captures logs to a queue for SSE streaming.
"""
import logging
import time
from queue import Queue


class QueueLogHandler(logging.Handler):
    """
    A logging handler that sends log records to a Queue.
    Used for streaming logs via Server-Sent Events.
    """
    
    def __init__(self, queue: Queue, level: int = logging.DEBUG):
        super().__init__(level)
        self.queue = queue
        self.formatter = logging.Formatter('%(message)s')
    
    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Format the log message
            message = self.format(record)
            
            # Create log entry dict
            log_entry = {
                "level": record.levelname,
                "message": message,
                "time": time.strftime("%H:%M:%S", time.localtime(record.created)),
                "timestamp": record.created
            }
            
            # Put in queue (non-blocking)
            self.queue.put_nowait(log_entry)
        except Exception:
            self.handleError(record)


def setup_queue_logger(queue: Queue, logger_name: str = "fps_video_snap") -> logging.Logger:
    """
    Setup a logger that sends output to a queue.
    
    Args:
        queue: The queue to send log entries to
        logger_name: Name of the logger to configure
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    
    # Remove existing handlers to avoid duplicates
    # But keep RichHandler for console output if present
    
    # Add our queue handler
    queue_handler = QueueLogHandler(queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)
    
    return logger


def remove_queue_handler(logger_name: str = "fps_video_snap") -> None:
    """Remove QueueLogHandler from the specified logger."""
    logger = logging.getLogger(logger_name)
    handlers_to_remove = [h for h in logger.handlers if isinstance(h, QueueLogHandler)]
    for handler in handlers_to_remove:
        logger.removeHandler(handler)
