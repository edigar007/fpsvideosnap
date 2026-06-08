from typing import List, Dict, Optional
import numpy as np
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.ocr_detector import OCRDetector
from src.ai.batch_detection_runner import BatchDetectionRunner
from src.ai.color_utils import get_hsv_bounds
from src.ai.events import DetectionEvent
from src.ai.rule_engine import DetectionRuleEngine
from src.ai.signal_extractors import ColorSignalExtractor, DetectionSignalExtractor
from src.ai.signal_fusion import WeightedSignalFusion
from src.ai.signals import SignalResult
from src.config.detection_view import DetectionConfigView
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
    def __init__(
        self,
        yolo_detector: YoloDetector,
        opencv_matcher: OpenCVMatcher,
        game_config: dict,
        ocr_detector: Optional[OCRDetector] = None,
    ):
        self.yolo = yolo_detector
        self.cv = opencv_matcher
        self.config = game_config
        
        detection_cfg = game_config.get('detection', {})
        self.detection_view = DetectionConfigView.from_config(detection_cfg)
        
        # Detection thresholds from config
        self.conf_threshold = self.detection_view.confidence_threshold
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
        self.prefilter_enabled = prefilter_cfg.get('enabled', True)
        self.color_threshold = prefilter_cfg.get('color_threshold', 0.01)
        
        # Weights (TASK-021)
        self.weights = dict(self.detection_view.weights)
        
        # OR-of-AND Rules mode
        self.signal_extractor = DetectionSignalExtractor()
        self.color_extractor = ColorSignalExtractor()
        self.signal_fusion = WeightedSignalFusion()
        self.rule_engine = DetectionRuleEngine(self.detection_view, templates_loaded=lambda: bool(self.cv.templates))
        self.batch_runner = BatchDetectionRunner(self)
        
        # Multi-threading settings
        # NOTE: 多线程并行候选帧处理已移除。
        # 经验上此处线程容易被 OCR/OpenCV 锁与 GIL 抵消收益，且 GPU 推理本身已 batch 化。

    def _build_detection_event(
        self,
        timestamp_ms: int,
        confidence: float,
        signals: Dict,
    ) -> dict:
        return DetectionEvent(
            timestamp_ms=timestamp_ms,
            confidence=confidence,
            type="kill",
            signals=SignalResult.from_dict(signals).as_dict(),
        ).to_dict()

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
        try:
            return self.color_extractor.prefilter(
                frame,
                self.cv,
                self.colors,
                self.roi,
                self.color_threshold,
                enabled=self.prefilter_enabled,
            )
        finally:
            profiler.end('prefilter_color_detection')

    def _get_color_bounds(self, color_cfg: dict) -> tuple:
        """
        Return HSV bounds for color detection.
        Explicit lower/upper ranges are treated as final bounds; tolerance is only
        applied when config stores a center HSV value.
        """
        return get_hsv_bounds(color_cfg)

    def _calculate_confidence(self, signals: Dict) -> float:
        """
        Calculate weighted confidence score. (TASK-025)
        Redistributes weights if certain signals are not used (e.g. OCR disabled).
        """
        return self.signal_fusion.calculate(
            signals,
            self.weights,
            ocr_active=bool(self.ocr_enabled and self.ocr),
            templates_active=bool(self.cv.templates),
        )

    def _evaluate_rules(
        self,
        frame: np.ndarray,
        signals: Dict,
        cached_color_pct: Optional[float] = None,
        yolo_conf: Optional[float] = None,
    ) -> Optional[bool]:
        """
        Evaluate OR-of-AND rules. Rules without signal-affecting overrides reuse
        the already-computed precise signals; per-rule signal computation is only
        used when overrides change ROI/OCR/template/color/prefilter behavior.
        
        Returns True if ANY rule matches, False if rules exist but none match, None if no rules.
        """
        return self.rule_engine.evaluate(
            frame,
            signals,
            compute_signals=self._compute_signals_for_config,
            cached_color_pct=cached_color_pct,
            yolo_conf=yolo_conf,
        )

    def _compute_signals_for_config(
        self,
        frame: np.ndarray,
        detection_cfg: dict,
        cached_color_pct: Optional[float] = None,
        yolo_conf: Optional[float] = None,
    ) -> dict:
        return self.signal_extractor.compute(
            frame,
            self.yolo,
            self.cv,
            self.ocr,
            detection_cfg,
            self.roi,
            cached_color_pct=cached_color_pct,
            yolo_conf=yolo_conf,
        )

    def _precise_detect(
        self,
        frame: np.ndarray,
        yolo_conf: Optional[float] = None,
        cached_color_pct: Optional[float] = None,
    ) -> Dict:
        """
        Runs heavy detection signals (OCR, Template, YOLO). (TASK-023)
        
        Args:
            cached_color_pct: 如果提供，则使用缓存的颜色检测结果，避免重复计算
        """
        detection_cfg = self.config.get('detection', {})

        # 1. OCR Signal
        profiler.start('precise_ocr_detection')
        ocr_conf = self.signal_extractor.ocr.compute(frame, self.ocr, detection_cfg, self.roi)
        profiler.end('precise_ocr_detection')

        # 2. Template Signal
        profiler.start('precise_template_matching')
        template_conf = self.signal_extractor.template.compute(frame, self.cv, detection_cfg, self.roi)
        profiler.end('precise_template_matching')

        # 3. YOLO Signal
        profiler.start('precise_yolo_detection')
        max_yolo_conf = self.signal_extractor.yolo.compute(frame, self.yolo, yolo_conf=yolo_conf)
        profiler.end('precise_yolo_detection')

        # 4. Color Signal (使用缓存结果或重新计算)
        profiler.start('precise_color_signal')
        color_conf = self.signal_extractor.color.compute(
            frame,
            self.cv,
            detection_cfg,
            self.roi,
            cached_color_pct=cached_color_pct,
        )
        profiler.end('precise_color_signal')

        return SignalResult.from_dict({
            "ocr": ocr_conf,
            "template": template_conf,
            "yolo": max_yolo_conf,
            "color": color_conf,
        }).as_dict()

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
        rules_result = self._evaluate_rules(frame, signals, cached_color_pct)
        
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

    def process_video_batch(self, frames: List[np.ndarray], timestamps_ms: List[int]) -> List[dict]:
        """
        Processes a batch of frames and returns a list of kill events. (TASK-028)
        Optimized using two-stage flow with color result caching.
        """
        return self.batch_runner.process(frames, timestamps_ms)

