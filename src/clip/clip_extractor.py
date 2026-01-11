import os
import json
from typing import List, Dict, Optional
from src.utils.logger import get_logger
from src.utils.progress import get_progress_bar
from src.video.clip_cutter import ClipCutter
from .time_calculator import TimeCalculator
from .overlap_merger import OverlapMerger
from .multikill_detector import MultiKillDetector

logger = get_logger(__name__)

class ClipExtractor:
    """
    Orchestrates the extraction of video clips from detected kill events.
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.highlights_cfg = config.get("highlights", {})
        self.video_cfg = config.get("video", {})
        
        self.pre_kill_time = self.highlights_cfg.get("pre_kill_time", 3.0)
        self.post_kill_time = self.highlights_cfg.get("post_kill_time", 1.0)
        self.multikill_threshold = self.highlights_cfg.get("multikill_threshold", 10.0)
        
        self.calculator = TimeCalculator(self.pre_kill_time, self.post_kill_time)
        self.merger = OverlapMerger()
        self.detector = MultiKillDetector(self.multikill_threshold)
        
        self.cutter = ClipCutter(
            ffmpeg_path=self.video_cfg.get("ffmpeg_path", "ffmpeg"),
            hwaccel=self.video_cfg.get("hwaccel", "cuda")
        )

    def extract_from_json(self, video_path: str, json_path: str, output_dir: str) -> List[Dict]:
        """
        Loads events from JSON and extracts clips.
        """
        if not os.path.exists(json_path):
            logger.error(f"Detection JSON not found: {json_path}")
            return []
            
        with open(json_path, 'r', encoding='utf-8') as f:
            events = json.load(f)
            
        return self.extract_clips(video_path, events, output_dir)

    def extract_clips(self, video_path: str, events: List[Dict], output_dir: str) -> List[Dict]:
        """
        Main extraction pipeline.
        """
        if not events:
            logger.info("No events detected, skipping extraction.")
            return []
            
        logger.info(f"Starting clip extraction for {video_path}...")
        
        # 1. Calculate segments
        segments = self.calculator.calculate_segments(events)
        
        # 2. Merge overlapping segments
        merged_clips = self.merger.merge(segments)
        
        # 3. Detect multi-kills and add metadata
        processed_clips = self.detector.detect(merged_clips)
        
        # 4. Extract clips using FFmpeg
        final_clips = []
        os.makedirs(output_dir, exist_ok=True)
        
        progress = get_progress_bar()
        task_id = progress.add_task("[cyan]Extracting clips...", total=len(processed_clips))
        
        with progress:
            for idx, clip in enumerate(processed_clips):
                # Format metadata
                start = clip["start"]
                duration = clip["end"] - start
                kill_count = clip["kill_count"]
                kill_type = clip["kill_type"]
                timestamp_str = f"{int(start)}s"
                
                # TASK-031: Filename convention
                filename = f"clip_{idx+1:03d}_{kill_type}_{timestamp_str}.mp4"
                output_path = os.path.join(output_dir, filename)
                
                logger.info(f"Extracting clip {idx+1}: {filename} ({start:.2f}s -> {clip['end']:.2f}s)")
                
                try:
                    self.cutter.cut_segment(video_path, output_path, start, duration)
                    clip["filename"] = filename
                    clip["output_path"] = output_path
                    clip["id"] = idx + 1
                    final_clips.append(clip)
                except Exception as e:
                    logger.error(f"Failed to extract clip {idx+1}: {str(e)}")
                
                progress.update(task_id, advance=1)
                
        logger.info(f"Successfully extracted {len(final_clips)} clips.")
        
        # Save clip metadata for future phases (like concatenation)
        self._save_metadata(output_dir, final_clips)
        
        return final_clips

    def _save_metadata(self, output_dir: str, clips: List[Dict]):
        meta_path = os.path.join(output_dir, "clips_metadata.json")
        # Remove event objects to keep JSON clean if they are too large, 
        # or keep them if needed. Recording timestamps is essential.
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(clips, f, indent=4, ensure_ascii=False)
        logger.info(f"Saved clip metadata to {meta_path}")
