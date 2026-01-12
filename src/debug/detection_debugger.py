import os
import cv2
import numpy as np
import json
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DetectionDebugger:
    """
    Handles visualization and debugging for kill detection.
    (TASK-029, TASK-030, TASK-031, TASK-034)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.detection_cfg = config.get('detection', {})
        self.roi = self.detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
        self.conf_threshold = self.detection_cfg.get('confidence_threshold', 0.5)

    def visualize_signals(self, frame: np.ndarray, results: Dict[str, Any], prefilter_passed: bool = True) -> np.ndarray:
        """
        Draw ROI, signals, and confidence scores on the frame. (TASK-030, TASK-034)
        """
        debug_frame = frame.copy()
        h, w = frame.shape[:2]

        # 1. Draw ROI
        # ROI is [x1, y1, x2, y2] in normalized coordinates (0-1)
        x1, y1, x2, y2 = self.roi
        ix1, iy1 = int(x1 * w), int(y1 * h)
        ix2, iy2 = int(x2 * w), int(y2 * h)
        
        # Color based on pre-filter
        roi_color = (0, 255, 0) if prefilter_passed else (255, 255, 255) # Green if passed, White if not
        cv2.rectangle(debug_frame, (ix1, iy1), (ix2, iy2), roi_color, 2)
        cv2.putText(debug_frame, "ROI", (ix1, iy1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, roi_color, 1)

        # 2. Draw Signals Overlay (Right panel)
        overlay = debug_frame.copy()
        panel_w = 250
        panel_h = 220
        cv2.rectangle(overlay, (w - panel_w - 10, 10), (w - 10, panel_h + 10), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, debug_frame, 0.4, 0, debug_frame)

        # 3. Text Info
        signals = results.get('signals', {})
        final_conf = results.get('confidence', 0.0)
        is_kill = results.get('is_kill', final_conf >= self.conf_threshold)
        
        y_offset = 40
        x_start = w - panel_w
        
        def draw_text(text, color=(255, 255, 255), scale=0.6, thickness=1):
            nonlocal y_offset
            cv2.putText(debug_frame, text, (x_start, y_offset), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)
            y_offset += 25

        # Signal Header
        draw_text("Detection Signals", (0, 255, 255), 0.7, 2)
        y_offset += 5
        
        # Individual Signals
        for name in ['ocr', 'template', 'yolo', 'color']:
            val = signals.get(name, 0.0)
            color = (0, 255, 0) if val > 0 else (200, 200, 200)
            draw_text(f"{name.upper()}: {val:.2f}", color)
            
        y_offset += 10
        
        # Final Confidence (TASK-034)
        conf_color = (0, 255, 0) if is_kill else (0, 0, 255)
        status_str = "[PASS]" if is_kill else "[FAIL]"
        draw_text(f"Final: {final_conf:.2f} {status_str}", conf_color, 0.7, 2)
        draw_text(f"Thresh: {self.conf_threshold:.2f}", (255, 255, 255), 0.5, 1)

        return debug_frame

    def generate_debug_overlay(self, input_video: str, detections: List[Dict], output_video: str):
        """
        Renders a video file with detection metadata overlay. (TASK-031)
        """
        logger.info(f"Generating debug video: {output_video}")
        
        cap = cv2.VideoCapture(input_video)
        if not cap.isOpened():
            logger.error(f"Cannot open input video: {input_video}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

        # Map detections to millisecond timestamps for easy lookup
        detection_map = {d['timestamp_ms']: d for d in detections if 'timestamp_ms' in d}
        
        # Group detections by frames if needed (approximate)
        # Note: In our pipeline, we extract frames at a certain interval.
        # This debug overlay might want to show EVERY frame but only highlight detections when they occur.
        
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            timestamp_ms = int((frame_idx / fps) * 1000)
            
            # Find matching detection (within 50ms window since we might not match exactly)
            current_detection = None
            for ts, d in detection_map.items():
                if abs(ts - timestamp_ms) < (500 / fps): # Half frame interval or so
                    current_detection = d
                    break
            
            if current_detection:
                frame = self.visualize_signals(frame, current_detection, prefilter_passed=True)
            else:
                # Still show ROI and "Searching..." status
                frame = self._visualize_idle(frame)
                
            out.write(frame)
            frame_idx += 1
            if frame_idx % 100 == 0:
                logger.debug(f"Rendered {frame_idx}/{total_frames} debug frames")

        cap.release()
        out.release()
        logger.info("Debug video generation complete.")

    def _visualize_idle(self, frame: np.ndarray) -> np.ndarray:
        """Draw idle status with ROI."""
        debug_frame = frame.copy()
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = self.roi
        cv2.rectangle(debug_frame, (int(x1*w), int(y1*h)), (int(x2*w), int(y2*h)), (255, 255, 255), 1)
        
        # Overlay for status
        overlay = debug_frame.copy()
        cv2.rectangle(overlay, (10, 10), (180, 40), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, debug_frame, 0.5, 0, debug_frame)
        cv2.putText(debug_frame, "Monitoring...", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return debug_frame

    def save_debug_frame(self, frame: np.ndarray, results: Dict[str, Any], path: str):
        """Save a single debug frame to disk."""
        viz = self.visualize_signals(frame, results)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cv2.imwrite(path, viz)
