from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ClipMetadata:
    path: str
    start_ms: int = 0
    end_ms: int = 0
    kill_count: int = 0
    filename: Optional[str] = None
    source_video: Optional[str] = None

    @classmethod
    def from_dict(cls, values: Dict[str, Any]) -> "ClipMetadata":
        path = values.get("path") or values.get("output_path")
        if not path:
            clip_id = values.get("id", "unknown")
            raise RuntimeError(f"Clip {clip_id} missing path field")

        return cls(
            path=str(path),
            start_ms=int(values.get("start_ms", 0)),
            end_ms=int(values.get("end_ms", 0)),
            kill_count=int(values.get("kill_count", 0)),
            filename=values.get("filename"),
            source_video=values.get("source_video"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "path": self.path,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "kill_count": self.kill_count,
        }
        if self.filename is not None:
            result["filename"] = self.filename
        if self.source_video is not None:
            result["source_video"] = self.source_video
        return result
