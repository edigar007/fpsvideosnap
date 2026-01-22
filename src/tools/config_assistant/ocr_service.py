import os
import cv2
import numpy as np
from typing import List, Dict, Optional
from src.ai.ocr_detector import OCRDetector
from src.utils.logger import get_logger

logger = get_logger("config_assistant.ocr_service")


class OCRUnavailableError(Exception):
    """Raised when OCR service is not available."""
    pass


class OCRService:
    """
    Service layer for OCR operations in the Config Assistant.
    Provides text detection and caching for better performance.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCRService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once (prevent re-init on singleton reuse)
        if not hasattr(self, '_initialized'):
            self._detector = None
            self._initialized = False
            self._init_error: Optional[str] = None
            # Simple cache: (image_path, mtime, roi_tuple) -> results
            self._cache = {}

    def _ensure_initialized(self) -> None:
        """
        Lazy initialization of OCR detector.
        Called on first use rather than at import time.
        """
        if self._initialized:
            return
        
        self._initialized = True
        logger.info("Initializing OCR Service...")
        
        try:
            # Default to Chinese/English and GPU if available
            # Use force_subprocess=True on Windows to avoid DLL conflicts
            import sys
            force_subprocess = sys.platform == 'win32'
            self._detector = OCRDetector(lang='ch', use_gpu=True, force_subprocess=force_subprocess)
            logger.info("OCR Detector initialized successfully.")
        except OSError as e:
            # Handle DLL/CUDA errors specially
            if "WinError 127" in str(e) or "DLL" in str(e):
                self._init_error = "PaddleOCR unavailable: CUDA/cuDNN DLL not found. Use .venv_paddle environment."
                logger.warning(self._init_error)
            else:
                self._init_error = f"OCR initialization failed: {e}"
                logger.warning(self._init_error)
        except Exception as e:
            self._init_error = f"OCR initialization failed: {e}"
            logger.warning(self._init_error)

    def detect(self, image_path: str, roi: Optional[List[float]] = None) -> List[Dict]:
        """
        Detect text in an image, optionally limited to a ROI.
        
        Args:
            image_path: Path to the image file.
            roi: Optional ROI [x, y, w, h] as relative coordinates (0.0 to 1.0).
            
        Returns:
            List of detected items: [{'text': str, 'confidence': float, 'bbox': List[List[int]]}]
        """
        # Ensure OCR is initialized before use
        self._ensure_initialized()
        
        if self._detector is None:
            raise OCRUnavailableError(self._init_error or "OCR not initialized")

        if not os.path.exists(image_path):
            logger.error(f"Image path does not exist: {image_path}")
            return []

        # Cache check
        try:
            mtime = os.path.getmtime(image_path)
            roi_key = tuple(roi) if roi else None
            cache_key = (image_path, mtime, roi_key)
            
            if cache_key in self._cache:
                logger.debug(f"OCR Cache hit for {image_path} with ROI {roi}")
                return self._cache[cache_key]
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
            cache_key = None

        try:
            logger.info(f"Starting OCR detection for: {image_path}, ROI: {roi}")
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image from: {image_path}")
                return []

            h_img, w_img = image.shape[:2]
            logger.info(f"Image size: {w_img}x{h_img}")
            
            pixel_roi = None
            if roi:
                # Convert relative ROI to pixel coordinates
                rx, ry, rw, rh = roi
                pixel_roi = [
                    int(rx * w_img),
                    int(ry * h_img),
                    int(rw * w_img),
                    int(rh * h_img)
                ]
                logger.info(f"Pixel ROI: {pixel_roi}")

            logger.info("Calling OCR detector...")
            results = self._detector.detect_text(image, roi=pixel_roi)
            logger.info(f"OCR detection complete. Found {len(results)} text items.")
            
            # Update cache
            if cache_key:
                # Limit cache size (keep last 50 items)
                if len(self._cache) >= 50:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[cache_key] = results
                
            return results
        except OCRUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Error during OCR detection: {e}")
            return []


# Singleton accessor with lazy instantiation
_ocr_service_instance: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """
    Get the singleton OCRService instance.
    Creates the instance on first call (lazy initialization).
    """
    global _ocr_service_instance
    if _ocr_service_instance is None:
        _ocr_service_instance = OCRService()
    return _ocr_service_instance

