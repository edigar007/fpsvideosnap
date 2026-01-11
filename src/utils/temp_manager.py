import os
import shutil
import uuid
from typing import List
from src.utils.logger import logger

class TempManager:
    """Manages temporary directories and files for the video processing pipeline."""
    
    def __init__(self, base_temp_dir: str = "temp"):
        self.base_temp_dir = os.path.abspath(base_temp_dir)
        self.tracked_paths: List[str] = []
        
        if not os.path.exists(self.base_temp_dir):
            os.makedirs(self.base_temp_dir, exist_ok=True)
            logger.debug(f"Created base temp directory: {self.base_temp_dir}")

    def create_temp_dir(self, prefix: str = "snap_") -> str:
        """Creates a unique temporary directory and tracks it."""
        unique_id = str(uuid.uuid4())[:8]
        dir_name = f"{prefix}{unique_id}"
        temp_path = os.path.join(self.base_temp_dir, dir_name)
        
        os.makedirs(temp_path, exist_ok=True)
        self.tracked_paths.append(temp_path)
        logger.debug(f"Created temp directory: {temp_path}")
        return temp_path

    def get_temp_path(self, filename: str, subdir: str = None) -> str:
        """Generates a path within a temporary directory."""
        base = self.base_temp_dir
        if subdir:
            base = os.path.join(base, subdir)
            if not os.path.exists(base):
                os.makedirs(base, exist_ok=True)
                if base not in self.tracked_paths:
                    self.tracked_paths.append(base)
        
        return os.path.join(base, filename)

    def clean_all(self):
        """Removes all tracked temporary paths."""
        for path in self.tracked_paths:
            if os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    logger.debug(f"Cleaned up temp path: {path}")
                except Exception as e:
                    logger.error(f"Failed to clean up {path}: {e}")
        self.tracked_paths = []

    def __del__(self):
        pass

# Global instance for easy access
temp_manager = TempManager()
