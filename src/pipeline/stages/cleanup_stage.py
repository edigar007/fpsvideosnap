import os
import shutil

from src.pipeline.context import PipelineContext
from src.pipeline.stages.base import StageResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_cleanup_stage(context: PipelineContext) -> StageResult:
    keep_intermediates = bool(context.config.get("global", {}).get("debug", False)) or bool(
        context.config.get("video", {}).get("join_fix", {}).get("keep_intermediates", False)
    )

    if not keep_intermediates and context.temp_dir and os.path.isdir(context.temp_dir):
        shutil.rmtree(context.temp_dir, ignore_errors=True)

    if context.checkpoint_file and os.path.exists(context.checkpoint_file):
        try:
            os.remove(context.checkpoint_file)
        except FileNotFoundError:
            logger.debug(f"Checkpoint already removed: {context.checkpoint_file}")

    return StageResult()
