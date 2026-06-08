import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from src.config.fingerprint import STAGE_ORDER
from src.pipeline.results import (
    CLIPS,
    DETECTION_JSON,
    EVENTS,
    FINAL_VIDEO,
    FRAMES,
    JOINED_VIDEO,
    REPORT_PATH,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CheckpointData:
    stages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    temp_dir: str = ""
    fingerprints: Dict[str, str] = field(default_factory=dict)


class ArtifactValidator:
    """Validate stage artifacts referenced by a checkpoint before resume skips work."""

    def get_invalid_stage(self, checkpoint: CheckpointData) -> Optional[str]:
        for stage_name in STAGE_ORDER:
            stage_data = checkpoint.stages.get(stage_name)
            if not stage_data or stage_data.get("status") != "SUCCESS":
                continue
            if not self.stage_artifacts_valid(stage_name, checkpoint.results):
                return stage_name
        return None

    def stage_artifacts_valid(self, stage_name: str, results: Dict[str, Any]) -> bool:
        if stage_name in {"metadata", "history", "cleanup"}:
            return True

        if stage_name == "frames":
            frames = results.get(FRAMES, [])
            return isinstance(frames, list) and bool(frames) and all(os.path.exists(path) for path in frames)

        if stage_name == "detection":
            detection_json = results.get(DETECTION_JSON)
            if not detection_json or not os.path.exists(detection_json):
                return False
            try:
                with open(detection_json, "r", encoding="utf-8") as f:
                    json.load(f)
            except (OSError, json.JSONDecodeError):
                return False
            return isinstance(results.get(EVENTS, []), list)

        if stage_name == "clips":
            clips = results.get(CLIPS, [])
            if not isinstance(clips, list):
                return False
            for clip in clips:
                clip_path = clip.get("path") or clip.get("output_path") if isinstance(clip, dict) else None
                if not clip_path or not os.path.exists(clip_path):
                    return False
            return True

        if stage_name == "join":
            joined_video = results.get(JOINED_VIDEO)
            return bool(joined_video) and os.path.exists(joined_video)

        if stage_name == "audio":
            final_video = results.get(FINAL_VIDEO)
            return bool(final_video) and os.path.exists(final_video)

        if stage_name == "report":
            report_path = results.get(REPORT_PATH)
            return bool(report_path) and os.path.exists(report_path)

        return True


class CheckpointStore:
    """Read, write, and validate pipeline checkpoint files."""

    def __init__(self, checkpoint_version: int, artifact_validator: ArtifactValidator = None):
        self.checkpoint_version = checkpoint_version
        self.artifact_validator = artifact_validator or ArtifactValidator()

    def save(
        self,
        checkpoint_path: str,
        video_path: str,
        fingerprints: Dict[str, str],
        stages: Dict[str, Any],
        results: Dict[str, Any],
        temp_dir: str,
    ) -> None:
        if not checkpoint_path:
            return

        checkpoint_dir = os.path.dirname(os.path.abspath(checkpoint_path))
        os.makedirs(checkpoint_dir, exist_ok=True)
        temp_path = f"{checkpoint_path}.tmp"
        backup_path = f"{checkpoint_path}.bak"
        checkpoint_data = {
            "checkpoint_version": self.checkpoint_version,
            "video_path": video_path,
            "fingerprints": fingerprints,
            "stages": {
                name: {"status": stage.status.value, "duration": stage.duration}
                for name, stage in stages.items()
            },
            "results": results,
            "temp_dir": temp_dir,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(checkpoint_path):
                shutil.copy2(checkpoint_path, backup_path)
            os.replace(temp_path, checkpoint_path)
        except (OSError, TypeError, ValueError) as exc:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as cleanup_exc:
                    logger.warning(f"Failed to remove temporary checkpoint {temp_path}: {cleanup_exc}")
            logger.error(f"Failed to save checkpoint: {exc}")

    def load(self, checkpoint_path: str, current_video_path: str) -> Optional[CheckpointData]:
        if not os.path.exists(checkpoint_path):
            return None

        data = self._load_checkpoint_json(checkpoint_path)
        if data is None:
            backup_path = f"{checkpoint_path}.bak"
            data = self._load_checkpoint_json(backup_path, is_backup=True)
            if data is None:
                return None

        checkpoint_version = data.get("checkpoint_version", 1)
        if checkpoint_version < self.checkpoint_version:
            logger.info(
                f"Checkpoint version mismatch (v{checkpoint_version} < v{self.checkpoint_version}), "
                "starting fresh run"
            )
            return None

        saved_video_path = data.get("video_path", "")
        if saved_video_path and saved_video_path != current_video_path:
            logger.info("Checkpoint belongs to different video, starting fresh run")
            return None

        return CheckpointData(
            stages=data.get("stages", {}),
            results=data.get("results", {}),
            temp_dir=data.get("temp_dir", ""),
            fingerprints=data.get("fingerprints", {}),
        )

    def _load_checkpoint_json(self, checkpoint_path: str, is_backup: bool = False) -> Optional[Dict[str, Any]]:
        if not os.path.exists(checkpoint_path):
            return None

        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            label = "backup checkpoint" if is_backup else "checkpoint"
            logger.error(f"Failed to load {label} {checkpoint_path}: {exc}")
            return None

    def get_invalid_stage(self, checkpoint: CheckpointData) -> Optional[str]:
        return self.artifact_validator.get_invalid_stage(checkpoint)
