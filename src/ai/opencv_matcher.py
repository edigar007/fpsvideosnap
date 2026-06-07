import cv2
import numpy as np
import os
from typing import Dict, Optional
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
        self.templates_gray = {}

    def load_template_file(self, name: str, template_path: str) -> bool:
        """
        Load one template image with an explicit config name.
        Returns True when the image was loaded and cached.
        """
        if not template_path or not os.path.exists(template_path):
            logger.warning(f"Template file {template_path} does not exist.")
            return False

        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            logger.warning(f"Failed to load template image: {template_path}")
            return False

        self._cache_template(name, template)
        logger.debug(f"Loaded template: {name} from {template_path}")
        return True

    def load_templates_from_config(self, detection_config: Optional[Dict], project_root: str = None) -> int:
        """
        Load templates from detection.template_dir and detection.templates.*.path.
        Relative paths are resolved from project_root or the current working directory.
        """
        detection_config = detection_config or {}
        before_count = len(self.templates)

        template_dir = detection_config.get("template_dir", "")
        if template_dir:
            self.load_templates(self._resolve_path(template_dir, project_root))

        for templates_cfg in self._iter_template_configs(detection_config):
            for name, cfg in templates_cfg.items():
                if not isinstance(cfg, dict):
                    continue
                template_path = cfg.get("path")
                if template_path:
                    self.load_template_file(name, self._resolve_path(template_path, project_root))

        return len(self.templates) - before_count

    def load_templates(self, template_dir: str):
        """
        Loads all .png or .jpg templates from a directory.
        Caches both original and grayscale versions.
        """
        if not os.path.exists(template_dir):
            logger.warning(f"Template directory {template_dir} does not exist.")
            return

        for filename in os.listdir(template_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                path = os.path.join(template_dir, filename)
                name = os.path.splitext(filename)[0]
                self.load_template_file(name, path)

    def _cache_template(self, name: str, template: np.ndarray) -> None:
        """Cache original and grayscale template arrays."""
        self.templates[name] = template

        if len(template.shape) == 3 and template.shape[2] == 4:
            gray = cv2.cvtColor(template, cv2.COLOR_BGRA2GRAY)
        elif len(template.shape) == 3:
            gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            gray = template
        self.templates_gray[name] = gray

    def _resolve_path(self, path: str, project_root: str = None) -> str:
        """Resolve relative template paths from project root/current working directory."""
        if os.path.isabs(path):
            return path
        base_dir = project_root or os.getcwd()
        return os.path.abspath(os.path.join(base_dir, path))

    def _iter_template_configs(self, detection_config: Dict):
        """Yield global and per-rule template config dictionaries."""
        templates = detection_config.get("templates", {})
        if isinstance(templates, dict):
            yield templates

        for rule in detection_config.get("rules", []) or []:
            overrides = rule.get("detection_overrides", {})
            templates = overrides.get("templates", {})
            if isinstance(templates, dict):
                yield templates

    def _get_search_area(self, frame: np.ndarray, roi=None):
        """Helper to crop and grayscale search area."""
        h_f, w_f = frame.shape[:2]
        offset_x, offset_y = 0, 0
        search_area = frame
        
        if roi:
            tx, ty, tw, th = int(roi[0]*w_f), int(roi[1]*h_f), int(roi[2]*w_f), int(roi[3]*h_f)
            search_area = frame[ty:ty+th, tx:tx+tw]
            offset_x, offset_y = tx, ty

        if len(search_area.shape) == 3:
            search_gray = cv2.cvtColor(search_area, cv2.COLOR_BGR2GRAY)
        else:
            search_gray = search_area
            
        return search_gray, (offset_x, offset_y)

    def match_template(self, frame: np.ndarray, template_name: str, threshold=0.8, roi=None, scales=None):
        """
        Performs template matching on a frame or ROI.
        Supports multi-scale matching if scales list is provided.
        Returns (location, confidence_score) tuple.
        """
        if template_name not in self.templates:
            return None, 0

        search_gray, (offset_x, offset_y) = self._get_search_area(frame, roi)
        template_gray = self.templates_gray.get(template_name)
        
        if template_gray is None:
            # Fallback if somehow missing from gray cache
            template = self.templates[template_name]
            if len(template.shape) == 3 and template.shape[2] == 4:
                template_gray = cv2.cvtColor(template, cv2.COLOR_BGRA2GRAY)
            elif len(template.shape) == 3:
                template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            else:
                template_gray = template

        best_max_val = -1
        best_max_loc = None

        if scales is None:
            scales = [1.0]

        for scale in scales:
            if scale == 1.0:
                resized = template_gray
            else:
                w = int(template_gray.shape[1] * scale)
                h = int(template_gray.shape[0] * scale)
                if w <= 0 or h <= 0: continue
                resized = cv2.resize(template_gray, (w, h))

            if resized.shape[0] > search_gray.shape[0] or resized.shape[1] > search_gray.shape[1]:
                continue

            res = cv2.matchTemplate(search_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_max_val:
                best_max_val = max_val
                best_max_loc = max_loc

        if best_max_val >= threshold:
            return (best_max_loc[0] + offset_x, best_max_loc[1] + offset_y), best_max_val
        
        return None, best_max_val
    
    def match_any_template(self, frame: np.ndarray, template_names: list, threshold=0.8, roi=None, scales=None):
        """
        Matches multiple templates and returns the one with the highest score.
        Optimized to prepare search area once.
        Returns dict: {'name': str, 'location': tuple, 'score': float}
        """
        search_gray, (offset_x, offset_y) = self._get_search_area(frame, roi)
        
        best_result = {'name': None, 'location': None, 'score': 0.0}

        if scales is None:
            scales = [1.0]

        for name in template_names:
            if name not in self.templates:
                continue
            
            template_gray = self.templates_gray.get(name)
            if template_gray is None: continue # Should not happen

            current_best_score = -1
            current_best_loc = None

            for scale in scales:
                if scale == 1.0:
                    resized = template_gray
                else:
                    w = int(template_gray.shape[1] * scale)
                    h = int(template_gray.shape[0] * scale)
                    if w <= 0 or h <= 0: continue
                    resized = cv2.resize(template_gray, (w, h))

                if resized.shape[0] > search_gray.shape[0] or resized.shape[1] > search_gray.shape[1]:
                    continue

                res = cv2.matchTemplate(search_gray, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > current_best_score:
                    current_best_score = max_val
                    current_best_loc = max_loc

            if current_best_score > best_result['score']:
                best_result['score'] = current_best_score
                best_result['name'] = name
                best_result['location'] = (current_best_loc[0] + offset_x, current_best_loc[1] + offset_y) if current_best_loc else None

        if best_result['score'] < threshold:
            best_result['location'] = None

        return best_result

    def match_all_templates(self, frame: np.ndarray, threshold=0.8, roi=None, scales=None):
        """
        Matches all loaded templates against the frame.
        Optimized to prepare search area once.
        Returns dict of {template_name: (location, score)} for matches above threshold.
        """
        search_gray, (offset_x, offset_y) = self._get_search_area(frame, roi)
        matches = {}

        if scales is None:
            scales = [1.0]

        for name in self.templates.keys():
            template_gray = self.templates_gray[name]
            best_score = -1
            best_loc = None

            for scale in scales:
                if scale == 1.0:
                    resized = template_gray
                else:
                    w = int(template_gray.shape[1] * scale)
                    h = int(template_gray.shape[0] * scale)
                    if w <= 0 or h <= 0: continue
                    resized = cv2.resize(template_gray, (w, h))

                if resized.shape[0] > search_gray.shape[0] or resized.shape[1] > search_gray.shape[1]:
                    continue

                res = cv2.matchTemplate(search_gray, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > best_score:
                    best_score = max_val
                    best_loc = max_loc

            if best_score >= threshold:
                loc = (best_loc[0] + offset_x, best_loc[1] + offset_y)
                matches[name] = (loc, best_score)
                logger.debug(f"Template {name} matched with score {best_score:.3f}")

        return matches

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
