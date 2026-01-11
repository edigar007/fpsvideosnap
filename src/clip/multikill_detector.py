from typing import List, Dict

class MultiKillDetector:
    """
    Detects multi-kill patterns within merged clips.
    """
    
    KILL_TYPES = {
        1: "single_kill",
        2: "double_kill",
        3: "triple_kill",
        4: "quad_kill",
        5: "penta_kill"
    }
    DEFAULT_MORE = "multi_kill"

    def __init__(self, multikill_threshold: float = 10.0):
        """
        Args:
            multikill_threshold: Max seconds between first and last kill to consider it a multi-kill
                                 (or between consecutive kills, depending on definition).
                                 Here we use it as the window for the whole sequence in a clip.
        """
        self.multikill_threshold = multikill_threshold

    def detect(self, merged_clips: List[Dict]) -> List[Dict]:
        """
        Adds multi-kill metadata to merged clips.
        Each clip already has a list of 'events'.
        """
        for clip in merged_clips:
            events = clip["events"]
            kill_count = len(events)
            
            # Simple logic: If more than 1 kill in a merged segment, it's a multi-kill
            # In some cases, we might want to check if they are within N seconds of each other.
            # But since they are already merged (meaning they are close enough to overlap padding),
            # they are already temporally related.
            
            clip["kill_count"] = kill_count
            
            if kill_count >= 2:
                # Check time span
                span = (events[-1]["timestamp_ms"] - events[0]["timestamp_ms"]) / 1000.0
                if span <= self.multikill_threshold:
                    clip["kill_type"] = self.KILL_TYPES.get(kill_count, self.DEFAULT_MORE)
                else:
                    clip["kill_type"] = "multiple_kills" # Too far apart for "multi-kill" naming
            else:
                clip["kill_type"] = "single_kill"
                
        return merged_clips
