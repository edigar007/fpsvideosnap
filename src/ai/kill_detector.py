from typing import List, Dict, Optional
import numpy as np
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.ocr_detector import OCRDetector
from src.utils.logger import get_logger

logger = get_logger(__name__)

class KillDetector:
    """
    The main logic brain that combines YOLO, OCR, and OpenCV signals to detect kills.
    Implements a two-stage detection logic:
    1. Fast pre-filter (Color based)
    2. Precise detection (OCR + Template Matching + YOLO)
    """
    def __init__(self, yolo_detector: YoloDetector, opencv_matcher: OpenCVMatcher, game_config: dict, ocr_detector: Optional[OCRDetector] = None):
        self.yolo = yolo_detector
        self.cv = opencv_matcher
        self.config = game_config
        
        detection_cfg = game_config.get('detection', {})
        
        # Detection thresholds from config
        self.conf_threshold = detection_cfg.get('confidence_threshold', 0.5)
        self.roi = detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
        self.colors = detection_cfg.get('colors', {})
        
        # OCR Initialization (TASK-021)
        ocr_cfg = detection_cfg.get('ocr', {})
        self.ocr_enabled = ocr_cfg.get('enabled', False)
        self.ocr = ocr_detector
        if self.ocr_enabled and self.ocr is None:
            self.ocr = OCRDetector(
                lang=ocr_cfg.get('lang', 'ch'),
                use_gpu=ocr_cfg.get('use_gpu', True)
            )
        
        # Prefilter settings (TASK-022)
        prefilter_cfg = detection_cfg.get('prefilter', {})
        self.color_threshold = prefilter_cfg.get('color_threshold', 0.01)
        
        # Weights (TASK-021)
        self.weights = detection_cfg.get('weights', {
            'ocr': 0.4,
            'template': 0.3,
            'color': 0.2,
            'yolo': 0.1
        })

    def _prefilter(self, frame: np.ndarray) -> bool:
        """
        Fast color detection to decide if we should run heavy AI models. (TASK-022)
        """
        if not self.colors:
            return True # No colors defined, skip pre-filter
            
        max_color_pct = 0.0
        for color_name, color_cfg in self.colors.items():
            # 支持两种配置格式: hsv_lower/hsv_upper 或 lower/upper
            hsv_lower = color_cfg.get('hsv_lower', color_cfg.get('lower'))
            hsv_upper = color_cfg.get('hsv_upper', color_cfg.get('upper'))
            
            if hsv_lower and hsv_upper:
                # 应用容差
                tolerance = color_cfg.get('tolerance', 0)
                if tolerance > 0:
                    hsv_lower = [max(0, hsv_lower[0] - tolerance), max(0, hsv_lower[1] - tolerance), max(0, hsv_lower[2] - tolerance)]
                    hsv_upper = [min(179, hsv_upper[0] + tolerance), min(255, hsv_upper[1] + tolerance), min(255, hsv_upper[2] + tolerance)]
                
                pct = self.cv.detect_color(
                    frame, 
                    hsv_lower, 
                    hsv_upper, 
                    roi=self.roi
                )
                max_color_pct = max(max_color_pct, pct)
                
        return max_color_pct >= self.color_threshold

    def _calculate_confidence(self, signals: Dict) -> float:
        """
        Calculate weighted confidence score. (TASK-025)
        Redistributes weights if certain signals are not used (e.g. OCR disabled).
        """
        active_weights = {}
        
        # Determine which signals are "active"
        if self.ocr_enabled and self.ocr:
            active_weights['ocr'] = self.weights.get('ocr', 0.4)
        
        if self.cv.templates:
            active_weights['template'] = self.weights.get('template', 0.3)
            
        active_weights['color'] = self.weights.get('color', 0.2)
        active_weights['yolo'] = self.weights.get('yolo', 0.1)
        
        # Normalize weights
        total_weight = sum(active_weights.values())
        if total_weight == 0:
            return 0.0
            
        normalized_conf = 0.0
        for name, weight in active_weights.items():
            conf = signals.get(name, 0.0)
            normalized_conf += conf * (weight / total_weight)
            
        return normalized_conf

    def _precise_detect(self, frame: np.ndarray, yolo_conf: Optional[float] = None) -> Dict:
        """
        Runs heavy detection signals (OCR, Template, YOLO). (TASK-023)
        """
        signals = {}
        detection_cfg = self.config.get('detection', {})

        # 将相对 ROI 转换为像素坐标（用于 OCR）
        h, w = frame.shape[:2]
        x, y, w_roi, h_roi = self.roi
        roi_px = [int(x * w), int(y * h), int(w_roi * w), int(h_roi * h)]

        # 1. OCR Signal
        ocr_conf = 0.0
        if self.ocr_enabled and self.ocr:
            ocr_cfg = detection_cfg.get('ocr', {})
            keywords = ocr_cfg.get('keywords', ["击杀", "KILL"])
            res = self.ocr.find_keywords(frame, keywords, roi=roi_px)
            if res['found']:
                # fuzzy match gives 0-100, we want 0-1.0
                ocr_conf = res['confidence'] / 100.0 if res['confidence'] > 1.0 else res['confidence']
        signals['ocr'] = ocr_conf

        # 2. Template Signal
        max_template_conf = 0.0
        if self.cv.templates:
            # We check templates defined in config
            template_list = detection_cfg.get('templates', {})
            if not template_list:
                # Fallback to all loaded templates if not specified
                for t_name in self.cv.templates:
                    _, score = self.cv.match_template(frame, t_name, roi=self.roi)
                    max_template_conf = max(max_template_conf, score)
            else:
                for t_name in template_list:
                    _, score = self.cv.match_template(frame, t_name, roi=self.roi)
                    max_template_conf = max(max_template_conf, score)
        signals['template'] = max_template_conf

        # 3. YOLO Signal
        if yolo_conf is not None:
            max_yolo_conf = yolo_conf
        else:
            max_yolo_conf = 0.0
            yolo_detections = self.yolo.detect_single(frame)
            for d in yolo_detections:
                if d['name'] == 'kill':
                    max_yolo_conf = max(max_yolo_conf, d['conf'])
        signals['yolo'] = max_yolo_conf

        # 4. Color Signal (Recalculate or reuse for precise scoring)
        max_color_conf = 0.0
        for color_name, color_cfg in self.colors.items():
            # 支持两种配置格式: hsv_lower/hsv_upper 或 lower/upper
            hsv_lower = color_cfg.get('hsv_lower', color_cfg.get('lower'))
            hsv_upper = color_cfg.get('hsv_upper', color_cfg.get('upper'))
            
            if hsv_lower and hsv_upper:
                # 应用容差
                tolerance = color_cfg.get('tolerance', 0)
                if tolerance > 0:
                    hsv_lower = [max(0, hsv_lower[0] - tolerance), max(0, hsv_lower[1] - tolerance), max(0, hsv_lower[2] - tolerance)]
                    hsv_upper = [min(179, hsv_upper[0] + tolerance), min(255, hsv_upper[1] + tolerance), min(255, hsv_upper[2] + tolerance)]
                
                match_percent = self.cv.detect_color(frame, hsv_lower, hsv_upper, roi=self.roi)
                # Boost confidence if color pattern is found
                color_score = min(match_percent * 50, 1.0) 
                max_color_conf = max(max_color_conf, color_score)
        signals['color'] = max_color_conf

        return signals

    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Analyzes a single frame and returns detection results. (TASK-024, TASK-026, TASK-027)
        """
        results = {
            "is_kill": False,
            "confidence": 0.0,
            "signals": {}
        }

        # Step 1: Pre-filter (Fast)
        if not self._prefilter(frame):
            return results

        # Step 2: Precise detection (Heavy)
        signals = self._precise_detect(frame)
        results["signals"] = signals

        # Step 3: OCR Required logic (TASK-026)
        ocr_cfg = self.config.get('detection', {}).get('ocr', {})
        if ocr_cfg.get('required', False) and signals.get('ocr', 0.0) == 0:
            results["is_kill"] = False
            results["confidence"] = 0.0
            return results

        # Step 4: Weighted scoring
        final_conf = self._calculate_confidence(signals)
        results["confidence"] = final_conf
        results["is_kill"] = final_conf >= self.conf_threshold

        return results

    def process_video_batch(self, frames: List[np.ndarray], timestamps_ms: List[int]) -> List[dict]:
        """
        Processes a batch of frames and returns a list of kill events. (TASK-028)
        Optimized using two-stage flow.
        """
        events = []
        
        # Stage 1: Fast Filter all frames
        candidate_indices = []
        for i, frame in enumerate(frames):
            if self._prefilter(frame):
                candidate_indices.append(i)
        
        if not candidate_indices:
            return []

        # Stage 2: Heavy detection for candidates
        candidate_frames = [frames[i] for i in candidate_indices]
        
        # YOLO batch inference for candidates
        yolo_batch_results = self.yolo.detect_batch(candidate_frames)
        
        for idx, i in enumerate(candidate_indices):
            frame = frames[i]
            
            # Extract YOLO confidence from batch results
            max_yolo_conf = 0.0
            for d in yolo_batch_results[idx]:
                if d['name'] == 'kill':
                    max_yolo_conf = max(max_yolo_conf, d['conf'])
            
            # Run other signals (OCR, Template, Color) and combine with batch YOLO
            signals = self._precise_detect(frame, yolo_conf=max_yolo_conf)
            
            # OCR Required logic
            ocr_cfg = self.config.get('detection', {}).get('ocr', {})
            if ocr_cfg.get('required', False) and signals.get('ocr', 0.0) == 0:
                continue

            final_conf = self._calculate_confidence(signals)
            
            if final_conf >= self.conf_threshold:
                events.append({
                    "timestamp_ms": timestamps_ms[i],
                    "confidence": final_conf,
                    "type": "kill",
                    "signals": signals # Added for debugging (TASK-027 style)
                })
                
        return events

