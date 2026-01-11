import logging
from rich.logging import RichHandler

def setup_logger(debug: bool = False):
    """Sets up the global logger with Rich output."""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)]
    )
    
    return logging.getLogger("fps_video_snap")

def get_logger(name: str):
    """Returns a logger with the given name."""
    return logging.getLogger(f"fps_video_snap.{name}")

logger = logging.getLogger("fps_video_snap")
