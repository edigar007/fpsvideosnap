from typing import List, Dict
import numpy as np
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.utils.logger import get_logger

logger = get_logger(__name__)

class KillDetector:
    """
    The main logic brain that combines YOLO and OpenCV signals to detect kills.
    Implements a weighted scoring system for confidence.
    """
    def __init__(self, yolo_detector: YoloDetector, opencv_matcher: OpenCVMatcher, game_config: dict):
        self.yolo = yolo_detector
        self.cv = opencv_matcher
        self.config = game_config
        
        # Detection thresholds from config
        self.conf_threshold = game_config.get('detection', {}).get('confidence_threshold', 0.5)
        self.roi = game_config.get('detection', {}).get('killfeed_roi', [0, 0, 1, 1])
        self.colors = game_config.get('detection', {}).get('colors', {})

    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Analyzes a single frame and returns detection results with a confidence score.
        """
        results = {
            "is_kill": False,
            "confidence": 0.0,
            "signals": {}
        }

        # 1. YOLO Signal (Primary)
        # Assuming YOLO is trained to detect kill icons or text
        yolo_detections = self.yolo.detect_single(frame)
        max_yolo_conf = 0.0
        for d in yolo_detections:
            if d['name'] == 'kill':
                max_yolo_conf = max(max_yolo_conf, d['conf'])
        
        results["signals"]["yolo"] = max_yolo_conf

        # 2. OpenCV Color Signal (Supporting)
        # Check for specific colors in the killfeed ROI
        max_color_conf = 0.0
        for color_name, range_hsv in self.colors.items():
            if 'lower' in range_hsv and 'upper' in range_hsv:
                match_percent = self.cv.detect_color(
                    frame, 
                    range_hsv['lower'], 
                    range_hsv['upper'], 
                    roi=self.roi
                )
                # Boost confidence if color pattern is found
                # Typically, if >1% of ROI matches the color, it's a strong signal for UI
                color_score = min(match_percent * 50, 1.0) # Scale up
                max_color_conf = max(max_color_conf, color_score)
        
        results["signals"]["color"] = max_color_conf

        # 3. OpenCV Template Signal (Optional/Supporting)
        # If we have templates for things like "skull" icons
        max_template_conf = 0.0
        # For now, let's assume if templates are loaded, we check them
        if self.cv.templates:
            for t_name in self.cv.templates:
                _, score = self.cv.match_template(frame, t_name, roi=self.roi)
                max_template_conf = max(max_template_conf, score)
        
        results["signals"]["template"] = max_template_conf

        # 4. Weighted Confidence Scoring (TASK-021)
        # Weights: YOLO (0.6), Color (0.2), Template (0.2)
        final_conf = (max_yolo_conf * 0.6) + (max_color_conf * 0.2) + (max_template_conf * 0.2)
        
        # If no templates are used, redistribute weights or just use what we have
        if not self.cv.templates:
             final_conf = (max_yolo_conf * 0.7) + (max_color_conf * 0.3)

        results["confidence"] = final_conf
        results["is_kill"] = final_conf >= self.conf_threshold

        return results

    def process_video_batch(self, frames: List[np.ndarray], timestamps_ms: List[int]) -> List[dict]:
        """
        Processes a batch of frames and returns a list of kill events.
        """
        events = []
        
        # Batch YOLO for performance
        yolo_results = self.yolo.detect_batch(frames)
        
        for i, frame in enumerate(frames):
            # For each frame, merge with OpenCV signals
            # Note: OpenCV is fast enough to do per-frame even in batch mode
            # but we could also optimize if needed.
            
            # Recalculate signal for this frame (reuse YOLO results)
            max_yolo_conf = 0.0
            for d in yolo_results[i]:
                if d['name'] == 'kill':
                    max_yolo_conf = max(max_yolo_conf, d['conf'])
            
            # Color signal
            max_color_conf = 0.0
            for color_name, range_hsv in self.colors.items():
                match_percent = self.cv.detect_color(frame, range_hsv['lower'], range_hsv['upper'], roi=self.roi)
                max_color_conf = max(max_color_conf, min(match_percent * 50, 1.0))

            # Template signal
            max_template_conf = 0.0
            if self.cv.templates:
                for t_name in self.cv.templates:
                    _, score = self.cv.match_template(frame, t_name, roi=self.roi)
                    max_template_conf = max(max_template_conf, score)

            final_conf = (max_yolo_conf * 0.6) + (max_color_conf * 0.2) + (max_template_conf * 0.2)
            if not self.cv.templates:
                final_conf = (max_yolo_conf * 0.7) + (max_color_conf * 0.3)

            if final_conf >= self.conf_threshold:
                events.append({
                    "timestamp_ms": timestamps_ms[i],
                    "confidence": final_conf,
                    "type": "kill"
                })
                
        return events
