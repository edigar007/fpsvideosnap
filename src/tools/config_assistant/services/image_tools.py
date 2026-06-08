import os
from typing import Any

import cv2
import numpy as np
from PIL import Image

from src.tools.config_assistant.utils import calculate_hsv_range, rgb_to_hsv


def crop_relative_region(image_path: str, output_path: str, roi: list[float]) -> None:
    with Image.open(image_path) as img:
        width, height = img.size
        left = int(roi[0] * width)
        top = int(roi[1] * height)
        right = int((roi[0] + roi[2]) * width)
        bottom = int((roi[1] + roi[3]) * height)

        cropped = img.crop((left, top, right, bottom))
        cropped.save(output_path)


def pick_color_sample(image_path: str, x_value: float, y_value: float, tolerance: list[int]) -> dict[str, Any]:
    with Image.open(image_path) as img:
        width, height = img.size
        if 0 <= x_value <= 1 and 0 <= y_value <= 1:
            x = int(x_value * width)
            y = int(y_value * height)
        else:
            x = int(x_value)
            y = int(y_value)

        x = max(0, min(width - 1, x))
        y = max(0, min(height - 1, y))
        red, green, blue = img.convert("RGB").getpixel((x, y))

    hue, saturation, value = rgb_to_hsv(red, green, blue)
    lower, upper = calculate_hsv_range(hue, saturation, value, tuple(tolerance))

    return {
        "rgb": [red, green, blue],
        "hsv": [hue, saturation, value],
        "hsv_range": {
            "lower": lower,
            "upper": upper,
        },
    }


def preview_color_mask(image_path: str, roi: list[float] | None, lower: list[int], upper: list[int]) -> bytes | None:
    image = cv2.imread(image_path)
    if image is None:
        return None

    image_h, image_w = image.shape[:2]
    if roi:
        rx, ry, rw, rh = roi
        x1, y1 = int(rx * image_w), int(ry * image_h)
        x2, y2 = int((rx + rw) * image_w), int((ry + rh) * image_h)
        region = image[y1:y2, x1:x2]
    else:
        region = image

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
    ok, buffer = cv2.imencode(".png", mask)
    if not ok:
        return None
    return buffer.tobytes()


def list_template_files(target_dir: str) -> list[dict[str, str]]:
    if not os.path.exists(target_dir):
        return []

    templates = []
    for filename in os.listdir(target_dir):
        if filename.endswith((".png", ".jpg", ".jpeg")):
            templates.append(
                {
                    "name": os.path.splitext(filename)[0],
                    "filename": filename,
                }
            )
    return templates

