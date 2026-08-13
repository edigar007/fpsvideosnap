import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from src.audio.audio_mixer import AudioMixer
from src.report.report_generator import ReportGenerator, format_duration
from src.utils.logger import get_logger
from src.video.video_info import VideoInfo
from src.video.video_joiner import VideoJoiner

logger = get_logger(__name__)


def _is_cancelled(cancel_event: Any) -> bool:
    return bool(cancel_event and cancel_event.is_set())


def _cancelled_merge_result(stage: str, clips: List[Dict[str, Any]], source_videos: List[str]) -> Dict[str, Any]:
    return {
        "path": "MERGED",
        "success": False,
        "cancelled": True,
        "stage": stage,
        "total_clips": len(clips),
        "source_videos": len(source_videos),
    }


def merge_clips_to_highlight(
    config: Dict[str, Any],
    source_videos: List[str],
    clips: List[Dict[str, Any]],
    timestamp: Optional[str] = None,
    video_joiner_cls: Type[VideoJoiner] = VideoJoiner,
    audio_mixer_cls: Type[AudioMixer] = AudioMixer,
    report_generator_cls: Type[ReportGenerator] = ReportGenerator,
    cancel_event: Any = None,
) -> Optional[Dict[str, Any]]:
    """
    Merge clips from multiple videos into one final highlight and report.

    Returns a result dict compatible with BatchProcessor's MERGED result, or
    None when there are no valid clip paths or the join step fails.
    """
    clip_paths = [
        clip.get("path") or clip.get("output_path")
        for clip in clips
        if clip.get("path") or clip.get("output_path")
    ]
    if not clip_paths:
        logger.warning("[yellow]No clip paths available. Nothing to merge.[/yellow]")
        return None

    if _is_cancelled(cancel_event):
        return _cancelled_merge_result("merge_join", clips, source_videos)

    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config.get("global", {}).get("output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)

    merged_no_audio = os.path.join(output_dir, f"combined_temp_{timestamp}.mp4")
    final_output = os.path.join(output_dir, f"combined_highlights_{timestamp}.mp4")

    keep_intermediates = bool(config.get("global", {}).get("debug", False)) or bool(
        config.get("video", {}).get("join_fix", {}).get("keep_intermediates", False)
    )

    def _remove_merged_no_audio() -> None:
        """Remove the intermediate merged file unless keep_intermediates is set."""
        if os.path.exists(merged_no_audio) and merged_no_audio != final_output and not keep_intermediates:
            try:
                os.remove(merged_no_audio)
            except OSError as exc:
                logger.warning(f"Failed to remove intermediate merged video {merged_no_audio}: {exc}")

    joiner = video_joiner_cls(config)
    if not joiner.join_clips(clip_paths, merged_no_audio):
        logger.error("[red]Failed to merge clips.[/red]")
        return None

    if _is_cancelled(cancel_event):
        _remove_merged_no_audio()
        return _cancelled_merge_result("merge_audio", clips, source_videos)

    mixer = audio_mixer_cls(config)
    result_path = mixer.mix_audio(merged_no_audio, final_output)

    if _is_cancelled(cancel_event):
        _remove_merged_no_audio()
        return _cancelled_merge_result("merge_report", clips, source_videos)

    if result_path == merged_no_audio:
        shutil.copy2(merged_no_audio, final_output)

    _remove_merged_no_audio()

    report_gen = report_generator_cls(output_dir)
    video_info = {
        "path": f"Combined from {len(source_videos)} videos",
        "source_videos": [os.path.basename(v) for v in source_videos],
    }
    try:
        merged_info = VideoInfo(
            final_output,
            ffprobe_path=config.get("video", {}).get("ffprobe_path", "ffprobe"),
        )
        video_info.update(
            {
                "video_path": final_output,
                "width": merged_info.width,
                "height": merged_info.height,
                "fps": merged_info.fps,
                "duration": merged_info.duration,
                "duration_str": format_duration(merged_info.duration),
                "source_videos": [os.path.basename(v) for v in source_videos],
            }
        )
    except Exception as exc:
        logger.warning(f"Failed to probe merged video {final_output}: {exc}")
    report_path = report_gen.generate(video_info, clips, config)

    return {
        "path": "MERGED",
        "success": True,
        "final_video": final_output,
        "total_clips": len(clips),
        "source_videos": len(source_videos),
        "report_path": report_path,
    }
