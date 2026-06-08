from typing import Dict


class WeightedSignalFusion:
    """Calculate normalized weighted confidence for detection signals."""

    def calculate(
        self,
        signals: Dict[str, float],
        weights: Dict[str, float],
        ocr_active: bool,
        templates_active: bool,
    ) -> float:
        active_weights = {}

        if ocr_active:
            active_weights["ocr"] = weights.get("ocr", 0.4)

        if templates_active:
            active_weights["template"] = weights.get("template", 0.3)

        active_weights["color"] = weights.get("color", 0.2)
        active_weights["yolo"] = weights.get("yolo", 0.1)

        total_weight = sum(active_weights.values())
        if total_weight == 0:
            return 0.0

        return sum(
            signals.get(name, 0.0) * (weight / total_weight)
            for name, weight in active_weights.items()
        )

