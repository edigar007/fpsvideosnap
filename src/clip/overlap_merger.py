from typing import List, Dict
from src.utils.logger import get_logger

logger = get_logger(__name__)

class OverlapMerger:
    """
    Merges overlapping time segments into continuous clips.
    """
    
    def merge(self, segments: List[Dict]) -> List[Dict]:
        """
        Merges overlapping segments. 
        Input segments should have 'start', 'end', and 'event' (or list of 'events').
        """
        if not segments:
            return []

        # Sort segments by start time
        sorted_segments = sorted(segments, key=lambda x: x["start"])
        
        merged = []
        if not sorted_segments:
            return merged

        current = {
            "start": sorted_segments[0]["start"],
            "end": sorted_segments[0]["end"],
            "events": [sorted_segments[0]["event"]]
        }

        for i in range(1, len(sorted_segments)):
            next_seg = sorted_segments[i]
            
            # If next segment starts before or exactly when current ends, merge them
            # We can also add a small buffer if needed, but simple overlap is usually fine
            if next_seg["start"] <= current["end"]:
                current["end"] = max(current["end"], next_seg["end"])
                current["events"].append(next_seg["event"])
            else:
                merged.append(current)
                current = {
                    "start": next_seg["start"],
                    "end": next_seg["end"],
                    "events": [next_seg["event"]]
                }
        
        merged.append(current)
        logger.info(f"Merged {len(segments)} segments into {len(merged)} clips.")
        return merged
