from typing import List, Union
import numpy as np
import cv2
from src.utils.logger import get_logger

logger = get_logger(__name__)

class YoloDetector:
    """
    Wrapper for Ultralytics YOLOv8 focused on high-performance batch inference.
    """
    def __init__(self, model, batch_size=16, confidence_threshold=0.5):
        self.model = model
        self.batch_size = batch_size
        self.confidence_threshold = confidence_threshold

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[dict]]:
        """
        Runs inference on a list of frames and returns detection results.
        
        Args:
            frames: List of images (BGR format from OpenCV)
            
        Returns:
            A list of lists, where each inner list contains dictionaries of detections:
            [{'box': [x1, y1, x2, y2], 'conf': 0.9, 'class': 'kill'}]
        """
        if not frames:
            return []
            
        all_results = []
        
        # Process in batches to optimize GPU utilization
        for i in range(0, len(frames), self.batch_size):
            batch = frames[i:i + self.batch_size]
            
            # Run inference
            # stream=True can be more memory efficient for large batches
            results = self.model(batch, conf=self.confidence_threshold, verbose=False)
            
            for r in results:
                detections = []
                for box in r.boxes:
                    detections.append({
                        'box': box.xyxy[0].tolist(), # [x1, y1, x2, y2]
                        'conf': float(box.conf[0]),
                        'class': int(box.cls[0]),
                        'name': r.names[int(box.cls[0])]
                    })
                all_results.append(detections)
                
        return all_results

    def detect_single(self, frame: np.ndarray) -> List[dict]:
        """
        Convenience method for single frame detection.
        """
        return self.detect_batch([frame])[0]
