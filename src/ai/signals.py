from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SignalResult:
    ocr: float = 0.0
    template: float = 0.0
    color: float = 0.0
    yolo: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, float]:
        return {
            "ocr": self.ocr,
            "template": self.template,
            "color": self.color,
            "yolo": self.yolo,
        }

    @classmethod
    def from_dict(cls, values: Dict[str, float]) -> "SignalResult":
        return cls(
            ocr=float(values.get("ocr", 0.0)),
            template=float(values.get("template", 0.0)),
            color=float(values.get("color", 0.0)),
            yolo=float(values.get("yolo", 0.0)),
        )
