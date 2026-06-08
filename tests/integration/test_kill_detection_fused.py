import pytest
import numpy as np
import cv2
import time
import os
import shutil
from unittest.mock import MagicMock, patch

# Add src to python path if needed (but pytest usually handles it if run from root)
from src.ai.kill_detector import KillDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.yolo_detector import YoloDetector
from src.ai.ocr_detector import OCRDetector
from src.debug.detection_debugger import DetectionDebugger

@pytest.fixture
def mock_config():
    return {
        'detection': {
            'confidence_threshold': 0.5,
            'killfeed_roi': [0.7, 0.7, 0.2, 0.2],
            'colors': {
                'kill_blue': {
                    'lower': [100, 150, 50],
                    'upper': [130, 255, 255]
                }
            },
            'ocr': {
                'enabled': True,
                'required': False,
                'keywords': ["击杀", "KILL"],
                'similarity_threshold': 0.8
            },
            'prefilter': {
                'color_threshold': 0.01
            },
            'weights': {
                'ocr': 0.4,
                'template': 0.3,
                'color': 0.2,
                'yolo': 0.1
            }
        }
    }

@pytest.fixture
def mock_yolo():
    yolo = MagicMock(spec=YoloDetector)
    yolo.detect_single.return_value = []
    yolo.detect_batch.return_value = [[]]
    return yolo

@pytest.fixture
def mock_ocr():
    ocr = MagicMock(spec=OCRDetector)
    ocr.find_keywords.return_value = {'found': False, 'confidence': 0.0}
    return ocr

@pytest.fixture
def cv_matcher():
    matcher = OpenCVMatcher()
    # Mock templates to avoid needing real files
    matcher.templates = {'skull': np.zeros((10, 10), dtype=np.uint8)}
    matcher.templates_gray = {'skull': np.zeros((10, 10), dtype=np.uint8)}
    return matcher

def create_dummy_frame(color_hsv=None, roi=None, fill_percent=0.0):
    """Creates a dummy frame with a specific color in the ROI."""
    roi = roi or [0.7, 0.7, 0.2, 0.2]
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    if color_hsv is not None and fill_percent > 0:
        h, w = frame.shape[:2]
        tx, ty, tw, th = int(roi[0]*w), int(roi[1]*h), int(roi[2]*w), int(roi[3]*h)
        
        # Convert HSV to BGR for the frame
        color_bgr = cv2.cvtColor(np.uint8([[color_hsv]]), cv2.COLOR_HSV2BGR)[0][0]
        
        # Fill a portion of the ROI
        fill_w = int(tw * fill_percent)
        frame[ty:ty+th, tx:tx+fill_w] = color_bgr
        
    return frame

def test_detection_debugger_save(mock_config):
    """TASK-039: Verify DetectionDebugger saves frames."""
    debugger = DetectionDebugger(mock_config)
    frame = create_dummy_frame()
    results = {
        "is_kill": True,
        "confidence": 0.85,
        "signals": {"ocr": 0.9, "template": 0.8, "yolo": 0.7, "color": 0.9}
    }
    
    debug_dir = "temp/test_debug_viz"
    if os.path.exists(debug_dir):
        shutil.rmtree(debug_dir)
    if not os.path.exists("temp"):
        os.makedirs("temp")
    os.makedirs(debug_dir)
    
    save_path = os.path.join(debug_dir, "test_frame.jpg")
    debugger.save_debug_frame(frame, results, save_path)
    
    assert os.path.exists(save_path)
    # Check if file has content
    assert os.path.getsize(save_path) > 0
    
    # Clean up
    shutil.rmtree(debug_dir)

def test_kill_detection_true_positive(mock_config, mock_yolo, mock_ocr, cv_matcher):
    """TASK-035: Test weighted logic with all signals present."""
    detector = KillDetector(mock_yolo, cv_matcher, mock_config, ocr_detector=mock_ocr)
    
    # 1. Setup signals
    # Color match (Blue)
    frame = create_dummy_frame(color_hsv=[115, 200, 200], fill_percent=0.05)
    
    # OCR match
    mock_ocr.find_keywords.return_value = {'found': True, 'confidence': 1.0, 'matched_keyword': "击杀"}
    
    # Template match
    with patch.object(cv_matcher, 'match_template', return_value=((100, 100), 0.9)):
        # YOLO match
        mock_yolo.detect_single.return_value = [{'name': 'kill', 'conf': 0.8}]
        
        # 2. Process
        result = detector.process_frame(frame)
        
        # 3. Verify
        assert result['is_kill'] is True
        assert result['confidence'] > 0.5
        assert result['signals']['ocr'] == 1.0
        assert result['signals']['template'] == 0.9
        assert result['signals']['yolo'] == 0.8

def test_kill_detection_hard_negative(mock_config, mock_yolo, mock_ocr, cv_matcher):
    """TASK-036: Test 'Hard Negatives' (enemy name in ROI but no kill text)."""
    detector = KillDetector(mock_yolo, cv_matcher, mock_config, ocr_detector=mock_ocr)
    
    # 1. Setup signals: Only color matches (enemy name is often red/blue)
    frame = create_dummy_frame(color_hsv=[115, 200, 200], fill_percent=0.05)
    
    # No OCR match
    mock_ocr.find_keywords.return_value = {'found': False, 'confidence': 0.0}
    
    # No Template match
    with patch.object(cv_matcher, 'match_template', return_value=(None, 0.2)):
        # No YOLO match
        mock_yolo.detect_single.return_value = []
        
        # 2. Process
        result = detector.process_frame(frame)
        
        # 3. Verify: Should fail because weights for OCR/Template/YOLO are 0
        assert result['is_kill'] is False
        assert result['confidence'] < 0.5

def test_kill_detection_ocr_required(mock_config, mock_yolo, mock_ocr, cv_matcher):
    """TASK-037: Test OCR required vs optional."""
    # Scenario: OCR Required = True
    config = mock_config.copy()
    config['detection'] = mock_config['detection'].copy()
    config['detection']['ocr'] = mock_config['detection']['ocr'].copy()
    config['detection']['ocr']['required'] = True
    
    detector = KillDetector(mock_yolo, cv_matcher, config, ocr_detector=mock_ocr)
    
    frame = create_dummy_frame(color_hsv=[115, 200, 200], fill_percent=0.05)
    
    # OCR NOT FOUND
    mock_ocr.find_keywords.return_value = {'found': False, 'confidence': 0.0}
    
    # But other signals are strong
    with patch.object(cv_matcher, 'match_template', return_value=((100, 100), 0.9)):
        mock_yolo.detect_single.return_value = [{'name': 'kill', 'conf': 0.9}]
        
        result = detector.process_frame(frame)
        
        # Should be FALSE because OCR is required
        assert result['is_kill'] is False
        assert result['signals']['ocr'] == 0.0

def test_kill_detection_ocr_optional(mock_config, mock_yolo, mock_ocr, cv_matcher):
    """TASK-037: Test OCR optional."""
    # Scenario: OCR Required = False (Default in mock_config)
    detector = KillDetector(mock_yolo, cv_matcher, mock_config, ocr_detector=mock_ocr)
    
    frame = create_dummy_frame(color_hsv=[115, 200, 200], fill_percent=0.05)
    
    # OCR NOT FOUND
    mock_ocr.find_keywords.return_value = {'found': False, 'confidence': 0.0}
    
    # But other signals are strong enough to carry it
    with patch.object(cv_matcher, 'match_template', return_value=((100, 100), 0.9)):
        mock_yolo.detect_single.return_value = [{'name': 'kill', 'conf': 0.9}]
        
        result = detector.process_frame(frame)
        
        # Should be TRUE because OCR is optional and others are strong
        assert result['is_kill'] is True
        assert result['confidence'] >= 0.5

def test_performance_prefilter(mock_config, mock_yolo, mock_ocr, cv_matcher):
    """TASK-038: Measure performance (FPS) with pre-filter."""
    detector = KillDetector(mock_yolo, cv_matcher, mock_config, ocr_detector=mock_ocr)
    
    # Frame that fails pre-filter (Empty)
    black_frame = create_dummy_frame(fill_percent=0.0)
    
    # Frame that passes pre-filter
    color_frame = create_dummy_frame(color_hsv=[115, 200, 200], fill_percent=0.1)
    
    # Warm up
    detector.process_frame(black_frame)
    detector.process_frame(color_frame)
    
    # Measure black frame
    start = time.time()
    iters = 50
    for _ in range(iters):
        detector.process_frame(black_frame)
    black_time = (time.time() - start) / iters
    
    # Measure color frame
    start = time.time()
    for _ in range(iters):
        detector.process_frame(color_frame)
    color_time = (time.time() - start) / iters
    
    print(f"\nAverage time (Pre-filter skip): {black_time*1000:.2f}ms")
    print(f"Average time (Full process): {color_time*1000:.2f}ms")
    
    # Pre-filter should be significantly faster
    assert black_time < color_time
    assert black_time < 0.01 # Should be very fast (< 10ms)

def test_weighted_normalization(mock_config, mock_yolo, mock_ocr, cv_matcher):
    """Verify weight normalization when OCR is disabled."""
    config = mock_config.copy()
    config['detection'] = mock_config['detection'].copy()
    config['detection']['ocr'] = mock_config['detection']['ocr'].copy()
    config['detection']['ocr']['enabled'] = False
    
    detector = KillDetector(mock_yolo, cv_matcher, config, ocr_detector=mock_ocr)
    
    frame = create_dummy_frame(color_hsv=[115, 200, 200], fill_percent=0.05)
    
    # Full signals except OCR
    with patch.object(cv_matcher, 'match_template', return_value=((100, 100), 1.0)):
        mock_yolo.detect_single.return_value = [{'name': 'kill', 'conf': 1.0}]
        
        result = detector.process_frame(frame)
        
        # When OCR is disabled, weights should be redistributed or normalized.
        assert result['confidence'] > 0.9
