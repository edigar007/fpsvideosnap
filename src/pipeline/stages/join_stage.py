import os
from typing import Any, Dict, List, Type

from src.clip.metadata import ClipMetadata
from src.pipeline.context import PipelineContext
from src.pipeline.results import JOINED_VIDEO
from src.pipeline.stages.base import StageResult
from src.video.video_joiner import VideoJoiner


def collect_clip_paths(clips: List[Dict[str, Any]]) -> List[str]:
    clip_paths = []
    for clip in clips:
        clip_path = ClipMetadata.from_dict(clip).path
        if not os.path.exists(clip_path):
            raise FileNotFoundError(f"Clip file not found: {clip_path}")
        clip_paths.append(clip_path)
    return clip_paths


def run_join_stage(
    context: PipelineContext,
    clips: List[Dict[str, Any]],
    video_joiner_cls: Type[VideoJoiner] = VideoJoiner,
) -> StageResult:
    if not clips:
        return StageResult({JOINED_VIDEO: None}, skipped=True)

    joined_video = os.path.join(context.temp_dir, "joined_no_audio.mp4")
    clip_paths = collect_clip_paths(clips)
    joiner = video_joiner_cls(context.config)

    if not joiner.join_clips(clip_paths, joined_video):
        raise RuntimeError("Failed to join clips.")

    return StageResult({JOINED_VIDEO: joined_video})
