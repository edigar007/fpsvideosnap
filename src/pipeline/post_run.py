import os
from datetime import datetime
from typing import Any, Dict

from src.utils.logger import get_logger
from src.utils.performance_profiler import get_profiler

logger = get_logger(__name__)
profiler = get_profiler()


def emit_performance_profile(config: Dict[str, Any], save_to_history: bool = True) -> str | None:
    """
    Print the current performance profile and optionally persist it under history_dir.
    """
    profiler.print_summary()
    if not save_to_history:
        return None

    history_dir = config.get("global", {}).get("history_dir", "history")
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    perf_file = os.path.join(history_dir, f"performance_{run_timestamp}.json")
    try:
        os.makedirs(history_dir, exist_ok=True)
        profiler.save_to_file(perf_file)
    except OSError as exc:
        logger.warning(f"Failed to save performance profile: {exc}")
        return None

    return perf_file
