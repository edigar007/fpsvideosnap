from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional


VIDEO_INFO = "video_info"
FRAMES = "frames"
EVENTS = "events"
DETECTION_JSON = "detection_json"
DEBUG_VIDEO = "debug_video"
CLIPS = "clips"
JOINED_VIDEO = "joined_video"
FINAL_VIDEO = "final_video"
REPORT_PATH = "report_path"

ALL_RESULT_KEYS: FrozenSet[str] = frozenset(
    {
        VIDEO_INFO,
        FRAMES,
        EVENTS,
        DETECTION_JSON,
        DEBUG_VIDEO,
        CLIPS,
        JOINED_VIDEO,
        FINAL_VIDEO,
        REPORT_PATH,
    }
)


@dataclass
class StageResult:
    values: Dict[str, Any] = field(default_factory=dict)
    skipped: bool = False

    def __post_init__(self) -> None:
        validate_result_keys(self.values)


@dataclass
class PipelineResult:
    values: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        validate_result_keys({key: value})
        self.values[key] = value

    def update(self, values: Dict[str, Any]) -> None:
        validate_result_keys(values)
        self.values.update(values)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.values)


@dataclass
class PipelineRunResult:
    success: bool
    mode: str
    video_path: str
    clips: List[Dict[str, Any]] = field(default_factory=list)
    final_video: Optional[str] = None
    report_path: Optional[str] = None
    failed_stage: Optional[str] = None
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "mode": self.mode,
            "video_path": self.video_path,
            "clips": list(self.clips),
            "final_video": self.final_video,
            "report_path": self.report_path,
            "failed_stage": self.failed_stage,
            "error": self.error,
        }


def validate_result_keys(values: Dict[str, Any]) -> None:
    unknown_keys = set(values) - ALL_RESULT_KEYS
    if unknown_keys:
        keys = ", ".join(sorted(unknown_keys))
        raise KeyError(f"Unknown pipeline result key(s): {keys}")
