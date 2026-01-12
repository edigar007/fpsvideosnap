import cv2
import numpy as np
import os
import re
from werkzeug.utils import secure_filename
from src.utils.logger import get_logger

logger = get_logger("config_assistant.utils")

SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

def sanitize_filename(filename: str) -> str:
    """Return a Werkzeug-secured filename while preserving extension."""
    if not filename:
        raise ValueError("Filename is required")
    safe_name = secure_filename(filename)
    if not safe_name:
        raise ValueError("Provided filename contains no valid characters")
    return safe_name

def validate_identifier(value: str, field_name: str) -> str:
    """Ensure identifiers like game/template names are alphanumeric/_/-."""
    if not value:
        raise ValueError(f"{field_name} is required")
    normalized = value.strip()
    if not SAFE_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must match pattern {SAFE_NAME_PATTERN.pattern}")
    return normalized

def safe_join(base_dir: str, *paths: str) -> str:
    """Join paths and ensure the final path stays within base_dir."""
    if not base_dir:
        raise ValueError("Base directory is required")
    candidate = os.path.abspath(os.path.join(base_dir, *paths))
    base_abs = os.path.abspath(base_dir)
    if os.path.commonpath([candidate, base_abs]) != base_abs:
        raise ValueError("Attempted path traversal outside of base directory")
    return candidate

def rgb_to_hsv(r, g, b):
    """
    Converts RGB values to HSV using OpenCV logic.
    OpenCV HSV range: H [0, 179], S [0, 255], V [0, 255]
    """
    # Create a 1x1 pixel image in BGR format
    pixel_bgr = np.uint8([[[b, g, r]]])
    pixel_hsv = cv2.cvtColor(pixel_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = pixel_hsv[0][0]
    return int(h), int(s), int(v)

def calculate_hsv_range(h, s, v, tolerance=(10, 50, 50)):
    """
    Calculates lower and upper HSV bounds based on tolerance.
    tolerance: (h_tol, s_tol, v_tol)
    """
    h_tol, s_tol, v_tol = tolerance
    
    lower = [
        max(0, h - h_tol),
        max(0, s - s_tol),
        max(0, v - v_tol)
    ]
    
    upper = [
        min(179, h + h_tol),
        min(255, s + s_tol),
        min(255, v + v_tol)
    ]
    
    return lower, upper
