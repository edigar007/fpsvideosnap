import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type

import cv2

from src.ai.kill_detector import KillDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.timestamp_recorder import TimestampRecorder
from src.ai.yolo_detector import YoloDetector
from src.config.settings import AppSettings
from src.debug.detection_debugger import DetectionDebugger
from src.pipeline.context import PipelineContext
from src.utils.logger import get_logger
from src.utils.performance_profiler import get_profiler
from src.utils.progress import create_progress_bar

logger = get_logger(__name__)
profiler = get_profiler()


@dataclass
class DetectionStageResult:
    events: List[Dict[str, Any]]
    detection_json_path: str
    debug_video_path: Optional[str] = None


def _parse_frame_timestamp_ms(frame_path: str) -> int:
    try:
        basename = os.path.basename(frame_path)
        m = re.search(r"frame_(\d+)", basename)
        if m:
            return int(m.group(1))
        logger.warning(f"Failed to parse timestamp from frame name: {frame_path}")
        return 0
    except (IndexError, ValueError):
        logger.warning(f"Failed to parse timestamp from frame name: {frame_path}")
        return 0


def run_detection_stage(
    context: PipelineContext,
    frames: List[str],
    model_manager: Any,
    load_templates: Callable[[OpenCVMatcher], int],
    progress_desc: str,
    yolo_detector_cls: Type[YoloDetector] = YoloDetector,
    opencv_matcher_cls: Type[OpenCVMatcher] = OpenCVMatcher,
    kill_detector_cls: Type[KillDetector] = KillDetector,
    timestamp_recorder_cls: Type[TimestampRecorder] = TimestampRecorder,
    progress_factory: Callable[..., Any] = create_progress_bar,
    detection_debugger_cls: Type[DetectionDebugger] = DetectionDebugger,
) -> DetectionStageResult:
    profiler.start("stage_detection_total")
    kill_detector = None

    try:
        profiler.start("stage_detection_setup")
        settings = AppSettings.from_config(context.config)
        detection_cfg = context.config.get("detection", {})
        model_manager.model_path = settings.detection.model_path
        yolo_model = model_manager.load_model()

        yolo_detector = yolo_detector_cls(yolo_model, batch_size=settings.ai.batch_size)
        opencv_matcher = opencv_matcher_cls(context.config)
        load_templates(opencv_matcher)

        kill_detector = kill_detector_cls(yolo_detector, opencv_matcher, context.config)
        profiler.end("stage_detection_setup")

        logger.debug("KillDetector initialized with:")
        logger.debug(f"  Confidence threshold: {detection_cfg.get('confidence_threshold', 0.5)}")
        logger.debug(f"  ROI: {detection_cfg.get('killfeed_roi', [0, 0, 1, 1])}")
        logger.debug(f"  Colors: {list(detection_cfg.get('colors', {}).keys())}")
        logger.debug(f"  OCR enabled: {detection_cfg.get('ocr', {}).get('enabled', False)}")
        logger.debug(f"  Prefilter threshold: {detection_cfg.get('prefilter', {}).get('color_threshold', 0.01)}")

        history_dir = context.config.get("global", {}).get("history_dir", "history")
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(history_dir, f"run_{run_timestamp}")
        os.makedirs(run_dir, exist_ok=True)

        detection_json_path = os.path.join(run_dir, "detections.json")
        timestamp_recorder = timestamp_recorder_cls(detection_json_path)

        detected_events: List[Dict[str, Any]] = []
        pbar = progress_factory(total=len(frames), desc=progress_desc)
        chunk_size = settings.detection.chunk_size

        profiler.start("stage_detection_processing")
        for i in range(0, len(frames), chunk_size):
            chunk_paths = frames[i:i + chunk_size]
            chunk_frames = []
            chunk_timestamps = []

            profiler.start("stage_detection_read_frames")
            for frame_path in chunk_paths:
                frame = cv2.imread(frame_path)
                if frame is not None:
                    chunk_frames.append(frame)
                    chunk_timestamps.append(_parse_frame_timestamp_ms(frame_path))
                else:
                    logger.warning(f"Failed to read frame: {frame_path}")
            profiler.end("stage_detection_read_frames")

            if chunk_frames:
                batch_events = kill_detector.process_video_batch(chunk_frames, chunk_timestamps)
                detected_events.extend(batch_events)

                if batch_events:
                    logger.debug(f"Batch {i // chunk_size + 1}: Detected {len(batch_events)} events")
                    for event in batch_events[:3]:
                        logger.debug(
                            f"  Event: ts={event.get('timestamp_ms')}ms, "
                            f"conf={event.get('confidence', 0):.3f}"
                        )

                profiler.start("stage_detection_record_events")
                for event in batch_events:
                    timestamp_recorder.record_event(
                        timestamp_ms=event.get("timestamp_ms", 0),
                        event_type="kill",
                        confidence=event.get("confidence", 0.0),
                        meta={
                            "signals": event.get("signals", {}),
                            "frame_path": event.get("frame_path", ""),
                        },
                    )
                profiler.end("stage_detection_record_events")

            pbar.update(len(chunk_paths))
            if context.progress_callback:
                context.progress_callback(
                    {
                        "stage": "detection",
                        "processed": min(i + len(chunk_paths), len(frames)),
                        "total": len(frames),
                        "detected": len(detected_events),
                    }
                )

        profiler.end("stage_detection_processing")
        pbar.close()

        profiler.start("stage_detection_save_results")
        timestamp_recorder.save()
        logger.info(f"Detection events saved to {detection_json_path}")
        profiler.end("stage_detection_save_results")
        profiler.end("stage_detection_total")

        _log_detection_summary(frames, detected_events)
        debug_video_path = _write_debug_visuals(
            context,
            frames,
            detected_events,
            detection_debugger_cls,
        )

        return DetectionStageResult(
            events=detected_events,
            detection_json_path=detection_json_path,
            debug_video_path=debug_video_path,
        )
    finally:
        if kill_detector is not None:
            try:
                if getattr(kill_detector, "ocr", None) is not None:
                    kill_detector.ocr.close()
            except Exception as exc:
                logger.warning(f"Failed to close OCR resources: {exc}")


def _log_detection_summary(frames: List[str], detected_events: List[Dict[str, Any]]) -> None:
    logger.info("[bold]Detection Summary:[/bold]")
    logger.info(f"  Total frames processed: {len(frames)}")
    logger.info(f"  Total events detected: {len(detected_events)}")

    if detected_events:
        avg_conf = sum(e.get("confidence", 0) for e in detected_events) / len(detected_events)
        logger.info(f"  Average confidence: {avg_conf:.3f}")
        logger.info(
            f"  First event: ts={detected_events[0].get('timestamp_ms')}ms, "
            f"conf={detected_events[0].get('confidence', 0):.3f}"
        )
        logger.info(
            f"  Last event: ts={detected_events[-1].get('timestamp_ms')}ms, "
            f"conf={detected_events[-1].get('confidence', 0):.3f}"
        )


def _write_debug_visuals(
    context: PipelineContext,
    frames: List[str],
    detected_events: List[Dict[str, Any]],
    detection_debugger_cls: Type[DetectionDebugger],
) -> Optional[str]:
    if not context.config.get("global", {}).get("debug_visual", False):
        return None

    debug_viz_dir = os.path.join(context.temp_dir, "debug_viz")
    os.makedirs(debug_viz_dir, exist_ok=True)
    debugger = detection_debugger_cls(context.config)

    for event in detected_events:
        ts = event.get("timestamp_ms", 0)
        for frame_path in frames:
            if f"_{ts}." in frame_path:
                frame = cv2.imread(frame_path)
                if frame is not None:
                    debug_path = os.path.join(debug_viz_dir, f"kill_{ts}_debug.jpg")
                    debugger.save_debug_frame(frame, event, debug_path)
                break

    debug_video_path = os.path.join(debug_viz_dir, "detection_debug.mp4")
    debugger.generate_debug_overlay(context.video_path, detected_events, debug_video_path)
    logger.info(f"Visual debug evidence saved to {debug_viz_dir}")
    return debug_video_path
