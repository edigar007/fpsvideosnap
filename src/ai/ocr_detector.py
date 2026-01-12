import numpy as np
import cv2
from typing import List, Dict, Union, Optional
try:
    from fuzzywuzzy import fuzz
except ImportError:
    # Fallback to a simple ratio if fuzzywuzzy is not available
    def fuzz_ratio(s1, s2):
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio()
    class Fuzz:
        @staticmethod
        def ratio(s1, s2):
            return int(fuzz_ratio(s1, s2) * 100)
    fuzz = Fuzz()

from src.utils.logger import get_logger

logger = get_logger("ocr_detector")

try:
    from paddleocr import PaddleOCR
    HAS_PADDLEOCR = True
except ImportError:
    HAS_PADDLEOCR = False

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

if not HAS_PADDLEOCR and not HAS_EASYOCR:
    logger.warning("Neither PaddleOCR nor EasyOCR installed. OCRDetector will be limited.")

class OCRDetector:
    """
    OCR module for verifying kill text in ROIs using PaddleOCR (preferred) or EasyOCR (fallback).
    """
    def __init__(self, lang: str = 'ch', use_gpu: bool = True):
        """
        Initialize OCR Engine.
        
        Args:
            lang: Language code ('ch' for Chinese/English, 'en' for English).
            use_gpu: Whether to use GPU for inference.
        """
        self.lang = lang
        self.use_gpu = use_gpu
        self.ocr_engine = None
        self.engine_type = None
        
        if HAS_PADDLEOCR:
            try:
                # PaddleOCR 3.x 只使用最基本的参数
                self.ocr_engine = PaddleOCR(use_angle_cls=True, lang=self.lang)
                self.engine_type = 'paddle'
                logger.info(f"Initialized PaddleOCR (lang={lang})")
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")

        if not self.ocr_engine and HAS_EASYOCR:
            try:
                # EasyOCR uses 'ch_sim' for simplified chinese
                eocr_lang = ['ch_sim', 'en'] if lang == 'ch' else ['en']
                self.ocr_engine = easyocr.Reader(eocr_lang, gpu=self.use_gpu)
                self.engine_type = 'easyocr'
                logger.info(f"Initialized EasyOCR (lang={eocr_lang}, gpu={use_gpu})")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")

        if not self.ocr_engine:
            logger.error("No OCR engine available.")

    def detect_text(self, image: np.ndarray, roi: Optional[List[int]] = None) -> List[Dict]:
        """
        Detects all text in an image or specific ROI.
        
        Args:
            image: Input image (BGR format from OpenCV).
            roi: Optional [x, y, w, h] to limit search area.
            
        Returns:
            List of detected text items: [{'text': str, 'confidence': float, 'bbox': List}]
        """
        if not self.ocr_engine:
            return []

        target_img = image
        offset_x, offset_y = 0, 0
        
        if roi:
            x, y, w, h = roi
            img_h, img_w = image.shape[:2]
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(img_w, x + w), min(img_h, y + h)
            
            if x2 <= x1 or y2 <= y1:
                logger.warning(f"Invalid ROI: {roi}")
                return []
                
            target_img = image[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1

        try:
            detections = []
            if self.engine_type == 'paddle':
                # PaddleOCR 3.x predict 返回列表，第一个元素包含所有结果
                result = self.ocr_engine.predict(target_img)
                if result and len(result) > 0:
                    page_result = result[0]
                    rec_texts = page_result.get('rec_texts', [])
                    rec_scores = page_result.get('rec_scores', [])
                    rec_polys = page_result.get('rec_polys', [])
                    
                    for i, text in enumerate(rec_texts):
                        confidence = rec_scores[i] if i < len(rec_scores) else 1.0
                        bbox = rec_polys[i] if i < len(rec_polys) else [[0, 0], [0, 0], [0, 0], [0, 0]]
                        detections.append({
                            'text': text,
                            'confidence': float(confidence),
                            'bbox': [[float(p[0] + offset_x), float(p[1] + offset_y)] for p in bbox]
                        })
            elif self.engine_type == 'easyocr':
                # EasyOCR returns [[bbox, text, confidence], ...]
                # bbox is [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                result = self.ocr_engine.readtext(target_img)
                for (bbox, text, confidence) in result:
                    detections.append({
                        'text': text,
                        'confidence': float(confidence),
                        'bbox': [[float(p[0] + offset_x), float(p[1] + offset_y)] for p in bbox]
                    })
            
            return detections
        except Exception as e:
            logger.error(f"OCR detection failed ({self.engine_type}): {e}")
            return []

    def find_keywords(self, image: np.ndarray, keywords: List[str], roi: Optional[List[int]] = None, threshold: float = 0.8) -> Dict:
        """
        Searches for specific keywords using fuzzy matching.
        
        Args:
            image: Input image.
            keywords: List of target strings (e.g., ["击杀", "KILL"]).
            roi: Optional ROI.
            threshold: Similarity threshold (0.0 to 1.0).
            
        Returns:
            Dict: {
                "found": bool, 
                "matched_keyword": str, 
                "text": str, 
                "confidence": float, 
                "similarity": float,
                "bbox": list
            }
        """
        detections = self.detect_text(image, roi)
        
        best_match = {
            "found": False,
            "matched_keyword": None,
            "text": None,
            "confidence": 0.0,
            "similarity": 0.0,
            "bbox": None
        }

        for det in detections:
            text = det['text'].strip()
            for kw in keywords:
                # Calculate similarity (0-100) -> (0.0-1.0)
                similarity = fuzz.ratio(text.lower(), kw.lower()) / 100.0
                
                if similarity >= threshold and similarity > best_match["similarity"]:
                    best_match.update({
                        "found": True,
                        "matched_keyword": kw,
                        "text": text,
                        "confidence": det['confidence'],
                        "similarity": similarity,
                        "bbox": det['bbox']
                    })
        
        return best_match
