from typing import List

import numpy as np

from src.utils.logger import get_logger
from src.utils.performance_profiler import get_profiler

logger = get_logger(__name__)
profiler = get_profiler()


class BatchDetectionRunner:
    """Run KillDetector's optimized two-stage batch detection flow."""

    def __init__(self, detector):
        self.detector = detector

    def _process_candidates_sequential(
        self,
        frames: List[np.ndarray],
        candidate_indices: List[int],
        timestamps_ms: List[int],
        yolo_batch_results: List[List[dict]],
        color_cache: dict,
    ) -> List[dict]:
        events = []

        for idx, i in enumerate(candidate_indices):
            frame = frames[i]

            profiler.start("batch_extract_yolo_results")
            max_yolo_conf = 0.0
            for detection in yolo_batch_results[idx]:
                if detection["name"] == "kill":
                    max_yolo_conf = max(max_yolo_conf, detection["conf"])
            profiler.end("batch_extract_yolo_results")

            profiler.start("batch_precise_detect_per_frame")
            cached_color = color_cache.get(i, 0.0)
            signals = self.detector._precise_detect(
                frame,
                yolo_conf=max_yolo_conf,
                cached_color_pct=cached_color,
            )
            profiler.end("batch_precise_detect_per_frame")

            profiler.start("batch_ocr_required_check")
            if self.detector.detection_view.ocr.required and signals.get("ocr", 0.0) == 0:
                profiler.end("batch_ocr_required_check")
                continue
            profiler.end("batch_ocr_required_check")

            profiler.start("batch_calculate_confidence")
            rules_result = self.detector._evaluate_rules(
                frame,
                signals,
                cached_color,
                yolo_conf=max_yolo_conf,
            )

            if rules_result is not None:
                if rules_result:
                    events.append(self.detector._build_detection_event(timestamps_ms[i], 1.0, signals))
            else:
                final_conf = self.detector._calculate_confidence(signals)
                if final_conf >= self.detector.conf_threshold:
                    events.append(self.detector._build_detection_event(timestamps_ms[i], final_conf, signals))
            profiler.end("batch_calculate_confidence")

        return events

    def process(self, frames: List[np.ndarray], timestamps_ms: List[int]) -> List[dict]:
        events = []
        profiler.start("batch_processing_total")

        profiler.start("batch_stage1_prefilter")
        candidate_indices = []
        color_cache = {}

        for i, frame in enumerate(frames):
            passed, max_color_pct = self.detector._prefilter_with_result(frame)
            if passed:
                candidate_indices.append(i)
                color_cache[i] = max_color_pct

        prefilter_time = profiler.end("batch_stage1_prefilter")

        if not candidate_indices:
            profiler.end("batch_processing_total")
            logger.debug(f"Batch processing: {len(frames)} frames, 0 candidates, prefilter: {prefilter_time:.3f}s")
            return []

        profiler.start("batch_stage2_yolo")
        candidate_frames = [frames[i] for i in candidate_indices]
        yolo_batch_results = self.detector.yolo.detect_batch(candidate_frames)
        yolo_time = profiler.end("batch_stage2_yolo")

        profiler.start("batch_stage3_precise")
        events.extend(
            self._process_candidates_sequential(
                frames,
                candidate_indices,
                timestamps_ms,
                yolo_batch_results,
                color_cache,
            )
        )

        precise_time = profiler.end("batch_stage3_precise")
        total_time = profiler.end("batch_processing_total")

        profiler.record("batch_total_frames", len(frames))
        profiler.record("batch_candidate_frames", len(candidate_indices))
        profiler.record("batch_detected_events", len(events))

        logger.debug(
            f"Batch: {len(frames)} frames, {len(candidate_indices)} candidates, {len(events)} events | "
            f"Mode: sequential | "
            f"Times: prefilter={prefilter_time:.3f}s, yolo={yolo_time:.3f}s, "
            f"precise={precise_time:.3f}s, total={total_time:.3f}s"
        )

        return events

