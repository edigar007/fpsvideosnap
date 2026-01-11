import json
import os
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)

class TimestampRecorder:
    """
    Records detection results (timestamp, event type, confidence) to a JSON file.
    """
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.events = []

    def record_event(self, timestamp_ms: int, event_type: str, confidence: float, meta: dict = None):
        """
        Records a single detection event.
        """
        event = {
            "timestamp_ms": timestamp_ms,
            "type": event_type,
            "confidence": round(float(confidence), 3),
            "recorded_at": datetime.now().isoformat(),
            "meta": meta or {}
        }
        self.events.append(event)
        logger.debug(f"Recorded event: {event_type} at {timestamp_ms}ms (conf: {confidence})")

    def save(self):
        """
        Saves all recorded events to a JSON file.
        """
        try:
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(self.events, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved {len(self.events)} events to {self.output_path}")
        except Exception as e:
            logger.error(f"Failed to save events: {str(e)}")

    def get_events(self):
        return self.events
