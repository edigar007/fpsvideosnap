import logging
import os
import time
import threading
from queue import Full
from typing import List

from src.pipeline.results import CLIPS, EVENTS, FRAMES
from src.tools.dashboard.progress import (
    PIPELINE_STAGES,
    completed_stage_map,
    make_output_file,
    pending_stage_map,
)

logger = logging.getLogger(__name__)


class ErrorLogHandler(logging.Handler):
    """Forward warnings and errors from a worker process into the dashboard queue."""

    def __init__(self, progress_queue):
        super().__init__()
        self.progress_queue = progress_queue

    def emit(self, record):
        if record.levelno < logging.WARNING:
            return
        try:
            self.progress_queue.put_nowait(
                {
                    "type": "error",
                    "level": record.levelname,
                    "message": self.format(record),
                    "time": time.strftime("%H:%M:%S"),
                }
            )
        except Full:
            logger.debug("Dashboard progress queue full while forwarding log record")


def _send_progress(progress_queue, progress_data: dict) -> None:
    try:
        progress_queue.put_nowait({"type": "progress", **progress_data})
    except Full:
        logger.debug("Dashboard progress queue full while sending progress update")


def _send_error(progress_queue, message: str) -> None:
    try:
        progress_queue.put_nowait(
            {
                "type": "error",
                "message": message,
                "time": time.strftime("%H:%M:%S"),
            }
        )
    except Full:
        logger.debug("Dashboard progress queue full while sending error update")


def _configure_worker_logging(progress_queue) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []

    handler = ErrorLogHandler(progress_queue)
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(handler)

    fps_logger = logging.getLogger("fps_video_snap")
    fps_logger.setLevel(logging.DEBUG)
    fps_logger.handlers = []
    fps_logger.addHandler(handler)


def _stage_statuses(monitored_pipeline, stage_status_cls) -> tuple[dict, str]:
    stage_statuses = {}
    current_stage = ""
    for stage_name, _ in PIPELINE_STAGES:
        if stage_name not in monitored_pipeline.stages:
            continue

        status = monitored_pipeline.stages[stage_name].status
        if status == stage_status_cls.SUCCESS:
            stage_statuses[stage_name] = "success"
        elif status == stage_status_cls.RUNNING:
            stage_statuses[stage_name] = "running"
            current_stage = stage_name
        elif status == stage_status_cls.FAILED:
            stage_statuses[stage_name] = "failed"
        elif status == stage_status_cls.SKIPPED:
            stage_statuses[stage_name] = "skipped"
        else:
            stage_statuses[stage_name] = "pending"

    return stage_statuses, current_stage


def _monitor_pipeline(
    pipeline,
    stage_status_cls,
    progress_queue,
    stop_event,
    video_name: str,
    video_idx: int,
    total_videos: int,
) -> None:
    while not stop_event.is_set():
        try:
            stage_statuses, current_stage = _stage_statuses(pipeline, stage_status_cls)
            frames = pipeline.results.get(FRAMES, [])
            events = pipeline.results.get(EVENTS, [])
            clips = pipeline.results.get(CLIPS, [])
            detection_total = len(frames) if frames else 0
            progress_payload = {
                "current_video": video_name,
                "current_video_index": video_idx + 1,
                "total_videos": total_videos,
                "current_stage": current_stage,
                "stages": stage_statuses,
                "detected_kills": len(events),
                "extracted_clips": len(clips),
            }
            if current_stage != "detection":
                progress_payload["detection_total"] = detection_total
                progress_payload["detection_progress"] = (
                    detection_total if stage_statuses.get("detection") == "success" else 0
                )
            _send_progress(progress_queue, progress_payload)
        except Exception as exc:
            logger.debug("Dashboard pipeline monitor update failed: %s", exc, exc_info=True)

        time.sleep(0.5)


def run_processing_task(videos: List[str], game: str, progress_queue, result_queue, cancel_event):
    """
    Worker function that runs in a separate process.
    Executes the video processing pipeline with progress reporting.
    """
    _configure_worker_logging(progress_queue)

    try:
        _send_progress(
            progress_queue,
            {
                "current_video": "",
                "current_video_index": 0,
                "total_videos": len(videos),
                "current_stage": "initializing",
                "stages": pending_stage_map(),
                "detection_progress": 0,
                "detection_total": 0,
                "detected_kills": 0,
                "extracted_clips": 0,
            },
        )

        if cancel_event.is_set():
            result_queue.put({"success": False, "error": "Cancelled"})
            return

        from src.config.config_loader import get_config
        from src.pipeline.pipeline import Pipeline, StageStatus

        _send_progress(progress_queue, {"current_stage": "loading_config"})
        config = get_config(game_name=game)

        if cancel_event.is_set():
            result_queue.put({"success": False, "error": "Cancelled"})
            return

        all_clips = []
        output_files = []
        video_results = []

        for video_idx, video_path in enumerate(videos):
            if cancel_event.is_set():
                result_queue.put({"success": False, "error": "Cancelled"})
                return

            video_name = os.path.basename(video_path)

            _send_progress(
                progress_queue,
                {
                    "current_video": video_name,
                    "current_video_index": video_idx + 1,
                    "total_videos": len(videos),
                    "current_stage": "metadata",
                    "stages": pending_stage_map(),
                    "detection_progress": 0,
                    "detection_total": 0,
                    "detected_kills": 0,
                    "extracted_clips": 0,
                },
            )

            def send_pipeline_progress(
                event: dict,
                progress_video_name: str = video_name,
                progress_video_idx: int = video_idx,
            ):
                if event.get("stage") != "detection":
                    return
                _send_progress(
                    progress_queue,
                    {
                        "current_video": progress_video_name,
                        "current_video_index": progress_video_idx + 1,
                        "total_videos": len(videos),
                        "current_stage": "detection",
                        "detection_progress": int(event.get("processed", 0)),
                        "detection_total": int(event.get("total", 0)),
                        "detected_kills": int(event.get("detected", 0)),
                    },
                )

            pipeline = Pipeline(config, progress_callback=send_pipeline_progress)
            stop_monitor = threading.Event()
            monitor_thread = threading.Thread(
                target=_monitor_pipeline,
                args=(pipeline, StageStatus, progress_queue, stop_monitor, video_name, video_idx, len(videos)),
                daemon=True,
            )
            monitor_thread.start()

            try:
                if len(videos) > 1:
                    run_result = pipeline.run_until_clips_result(video_path)
                else:
                    run_result = pipeline.run_full_result(video_path)
                clips = run_result.clips
                video_results.append(run_result.as_dict())

                if not run_result.success:
                    error = run_result.error or f"Failed processing {video_name}"
                    result_queue.put(
                        {
                            "success": False,
                            "error": error,
                            "failed_video": video_path,
                            "failed_stage": run_result.failed_stage,
                            "videos_processed": video_idx,
                            "video_results": video_results,
                            "output_files": output_files,
                        }
                    )
                    return

                all_clips.extend(clips)
                output_video = make_output_file(run_result.final_video, f"{video_name} 高光视频", "video")
                output_report = make_output_file(run_result.report_path, f"{video_name} 报告", "report")
                for output_file in [output_video, output_report]:
                    if output_file:
                        output_files.append(output_file)

                _send_progress(
                    progress_queue,
                    {
                        "current_video": video_name,
                        "current_video_index": video_idx + 1,
                        "total_videos": len(videos),
                        "current_stage": "completed",
                        "stages": completed_stage_map(),
                        "detection_progress": len(pipeline.results.get(FRAMES, [])),
                        "detection_total": len(pipeline.results.get(FRAMES, [])),
                        "detected_kills": len(pipeline.results.get(EVENTS, [])),
                        "extracted_clips": len(clips),
                    },
                )
            finally:
                stop_monitor.set()
                monitor_thread.join(timeout=1)

        if len(videos) > 1 and all_clips:
            _send_progress(
                progress_queue,
                {
                    "current_video": "合并所有片段...",
                    "current_video_index": len(videos),
                    "total_videos": len(videos),
                    "current_stage": "merging",
                    "stages": completed_stage_map(),
                    "detection_progress": 100,
                    "detection_total": 100,
                    "detected_kills": len(all_clips),
                    "extracted_clips": len(all_clips),
                },
            )

            from src.pipeline.multi_video import merge_clips_to_highlight

            merged_result = merge_clips_to_highlight(config, videos, all_clips)
            if merged_result:
                output_video = make_output_file(merged_result.get("final_video"), "合并高光视频", "video")
                output_report = make_output_file(merged_result.get("report_path"), "合并报告", "report")
                for output_file in [output_video, output_report]:
                    if output_file:
                        output_files.append(output_file)

        result_queue.put(
            {
                "success": True,
                "total_clips": len(all_clips),
                "videos_processed": len(videos),
                "video_results": video_results,
                "output_files": output_files,
                "message": "Processing completed successfully",
            }
        )
    except Exception as e:
        error_msg = str(e)
        _send_error(progress_queue, error_msg)
        result_queue.put({"success": False, "error": error_msg})


_run_processing_task = run_processing_task
