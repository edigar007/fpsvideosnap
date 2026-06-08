import os
import shutil
from typing import Iterable, List

from src.config.fingerprint import STAGE_ORDER, get_stages_to_invalidate
from src.pipeline.results import CLIPS, DETECTION_JSON, EVENTS, FINAL_VIDEO, FRAMES, JOINED_VIDEO, REPORT_PATH
from src.utils.logger import get_logger

logger = get_logger(__name__)


RESULT_KEYS_BY_STAGE = {
    "frames": [FRAMES],
    "detection": [EVENTS, DETECTION_JSON],
    "clips": [CLIPS],
    "join": [JOINED_VIDEO],
    "audio": [FINAL_VIDEO],
    "report": [REPORT_PATH],
}


class StageRegistry:
    """Central stage order and result-key invalidation metadata."""

    @property
    def stage_names(self) -> List[str]:
        return list(STAGE_ORDER)

    def stages_to_invalidate(self, from_stage: str) -> List[str]:
        return get_stages_to_invalidate(from_stage)

    def result_keys_for_stage(self, stage_name: str) -> List[str]:
        return list(RESULT_KEYS_BY_STAGE.get(stage_name, []))

    def result_keys_to_clear(self, stage_names: Iterable[str]) -> List[str]:
        keys = []
        for stage_name in stage_names:
            keys.extend(self.result_keys_for_stage(stage_name))
        return keys


class ArtifactStore:
    """Manage temp artifact paths owned by pipeline stages."""

    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir

    def artifact_path_for_stage(self, stage_name: str) -> str:
        if not self.temp_dir:
            return ""

        artifact_paths = {
            "frames": os.path.join(self.temp_dir, "frames"),
            "clips": os.path.join(self.temp_dir, "clips"),
            "join": os.path.join(self.temp_dir, "joined_no_audio.mp4"),
        }
        return artifact_paths.get(stage_name, "")

    def remove_stage_artifacts(self, stage_names: Iterable[str]) -> None:
        for stage_name in stage_names:
            path = self.artifact_path_for_stage(stage_name)
            if not path or not os.path.exists(path):
                continue

            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    logger.debug(f"Removed artifact directory: {path}")
                else:
                    os.remove(path)
                    logger.debug(f"Removed artifact file: {path}")
            except OSError as exc:
                logger.warning(f"Failed to remove artifact {path}: {exc}")

