from typing import Type

from src.history.history_manager import HistoryManager
from src.pipeline.context import PipelineContext
from src.pipeline.results import CLIPS
from src.pipeline.stages.base import StageResult


def run_history_stage(
    context: PipelineContext,
    history_manager_cls: Type[HistoryManager] = HistoryManager,
) -> StageResult:
    history_dir = context.config.get("global", {}).get("history_dir", "history")
    history_mgr = history_manager_cls(history_dir)
    history_mgr.save_run(context.config, context.results.get(CLIPS, []))
    return StageResult()
