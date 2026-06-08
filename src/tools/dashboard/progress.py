import os
from typing import Any, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

PIPELINE_STAGES = [
    ("metadata", "视频元数据"),
    ("frames", "帧提取"),
    ("detection", "击杀检测"),
    ("clips", "片段提取"),
    ("join", "视频拼接"),
    ("audio", "音频混合"),
]


def make_output_file(path: Optional[str], label: str, file_type: str) -> Optional[Dict[str, Any]]:
    """Build output file metadata for dashboard display."""
    if not path:
        return None

    abs_path = os.path.abspath(path)
    item = {
        "path": abs_path,
        "name": os.path.basename(abs_path),
        "label": label,
        "type": file_type,
        "exists": os.path.exists(abs_path),
    }

    if item["exists"]:
        try:
            item["size"] = os.path.getsize(abs_path)
        except OSError as exc:
            logger.debug(f"Failed to read output file size for {abs_path}: {exc}")

    return item


def pending_stage_map() -> Dict[str, str]:
    return {stage_name: "pending" for stage_name, _ in PIPELINE_STAGES}


def completed_stage_map() -> Dict[str, str]:
    return {stage_name: "success" for stage_name, _ in PIPELINE_STAGES}
