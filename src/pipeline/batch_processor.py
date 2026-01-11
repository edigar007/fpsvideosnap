import os
import glob
from typing import List, Dict, Any
from src.utils.logger import get_logger
from src.pipeline.pipeline import Pipeline

logger = get_logger(__name__)

class BatchProcessor:
    """
    Handles processing of multiple video files.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pipeline = Pipeline(config)

    def process(self, input_pattern: str) -> List[Dict[str, Any]]:
        """
        Processes video files matching the input pattern.
        """
        # Resolve wildcard patterns
        video_files = []
        if os.path.isdir(input_pattern):
            # If it's a directory, look for common video extensions
            for ext in ['.mp4', '.avi', '.mkv', '.mov']:
                video_files.extend(glob.glob(os.path.join(input_pattern, f"*{ext}")))
                video_files.extend(glob.glob(os.path.join(input_pattern, f"*{ext.upper()}")))
        else:
            video_files = glob.glob(input_pattern)

        if not video_files:
            logger.warning(f"No video files found matching pattern: {input_pattern}")
            return []

        logger.info(f"Found {len(video_files)} video files to process.")
        
        results = []
        for i, video_path in enumerate(video_files):
            logger.info(f"\n[bold magenta]Processing video {i+1}/{len(video_files)}: {video_path}[/bold magenta]")
            success = self.pipeline.run(video_path)
            
            results.append({
                "path": video_path,
                "success": success,
                "summary": self.pipeline.get_summary()
            })
            
            # Print individual summary
            logger.info(self.pipeline.get_summary())
            
            # Reset pipeline for next video if needed (Pipeline init handles some state)
            # Re-initializing to ensure a clean state
            self.pipeline = Pipeline(self.config)

        return results
