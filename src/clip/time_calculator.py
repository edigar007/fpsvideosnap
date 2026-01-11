from typing import List, Dict

class TimeCalculator:
    """
    Calculates start and end times for kill events based on padding configuration.
    """
    
    def __init__(self, pre_kill_time: float, post_kill_time: float):
        """
        Args:
            pre_kill_time: Seconds to include before the event.
            post_kill_time: Seconds to include after the event.
        """
        self.pre_kill_time = pre_kill_time
        self.post_kill_time = post_kill_time

    def calculate_segments(self, events: List[Dict]) -> List[Dict]:
        """
        Calculates start and end times in seconds for each event.
        Returns a list of segments with 'start', 'end', and original 'event' data.
        """
        segments = []
        for event in events:
            timestamp_sec = event["timestamp_ms"] / 1000.0
            start = max(0.0, timestamp_sec - self.pre_kill_time)
            end = timestamp_sec + self.post_kill_time
            
            segments.append({
                "start": round(start, 3),
                "end": round(end, 3),
                "event": event
            })
            
        return segments
