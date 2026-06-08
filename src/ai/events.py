from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DetectionEvent:
    timestamp_ms: int
    confidence: float
    type: str = "kill"
    signals: Dict[str, float] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, values: Dict[str, Any]) -> "DetectionEvent":
        return cls(
            timestamp_ms=int(values.get("timestamp_ms", 0)),
            confidence=float(values.get("confidence", 0.0)),
            type=str(values.get("type", "kill")),
            signals=dict(values.get("signals", {}) or {}),
            meta=dict(values.get("meta", {}) or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "timestamp_ms": self.timestamp_ms,
            "confidence": self.confidence,
            "type": self.type,
            "signals": self.signals,
        }
        if self.meta:
            result["meta"] = self.meta
        return result
