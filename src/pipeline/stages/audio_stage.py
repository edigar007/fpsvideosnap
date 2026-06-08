import os
import shutil
from typing import Callable, Type

from src.audio.audio_mixer import AudioMixer
from src.config.fingerprint import get_unique_output_path
from src.pipeline.context import PipelineContext
from src.pipeline.results import FINAL_VIDEO
from src.pipeline.stages.base import StageResult


def build_final_video_path(
    context: PipelineContext,
    unique_path_factory: Callable[[str], str] = get_unique_output_path,
) -> str:
    output_dir = context.config.get("global", {}).get("output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)
    base_final_path = os.path.join(output_dir, f"{context.base_name}_highlights.mp4")
    if os.path.exists(base_final_path):
        return unique_path_factory(base_final_path)
    return base_final_path


def run_audio_stage(
    context: PipelineContext,
    joined_video: str,
    audio_mixer_cls: Type[AudioMixer] = AudioMixer,
    unique_path_factory: Callable[[str], str] = get_unique_output_path,
) -> StageResult:
    if not joined_video or not os.path.exists(joined_video):
        return StageResult({FINAL_VIDEO: None}, skipped=True)

    final_video_path = build_final_video_path(context, unique_path_factory)
    mixer = audio_mixer_cls(context.config)
    result_path = mixer.mix_audio(joined_video, final_video_path)

    if result_path == joined_video:
        shutil.copy2(joined_video, final_video_path)

    return StageResult({FINAL_VIDEO: final_video_path})
