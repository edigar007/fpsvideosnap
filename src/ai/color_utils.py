from typing import Any, Dict, List, Optional, Tuple


def get_hsv_bounds(color_cfg: Dict[str, Any]) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """
    Return HSV lower/upper bounds from config.

    Explicit hsv_lower/hsv_upper values are final. Tolerance is only applied
    when config provides a center hsv value.
    """
    hsv_lower = color_cfg.get("hsv_lower", color_cfg.get("lower"))
    hsv_upper = color_cfg.get("hsv_upper", color_cfg.get("upper"))
    if hsv_lower and hsv_upper:
        return hsv_lower, hsv_upper

    hsv = color_cfg.get("hsv")
    if not hsv:
        return None, None

    tolerance = color_cfg.get("tolerance", 0)
    if isinstance(tolerance, (int, float)):
        # Saturation and Value ranges are wider (0-255) than Hue (0-179),
        # so we double their tolerance to maintain proportional sensitivity.
        tolerance = [tolerance, tolerance * 2, tolerance * 2]

    if not isinstance(tolerance, (list, tuple)) or len(tolerance) != 3:
        return None, None

    return (
        [
            max(0, hsv[0] - tolerance[0]),
            max(0, hsv[1] - tolerance[1]),
            max(0, hsv[2] - tolerance[2]),
        ],
        [
            min(179, hsv[0] + tolerance[0]),
            min(255, hsv[1] + tolerance[1]),
            min(255, hsv[2] + tolerance[2]),
        ],
    )
