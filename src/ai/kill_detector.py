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
        self.roi = list(self.detection_view.killfeed_roi)
        self.colors = dict(self.detection_view.colors.raw)
        
        # OCR Initialization (TASK-021)
        ocr_cfg = self.detection_view.ocr
        self.ocr_enabled = ocr_cfg.enabled
        self.ocr = ocr_detector
        if self.ocr_enabled and self.ocr is None:
            self.ocr = OCRDetector(
                lang=ocr_cfg.lang,
                use_gpu=ocr_cfg.use_gpu
            )
        
        # Prefilter settings (TASK-022)
        prefilter_cfg = self.detection_view.prefilter
        self.prefilter_enabled = prefilter_cfg.enabled
        self.color_threshold = prefilter_cfg.color_threshold
        
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

        复用 DetectionSignalExtractor.compute 的统一信号计算管线，消除与
        rule_engine 路径的重复实现（原先手动调用四个子 extractor）。

        Args:
            cached_color_pct: 如果提供，则使用缓存的颜色检测结果，避免重复计算
        """
        profiler.start('precise_detection')
        try:
            return self.signal_extractor.compute(
                frame,
                self.yolo,
                self.cv,
                self.ocr,
                self.detection_view,
                self.roi,
                cached_color_pct=cached_color_pct,
                yolo_conf=yolo_conf,
            )
        finally:
            profiler.end('precise_detection')

    def _analyze_candidate(
        self,
        frame: np.ndarray,
        timestamp_ms: int,
        yolo_conf: Optional[float] = None,
        cached_color_pct: Optional[float] = None,
    ) -> tuple:
        """
        Shared per-frame decision flow used by both process_frame and the batch runner.

        Runs precise detection, applies the OCR-required gate, then evaluates rules
        mode (confidence 1.0/0.0) or falls back to legacy weighted confidence vs
        threshold. Returns (signals, confidence, event_or_None) where confidence is
        the value to report (rules mode 1.0/0.0, OCR-gate 0.0, legacy weighted score)
        and event is a detection event dict when the candidate is a kill, else None.
        """
        precise_kwargs = {"cached_color_pct": cached_color_pct}
        if yolo_conf is not None:
            precise_kwargs["yolo_conf"] = yolo_conf
        signals = self._precise_detect(frame, **precise_kwargs)

        # OCR Required logic (TASK-026)
        if self.detection_view.ocr.required and signals.get('ocr', 0.0) == 0:
            return signals, 0.0, None

        # Rules mode OR legacy weighted scoring
        rules_result = self._evaluate_rules(frame, signals, cached_color_pct, yolo_conf=yolo_conf)

        if rules_result is not None:
            # Rules mode: confidence is 1.0 or 0.0
            if rules_result:
                return signals, 1.0, self._build_detection_event(timestamp_ms, 1.0, signals)
            return signals, 0.0, None

        # Legacy mode: weighted scoring vs threshold
        final_conf = self._calculate_confidence(signals)
        if final_conf >= self.conf_threshold:
            return signals, final_conf, self._build_detection_event(timestamp_ms, final_conf, signals)
        return signals, final_conf, None

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

        # Step 2+: Shared candidate analysis (precise detect -> OCR-required ->
        # rules/legacy decision -> event build)
        signals, confidence, event = self._analyze_candidate(frame, 0, cached_color_pct=cached_color_pct)
        results["signals"] = signals
        results["confidence"] = confidence
        if event is not None:
            results["is_kill"] = True

        return results

    def process_video_batch(self, frames: List[np.ndarray], timestamps_ms: List[int]) -> List[dict]:
        """
        Processes a batch of frames and returns a list of kill events. (TASK-028)
        Optimized using two-stage flow with color result caching.
        """
        return self.batch_runner.process(frames, timestamps_ms)

