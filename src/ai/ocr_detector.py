import numpy as np
import cv2
import os
import sys
import atexit
import importlib.util
import uuid
import threading
from typing import List, Dict, Optional

from src.utils.temp_manager import temp_manager
from src.ai.paddleocr_subprocess import PaddleOCRSubprocess
from src.utils.cuda_dll import setup_cuda_dll_directories

# Windows GPU 支持：必须在导入 PaddleOCR 之前设置 CUDA DLL 路径
if sys.platform == "win32":
    setup_cuda_dll_directories()

try:
    from rapidfuzz import fuzz
except ImportError:
    try:
        from fuzzywuzzy import fuzz
    except ImportError:
        # Fallback to a simple ratio if neither fuzzy library is available
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

# 惰性加载：避免在 import 阶段同时加载 Paddle/Torch 导致 DLL 冲突（Windows 上较常见）
HAS_PADDLEOCR = importlib.util.find_spec("paddleocr") is not None
HAS_EASYOCR = importlib.util.find_spec("easyocr") is not None

if not HAS_PADDLEOCR and not HAS_EASYOCR:
    logger.warning("Neither PaddleOCR nor EasyOCR installed. OCRDetector will be limited.")


_PADDLE_SUBPROC_LOCK = threading.Lock()
_PADDLE_SUBPROC_SINGLETON: Optional[PaddleOCRSubprocess] = None
_PADDLE_SUBPROC_REFCOUNT = 0


def _get_or_start_paddle_subprocess_worker() -> PaddleOCRSubprocess:
    global _PADDLE_SUBPROC_SINGLETON, _PADDLE_SUBPROC_REFCOUNT

    with _PADDLE_SUBPROC_LOCK:
        worker = _PADDLE_SUBPROC_SINGLETON
        if worker is None:
            worker = PaddleOCRSubprocess(PaddleOCRSubprocess.default())

            # 仅在 python/worker 脚本存在时启用（否则上层降级）
            if not worker.cfg.python_exe.exists():
                raise FileNotFoundError(f"Missing worker python: {worker.cfg.python_exe}")
            if not worker.cfg.worker_script.exists():
                raise FileNotFoundError(f"Missing worker script: {worker.cfg.worker_script}")

            worker.start()
            _PADDLE_SUBPROC_SINGLETON = worker

        else:
            worker.start()

        _PADDLE_SUBPROC_REFCOUNT += 1
        return worker


def _release_paddle_subprocess_worker() -> None:
    global _PADDLE_SUBPROC_SINGLETON, _PADDLE_SUBPROC_REFCOUNT

    with _PADDLE_SUBPROC_LOCK:
        if _PADDLE_SUBPROC_REFCOUNT > 0:
            _PADDLE_SUBPROC_REFCOUNT -= 1

        if _PADDLE_SUBPROC_REFCOUNT != 0:
            return

        worker = _PADDLE_SUBPROC_SINGLETON
        _PADDLE_SUBPROC_SINGLETON = None

    if worker:
        try:
            worker.close()
        except Exception as exc:
            logger.debug(f"Failed to close PaddleOCR subprocess worker: {exc}")


def _close_paddle_subprocess_worker_at_exit() -> None:
    # 进程退出时兜底回收
    global _PADDLE_SUBPROC_SINGLETON, _PADDLE_SUBPROC_REFCOUNT

    with _PADDLE_SUBPROC_LOCK:
        worker = _PADDLE_SUBPROC_SINGLETON
        _PADDLE_SUBPROC_SINGLETON = None
        _PADDLE_SUBPROC_REFCOUNT = 0

    if worker:
        try:
            worker.close()
        except Exception as exc:
            logger.debug(f"Failed to close PaddleOCR subprocess worker at exit: {exc}")


atexit.register(_close_paddle_subprocess_worker_at_exit)

class OCRDetector:
    """
    OCR module for verifying kill text in ROIs using PaddleOCR (preferred) or EasyOCR (fallback).
    """
    def __init__(self, lang: str = 'ch', use_gpu: bool = True, force_subprocess: bool = False):
        """
        Initialize OCR Engine.
        
        Args:
            lang: Language code ('ch' for Chinese/English, 'en' for English).
            use_gpu: Whether to use GPU for inference.
            force_subprocess: Force subprocess mode on Windows (bypasses torch check).
                             Useful for Config Assistant to avoid DLL conflicts.
        """
        self.lang = lang
        self.use_gpu = use_gpu
        self.force_subprocess = force_subprocess
        self.ocr_engine = None
        self.engine_type = None

        # 已知问题（Windows）：PyTorch(CUDA) 与 PaddlePaddle-GPU 在同一进程内常发生 DLL 冲突。
        # 若主流程已加载 torch（例如 YOLO/Ultralytics），或强制使用子进程模式，
        # 则用子进程运行 PaddleOCR(GPU)，避免 DLL 冲突。
        subprocess_mode = False
        if sys.platform == 'win32':
            if force_subprocess:
                subprocess_mode = True
            elif self.use_gpu and 'torch' in sys.modules:
                subprocess_mode = True
        
        if subprocess_mode:
            try:
                self.ocr_engine = _get_or_start_paddle_subprocess_worker()
                self.engine_type = 'paddle_subprocess'
                logger.info("Initialized PaddleOCR via subprocess worker (.venv_paddle)")
            except FileNotFoundError as e:
                logger.warning(
                    f"Subprocess OCR unavailable: {e}. "
                    "Install with: uv venv .venv_paddle && "
                    "uv pip install -r requirements-win-paddleocr-gpu-standalone.txt"
                )
                subprocess_mode = False
            except Exception as e:
                logger.warning(f"Subprocess OCR worker init failed: {e}")
                subprocess_mode = False
        
        if not subprocess_mode:
            if HAS_PADDLEOCR:
                try:
                    from paddleocr import PaddleOCR

                    # PaddleOCR 3.x使用 device 参数：'cpu' 或 'gpu:0'
                    # 即使安装了 GPU 版本，也可以通过 device='cpu' 强制使用 CPU
                    device = 'gpu:0' if self.use_gpu else 'cpu'
                    self.ocr_engine = PaddleOCR(
                        use_angle_cls=True,
                        lang=self.lang,
                        device=device
                    )
                    self.engine_type = 'paddle'
                    logger.info(f"Initialized PaddleOCR (lang={lang}, device={device})")
                except OSError as e:
                    # DLL errors are expected when PaddlePaddle conflicts with PyTorch
                    if "WinError 127" in str(e) or "DLL" in str(e):
                        logger.warning(
                            f"PaddleOCR unavailable (DLL conflict): {e}. "
                            "This is expected when PyTorch is loaded. Consider using force_subprocess=True."
                        )
                    else:
                        logger.exception("Failed to initialize PaddleOCR")
                    logger.info("Will try EasyOCR as fallback...")
                except Exception:
                    logger.exception("Failed to initialize PaddleOCR")
                    logger.info("Will try EasyOCR as fallback...")

        if not self.ocr_engine and HAS_EASYOCR:
            try:
                import easyocr

                # EasyOCR uses 'ch_sim' for simplified chinese
                eocr_lang = ['ch_sim', 'en'] if lang == 'ch' else ['en']
                self.ocr_engine = easyocr.Reader(eocr_lang, gpu=self.use_gpu)
                self.engine_type = 'easyocr'
                logger.info(f"Initialized EasyOCR (lang={eocr_lang}, gpu={use_gpu})")
            except Exception:
                logger.exception("Failed to initialize EasyOCR")

        if not self.ocr_engine:
            logger.error("No OCR engine available.")

    def close(self) -> None:
        if getattr(self, 'engine_type', None) == 'paddle_subprocess':
            try:
                _release_paddle_subprocess_worker()
            except Exception as exc:
                logger.debug(f"Failed to release PaddleOCR subprocess worker: {exc}")

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
            elif self.engine_type == 'paddle_subprocess':
                # 通过子进程 worker 调用 PaddleOCR，避免 Torch↔Paddle GPU DLL 冲突
                filename = f"ocr_{uuid.uuid4().hex}.png"
                image_path = temp_manager.get_temp_path(filename, subdir="ocr_worker")

                ok = cv2.imwrite(image_path, target_img)
                if not ok:
                    raise RuntimeError(f"Failed to write temp image: {image_path}")

                try:
                    detections = self.ocr_engine.predict_path(
                        image_path=image_path,
                        offset_x=offset_x,
                        offset_y=offset_y,
                        lang=self.lang,
                        device='gpu:0'
                    )
                finally:
                    try:
                        os.remove(image_path)
                    except OSError as exc:
                        logger.debug(f"Failed to remove temporary OCR image {image_path}: {exc}")
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

    def find_keywords(
        self,
        image: np.ndarray,
        keywords: List[str],
        roi: Optional[List[int]] = None,
        threshold: float = 0.8,
    ) -> Dict:
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
