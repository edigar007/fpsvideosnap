from typing import List, Dict, Optional
import numpy as np
import time
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.ocr_detector import OCRDetector
from src.utils.logger import get_logger
from src.utils.performance_profiler import get_profiler

logger = get_logger(__name__)
profiler = get_profiler()

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
        passed, _ = self._prefilter_with_result(frame)
        return passed
    
    def _prefilter_with_result(self, frame: np.ndarray) -> tuple:
        """
        Fast color detection with result caching support.
        Returns: (passed: bool, max_color_pct: float)
        """
        profiler.start('prefilter_color_detection')
        
        if not self.colors:
            profiler.end('prefilter_color_detection')
            return True, 1.0  # No colors defined, skip pre-filter
            
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
        
        profiler.end('prefilter_color_detection')
        return max_color_pct >= self.color_threshold, max_color_pct

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

    def _precise_detect(self, frame: np.ndarray, yolo_conf: Optional[float] = None, cached_color_pct: Optional[float] = None) -> Dict:
        """
        Runs heavy detection signals (OCR, Template, YOLO). (TASK-023)
        
        Args:
            cached_color_pct: 如果提供，则使用缓存的颜色检测结果，避免重复计算
        """
        signals = {}
        detection_cfg = self.config.get('detection', {})

        # 将相对 ROI 转换为像素坐标（用于 OCR）
        h, w = frame.shape[:2]
        profiler.start('precise_ocr_detection')
        ocr_conf = 0.0
        if self.ocr_enabled and self.ocr:
            ocr_cfg = detection_cfg.get('ocr', {})
            keywords = ocr_cfg.get('keywords', ["击杀", "KILL"])
            res = self.ocr.find_keywords(frame, keywords, roi=roi_px)
            if res['found']:
                # fuzzy match gives 0-100, we want 0-1.0
                ocr_conf = res['confidence'] / 100.0 if res['confidence'] > 1.0 else res['confidence']
        signals['ocr'] = ocr_conf
        profiler.end('precise_ocr_detection')

        # 2. Template Signal
        profiler.start('precise_template_matching')h gives 0-100, we want 0-1.0
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
        profiler.end('precise_template_matching')

        # 3. YOLO Signal
        profiler.start('precise_yolo_detection')
        if yolo_conf is not None:
            max_yolo_conf = yolo_conf
        else:
            max_yolo_conf = 0.0
            yolo_detections = self.yolo.detect_single(frame)
            for d in yolo_detections:
                if d['name'] == 'kill':
                    max_yolo_conf = max(max_yolo_conf, d['conf'])
        signals['yolo'] = max_yolo_conf
        profiler.end('precise_yolo_detection')

        # 4. Color Signal (使用缓存结果或重新计算)
        profiler.start('precise_color_signal'
            yolo_detections = self.yolo.detect_single(frame)
            for d in yolo_detections:
                if d['name'] == 'kill':
                    max_yolo_conf = max(max_yolo_conf, d['conf'])
        signals['yolo'] = max_yolo_conf

        # 4. Color Signal (使用缓存结果或重新计算)
        if cached_color_pct is not None:
            # 使用缓存的颜色匹配百分比
            color_score = min(cached_color_pct * 50, 1.0)
            signals['color'] = color_score
        else:
            # 重新计算（用于非批处理情况）
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
        profiler.end('precise_color_signal')
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
profiler.start('batch_processing_total')
        
        # Stage 1: Fast Filter all frames with color caching
        profiler.start('batch_stage1_prefilter')
        candidate_indices = []
        color_cache = {}  # 缓存颜色检测结果，避免在 Stage 2 中重复计算
        
        for i, frame in enumerate(frames):
            passed, max_color_pct = self._prefilter_with_result(frame)
            if passed:
                candidate_indices.append(i)
                color_cache[i] = max_color_pct  # 缓存颜色结果
        
        prefilter_time = profiler.end('batch_stage1_prefilter')
        
        if not candidate_indices:
            profiler.end('batch_processing_total')
            logger.debug(f"Batch processing: {len(frames)} frames, 0 candidates, prefilter: {prefilter_time:.3f}s")
            return []

        # Stage 2: Heavy detection for candidates
        profiler.start('batch_stage2_yolo')
        candidate_frames = [frames[i] for i in candidate_indices]
        
        # YOLO batch inference for candidates
        yolo_batch_results = self.yolo.detect_batch(candidate_frames)
        yolo_time = profiler.end('batch_stage2_yolo')
        
        # Stage 3: OCR and Template matching for each candidate
        profiler.start('batch_stage3_precise')
        
        for idx, i in enumerate(candidate_indices):
            frame = frames[i]
            
            # Extract YOLO confidence from batch results
            profiler.start('batch_extract_yolo_results')
            max_yolo_conf = 0.0
            for d in yolo_batch_results[idx]:
                if d['name'] == 'kill':
                    max_yolo_conf = max(max_yolo_conf, d['conf'])
            profiler.end('batch_extract_yolo_results')
            
            # Run other signals (OCR, Template) and combine with batch YOLO
            # 使用缓存的颜色结果避免重复计算
            profiler.start('batch_precise_detect_per_frame')
            cached_color = color_cache.get(i, 0.0)
            signals = self._precise_detect(frame, yolo_conf=max_yolo_conf, cached_color_pct=cached_color)
            profiler.end('batch_precise_detect_per_frame')
            
            # OCR Required logic
            profiler.start('batch_ocr_required_check')
            ocr_cfg = self.config.get('detection', {}).get('ocr', {})
            if ocr_cfg.get('required', False) and signals.get('ocr', 0.0) == 0:
                profiler.end('batch_ocr_required_check')
                continue
            profiler.end('batch_ocr_required_check')

            profiler.start('batch_calculate_confidence')
            final_conf = self._calculate_confidence(signals)
            profiler.end('batch_calculate_confidence')
            
            if final_conf >= self.conf_threshold:
                events.append({
                    "timestamp_ms": timestamps_ms[i],
                    "confidence": final_conf,
                    "type": "kill",
                    "signals": signals # Added for debugging (TASK-027 style)
                })
        
        precise_time = profiler.end('batch_stage3_precise')
        total_time = profiler.end('batch_processing_total')
        
        # 记录批次级统计
        profiler.record('batch_total_frames', len(frames))
        profiler.record('batch_candidate_frames', len(candidate_indices))
        profiler.record('batch_detected_events', len(events))
        
        # 详细的性能日志
        logger.debug(
            f"Batch: {len(frames)} frames, {len(candidate_indices)} candidates, {len(events)} events | "
            f"Times: prefilter={prefilter_time:.3f}s, yolo={yolo_time:.3f}s, "
            f"precise={precise_time:.3f}s
        precise_time = time.time() - precise_start
        total_time = time.time() - batch_start
        
        # 详细的性能日志
        logger.debug(
            f"Batch: {len(frames)} frames, {len(candidate_indices)} candidates, {len(events)} events | "
            f"Times: prefilter={prefilter_time:.3f}s, yolo={yolo_time:.3f}s, "
            f"precise={precise_time:.3f}s (ocr~{ocr_total_time:.3f}s), total={total_time:.3f}s"
        )
                
        return events

