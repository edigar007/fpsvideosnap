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
        
        # OR-of-AND Rules mode
        self.rules = detection_cfg.get('rules', [])
        
        # Multi-threading settings
        # NOTE: 多线程并行候选帧处理已移除。
        # 经验上此处线程容易被 OCR/OpenCV 锁与 GIL 抵消收益，且 GPU 推理本身已 batch 化。

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

    def _get_signal_booleans(self, signals: Dict, cached_color_pct: Optional[float] = None) -> Dict[str, bool]:
        """
        Convert signal values to boolean for rules evaluation.
        
        Signal True/False logic:
        - ocr: signals['ocr'] > 0
        - yolo: signals['yolo'] > 0
        - color: max_color_pct >= self.color_threshold
        - template: any template score >= per-template threshold (default 0.8)
        """
        detection_cfg = self.config.get('detection', {})
        
        # OCR: True if any keyword was found
        ocr_bool = signals.get('ocr', 0.0) > 0
        
        # YOLO: True if any kill detection
        yolo_bool = signals.get('yolo', 0.0) > 0
        
        # Color: Use cached_color_pct if available, otherwise check if color signal is positive
        if cached_color_pct is not None:
            color_bool = cached_color_pct >= self.color_threshold
        else:
            # Fallback: if color signal > 0, consider it True
            # (color signal is already thresholded during prefilter)
            color_bool = signals.get('color', 0.0) > 0
        
        # Template: Check if any template passes its configured threshold
        template_bool = False
        if self.cv.templates:
            template_cfg = detection_cfg.get('templates', {})
            for t_name in self.cv.templates:
                # Get per-template threshold, default 0.8
                t_threshold = 0.8
                if t_name in template_cfg and isinstance(template_cfg[t_name], dict):
                    t_threshold = template_cfg[t_name].get('threshold', 0.8)
                
                # Get the template score from the last match
                # Note: signals['template'] is max score, but for per-template threshold
                # we need to check individual scores. For simplicity, if signals['template'] >= min threshold
                # among all templates, we consider it True.
                # For accurate per-template checking, we'd need to store individual scores.
                # Using a simplified approach: template passes if max_score >= configured threshold for that template
                if signals.get('template', 0.0) >= t_threshold:
                    template_bool = True
                    break
        
        return {
            'ocr': ocr_bool,
            'yolo': yolo_bool,
            'color': color_bool,
            'template': template_bool
        }

    def _merge_detection_config(self, rule: dict) -> dict:
        """
        Merge rule.detection_overrides with global detection config.
        Rule overrides take precedence. Uses deep merge for nested dicts.
        """
        detection_cfg = self.config.get('detection', {}).copy()
        overrides = rule.get('detection_overrides', {})
        
        if not overrides:
            return detection_cfg
        
        # Deep merge overrides into detection_cfg
        for key, value in overrides.items():
            if key in detection_cfg and isinstance(detection_cfg[key], dict) and isinstance(value, dict):
                # Deep merge nested dicts (e.g., 'ocr', 'colors')
                detection_cfg[key] = {**detection_cfg[key], **value}
            else:
                detection_cfg[key] = value
        
        return detection_cfg

    def _compute_rule_signals(self, frame: np.ndarray, detection_cfg: dict, cached_color_pct: Optional[float] = None, yolo_conf: Optional[float] = None) -> dict:
        """
        Compute detection signals using the provided detection config.
        Similar to _precise_detect but uses provided config instead of self.config.
        """
        signals = {}
        
        # Get ROI from config
        roi = detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
        h, w = frame.shape[:2]
        roi_px = [int(roi[0] * w), int(roi[1] * h), int(roi[2] * w), int(roi[3] * h)]
        
        # OCR signal
        ocr_cfg = detection_cfg.get('ocr', {})
        ocr_enabled = ocr_cfg.get('enabled', False)
        if ocr_enabled and self.ocr:
            keywords = ocr_cfg.get('keywords', ["击杀", "KILL"])
            res = self.ocr.find_keywords(frame, keywords, roi=roi_px)
            if res['found']:
                # fuzzy match gives 0-100, we want 0-1.0
                signals['ocr'] = res['confidence'] / 100.0 if res['confidence'] > 1.0 else res['confidence']
            else:
                signals['ocr'] = 0.0
        else:
            signals['ocr'] = 0.0
        
        # Template signal
        max_template_conf = 0.0
        templates_cfg = detection_cfg.get('templates', {})
        if not templates_cfg:
            # Fallback to all loaded templates if not specified
            for t_name in self.cv.templates:
                _, score = self.cv.match_template(frame, t_name, roi=roi)
                max_template_conf = max(max_template_conf, score)
        else:
            for t_name in templates_cfg:
                if t_name in self.cv.templates:
                    _, score = self.cv.match_template(frame, t_name, roi=roi)
                    max_template_conf = max(max_template_conf, score)
        signals['template'] = max_template_conf
        
        # Color signal
        colors_cfg = detection_cfg.get('colors', {})
        if cached_color_pct is not None and not detection_cfg.get('_force_color_recompute'):
            signals['color'] = min(cached_color_pct * 50, 1.0)
        else:
            max_color_conf = 0.0
            for color_name, color_cfg in colors_cfg.items():
                hsv_lower = color_cfg.get('hsv_lower', color_cfg.get('lower'))
                hsv_upper = color_cfg.get('hsv_upper', color_cfg.get('upper'))
                if hsv_lower and hsv_upper:
                    tolerance = color_cfg.get('tolerance', 0)
                    if tolerance > 0:
                        hsv_lower = [max(0, hsv_lower[0] - tolerance), max(0, hsv_lower[1] - tolerance), max(0, hsv_lower[2] - tolerance)]
                        hsv_upper = [min(179, hsv_upper[0] + tolerance), min(255, hsv_upper[1] + tolerance), min(255, hsv_upper[2] + tolerance)]
                    match_percent = self.cv.detect_color(frame, hsv_lower, hsv_upper, roi=roi)
                    max_color_conf = max(max_color_conf, min(match_percent * 50, 1.0))
            signals['color'] = max_color_conf
        
        # YOLO signal (YOLO uses full frame, not ROI, so no config dependency)
        if yolo_conf is not None:
            signals['yolo'] = yolo_conf
        else:
            yolo_detections = self.yolo.detect_single(frame)
            max_yolo_conf = max((d['conf'] for d in yolo_detections if d['name'] == 'kill'), default=0.0)
            signals['yolo'] = max_yolo_conf
        
        return signals

    def _get_signal_booleans_for_config(self, signals: dict, detection_cfg: dict, cached_color_pct: Optional[float] = None) -> dict:
        """Convert signals to booleans using the provided detection config."""
        ocr_bool = signals.get('ocr', 0.0) > 0
        yolo_bool = signals.get('yolo', 0.0) > 0
        
        prefilter_cfg = detection_cfg.get('prefilter', {})
        color_threshold = prefilter_cfg.get('color_threshold', 0.01)
        
        if cached_color_pct is not None:
            color_bool = cached_color_pct >= color_threshold
        else:
            color_bool = signals.get('color', 0.0) > 0
        
        template_bool = False
        templates_cfg = detection_cfg.get('templates', {})
        if not templates_cfg:
            # Check all loaded templates with default 0.8
            if signals.get('template', 0.0) >= 0.8:
                template_bool = True
        else:
            for t_name, t_cfg in templates_cfg.items():
                t_threshold = t_cfg.get('threshold', 0.8) if isinstance(t_cfg, dict) else 0.8
                if signals.get('template', 0.0) >= t_threshold:
                    template_bool = True
                    break
        
        return {
            'ocr': ocr_bool,
            'yolo': yolo_bool,
            'color': color_bool,
            'template': template_bool
        }

    def _evaluate_rules(self, frame: np.ndarray, cached_color_pct: Optional[float] = None, yolo_conf: Optional[float] = None) -> Optional[bool]:
        """
        Evaluate OR-of-AND rules with per-rule detection_overrides.
        
        For each enabled rule:
        1. Compute effective detection config (global + rule overrides)
        2. Run signal detection with that config
        3. Convert to booleans and check if rule is satisfied
        
        Returns True if ANY rule matches, False if rules exist but none match, None if no rules.
        """
        if not self.rules:
            return None
        
        enabled_rules = [r for r in self.rules if r.get('enabled', True)]
        if not enabled_rules:
            return False
        
        for rule in enabled_rules:
            # Get effective detection config for this rule
            effective_cfg = self._merge_detection_config(rule)
            
            # Compute signals with rule-specific config
            signals = self._compute_rule_signals(frame, effective_cfg, cached_color_pct, yolo_conf)
            
            # Convert to booleans
            signal_booleans = self._get_signal_booleans_for_config(signals, effective_cfg, cached_color_pct)
            
            # Check if rule is satisfied (AND of required signals)
            require = rule.get('require', [])
            if require and all(signal_booleans.get(sig, False) for sig in require):
                logger.debug(f"Rule matched: {rule.get('name', 'unnamed')}")
                return True
        
        return False

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
        x, y, w_roi, h_roi = self.roi
        roi_px = [int(x * w), int(y * h), int(w_roi * w), int(h_roi * h)]

        # 1. OCR Signal
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
        profiler.start('precise_template_matching')
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
        profiler.start('precise_color_signal')
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
                        hsv_upper = [min(179, hsv_upper[0] + tolerance), min(255, hsv_upper[1] + tolerance), min(255, hsv_upper[2] + tolerance)]
                    
                    match_percent = self.cv.detect_color(frame, hsv_lower, hsv_upper, roi=self.roi)
                    # Boost confidence if color pattern is found
                    color_score = min(match_percent * 50, 1.0) 
                    max_color_conf = max(max_color_conf, color_score)
            signals['color'] = max_color_conf
        profiler.end('precise_color_signal')

        return signals

    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Analyzes a single frame and returns detection results. (TASK-024, TASK-026, TASK-027)
        Supports OR-of-AND rules mode when detection.rules is configured.
        """
        results = {
            "is_kill": False,
            "confidence": 0.0,
            "signals": {}
        }

        # Step 1: Pre-filter (Fast) with result caching for color
        passed, cached_color_pct = self._prefilter_with_result(frame)
        if not passed:
            return results

        # Step 2: Precise detection (Heavy)
        signals = self._precise_detect(frame, cached_color_pct=cached_color_pct)
        results["signals"] = signals

        # Step 3: OCR Required logic (TASK-026)
        ocr_cfg = self.config.get('detection', {}).get('ocr', {})
        if ocr_cfg.get('required', False) and signals.get('ocr', 0.0) == 0:
            results["is_kill"] = False
            results["confidence"] = 0.0
            return results

        # Step 4: Rules mode OR legacy weighted scoring
        rules_result = self._evaluate_rules(frame, cached_color_pct)
        
        if rules_result is not None:
            # Rules mode: is_kill from rules, confidence is 1.0 or 0.0
            results["is_kill"] = rules_result
            results["confidence"] = 1.0 if rules_result else 0.0
        else:
            # Legacy mode: weighted scoring
            final_conf = self._calculate_confidence(signals)
            results["confidence"] = final_conf
            results["is_kill"] = final_conf >= self.conf_threshold

        return results

    def _process_candidates_sequential(self, frames: List[np.ndarray],
                                      candidate_indices: List[int],
                                      timestamps_ms: List[int],
                                      yolo_batch_results: List[List[dict]],
                                      color_cache: dict) -> List[dict]:
        """
        单线程顺序处理候选帧（原始实现）
        Supports OR-of-AND rules mode when detection.rules is configured.
        """
        events = []
        
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

            # Rules mode OR legacy weighted scoring
            profiler.start('batch_calculate_confidence')
            rules_result = self._evaluate_rules(frame, cached_color, yolo_conf=max_yolo_conf)
            
            if rules_result is not None:
                # Rules mode
                if rules_result:
                    events.append({
                        "timestamp_ms": timestamps_ms[i],
                        "confidence": 1.0,
                        "type": "kill",
                        "signals": signals
                    })
                # If rules_result is False, don't append (no match)
            else:
                # Legacy mode: weighted scoring
                final_conf = self._calculate_confidence(signals)
                if final_conf >= self.conf_threshold:
                    events.append({
                        "timestamp_ms": timestamps_ms[i],
                        "confidence": final_conf,
                        "type": "kill",
                        "signals": signals
                    })
            profiler.end('batch_calculate_confidence')
        
        return events

    def process_video_batch(self, frames: List[np.ndarray], timestamps_ms: List[int]) -> List[dict]:
        """
        Processes a batch of frames and returns a list of kill events. (TASK-028)
        Optimized using two-stage flow with color result caching.
        """
        events = []
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

        # 单线程顺序处理（推荐/默认）
        events.extend(self._process_candidates_sequential(
            frames, candidate_indices, timestamps_ms,
            yolo_batch_results, color_cache
        ))
        
        precise_time = profiler.end('batch_stage3_precise')
        total_time = profiler.end('batch_processing_total')
        
        # 记录批次级统计
        profiler.record('batch_total_frames', len(frames))
        profiler.record('batch_candidate_frames', len(candidate_indices))
        profiler.record('batch_detected_events', len(events))
        
        # 详细的性能日志
        threading_mode = "sequential"
        logger.debug(
            f"Batch: {len(frames)} frames, {len(candidate_indices)} candidates, {len(events)} events | "
            f"Mode: {threading_mode} | "
            f"Times: prefilter={prefilter_time:.3f}s, yolo={yolo_time:.3f}s, "
            f"precise={precise_time:.3f}s, total={total_time:.3f}s"
        )
                
        return events

