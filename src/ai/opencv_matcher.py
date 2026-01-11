import cv2
import numpy as np
import os
from src.utils.logger import get_logger

logger = get_logger(__name__)

class OpenCVMatcher:
    """
    Handles image processing tasks using OpenCV:
    - Template matching (for UI icons)
    - Color detection (for killfeed colors like blue/red)
    - ROI (Region of Interest) cropping
    """
    def __init__(self, config=None):
        self.config = config or {}
        self.templates = {}
        
    def load_templates(self, template_dir: str):
        """
        Loads all .png or .jpg templates from a directory.
        """
        if not os.path.exists(template_dir):
            logger.warning(f"Template directory {template_dir} does not exist.")
            return

        for filename in os.listdir(template_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                path = os.path.join(template_dir, filename)
                template = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if template is not None:
                    name = os.path.splitext(filename)[0]
                    self.templates[name] = template
                    logger.debug(f"Loaded template: {name}")

    def match_template(self, frame: np.ndarray, template_name: str, threshold=0.8, roi=None):
        """
        Performs template matching on a frame or ROI.
        """
        if template_name not in self.templates:
            return None, 0

        template = self.templates[template_name]
        search_area = frame
        
        if roi:
            # roi format: [x, y, w, h] as decimals (0-1)
            h, w = frame.shape[:2]
            tx, ty, tw, th = int(roi[0]*w), int(roi[1]*h), int(roi[2]*w), int(roi[3]*h)
            search_area = frame[ty:ty+th, tx:tx+tw]

        # Convert to grayscale if template is grayscale or frame is color
        if len(template.shape) == 3 and template.shape[2] == 4: # Handle Alpha
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGRA2GRAY)
        elif len(template.shape) == 3:
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            template_gray = template

        if len(search_area.shape) == 3:
            search_gray = cv2.cvtColor(search_area, cv2.COLOR_BGR2GRAY)
        else:
            search_gray = search_area

        if template_gray.shape[0] > search_gray.shape[0] or template_gray.shape[1] > search_gray.shape[1]:
            logger.warning(f"Template {template_name} is larger than search area.")
            return None, 0

        res = cv2.matchTemplate(search_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            # Adjust location back to full frame if ROI was used
            if roi:
                h_f, w_f = frame.shape[:2]
                tx, ty = int(roi[0]*w_f), int(roi[1]*h_f)
                return (max_loc[0] + tx, max_loc[1] + ty), max_val
            return max_loc, max_val
        
        return None, max_val

    def detect_color(self, frame: np.ndarray, lower_hsv: list, upper_hsv: list, roi=None):
        """
        Detects pixels within an HSV range in a frame or ROI.
        Returns the percentage of pixels that match the color.
        """
        search_area = frame
        if roi:
            h, w = frame.shape[:2]
            tx, ty, tw, th = int(roi[0]*w), int(roi[1]*h), int(roi[2]*w), int(roi[3]*h)
            search_area = frame[ty:ty+th, tx:tx+tw]

        hsv = cv2.cvtColor(search_area, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))
        
        match_count = cv2.countNonZero(mask)
        total_pixels = search_area.shape[0] * search_area.shape[1]
        
        return (match_count / total_pixels) if total_pixels > 0 else 0
