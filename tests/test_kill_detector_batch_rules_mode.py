import numpy as np
import pytest
from unittest.mock import MagicMock

from src.ai.kill_detector import KillDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.yolo_detector import YoloDetector


# ==================== OR-of-AND RULES MODE TESTS ====================

@pytest.fixture
def mock_yolo_model_with_kill():
    """Mock YOLO model that returns a kill detection for each frame in batch."""
    def mock_call(frames, **kwargs):
        """Return one result per frame in the batch."""
        results = []
        for _ in frames:
            mock_result = MagicMock()
            mock_box = MagicMock()
            # Use MagicMock with proper return values instead of torch.tensor
            mock_box.xyxy = [MagicMock(tolist=MagicMock(return_value=[10, 10, 20, 20]))]
            mock_box.conf = [MagicMock(__float__=MagicMock(return_value=0.9))]
            mock_box.cls = [MagicMock(__int__=MagicMock(return_value=0))]
            mock_result.boxes = [mock_box]
            mock_result.names = {0: 'kill'}
            results.append(mock_result)
        return results
    
    mock = MagicMock(side_effect=mock_call)
    return mock


@pytest.fixture
def mock_yolo_model_no_kill():
    """Mock YOLO model that returns NO kill detection for each frame in batch."""
    def mock_call(frames, **kwargs):
        """Return one result per frame in the batch (no detections)."""
        results = []
        for _ in frames:
            mock_result = MagicMock()
            mock_result.boxes = []  # No detections
            mock_result.names = {0: 'kill'}
            results.append(mock_result)
        return results
    
    mock = MagicMock(side_effect=mock_call)
    return mock


class TestKillDetectorRulesModeBatch:
    """Tests for rules mode in batch processing path."""
    
    def test_batch_rules_mode_confidence_1_0(self, mock_yolo_model_with_kill):
        """
        In batch processing (process_video_batch), rules mode should produce
        confidence=1.0 for events that match a rule.
        """
        frames = []
        timestamps = []
        
        # Create 3 frames with blue color
        for i in range(3):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            frame[40:60, 40:60] = (255, 0, 0)  # Blue
            frames.append(frame)
            timestamps.append(i * 1000)
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': [
                    {
                        'name': 'yolo_and_color',
                        'enabled': True,
                        'require': ['yolo', 'color']
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        events = detector.process_video_batch(frames, timestamps)
        
        # Should have events for frames that pass rules
        assert len(events) >= 1
        
        # All events should have confidence=1.0 in rules mode
        for event in events:
            assert event["confidence"] == 1.0
            assert event["type"] == "kill"
    
    def test_batch_legacy_mode_weighted_confidence(self, mock_yolo_model_with_kill):
        """
        In batch processing with legacy mode (no rules), events should have
        weighted confidence values (not exactly 1.0).
        """
        frames = []
        timestamps = []
        
        for i in range(3):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            frame[40:60, 40:60] = (255, 0, 0)  # Blue
            frames.append(frame)
            timestamps.append(i * 1000)
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.3,  # Low threshold for legacy to pass
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': []  # Empty = legacy mode
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_with_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        events = detector.process_video_batch(frames, timestamps)
        
        assert len(events) >= 1
        
        # Legacy mode: confidence should be weighted (0 < conf < 1)
        for event in events:
            assert 0.0 < event["confidence"] < 1.0
    
    def test_batch_rules_mode_no_events_when_no_match(self, mock_yolo_model_no_kill):
        """
        Batch processing should produce no events when rules don't match.
        """
        frames = []
        timestamps = []
        
        for i in range(3):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            frame[40:60, 40:60] = (255, 0, 0)  # Blue - color passes
            frames.append(frame)
            timestamps.append(i * 1000)
        
        game_config = {
            'detection': {
                'confidence_threshold': 0.5,
                'killfeed_roi': [0, 0, 1, 1],
                'colors': {
                    'kill_color': {
                        'lower': [100, 100, 100],
                        'upper': [140, 255, 255]
                    }
                },
                'prefilter': {'color_threshold': 0.01},
                'rules': [
                    {
                        'name': 'require_yolo',
                        'enabled': True,
                        'require': ['yolo', 'color']  # yolo=False, so no match
                    }
                ]
            }
        }
        
        yolo = YoloDetector(mock_yolo_model_no_kill)
        cv_matcher = OpenCVMatcher(game_config)
        detector = KillDetector(yolo, cv_matcher, game_config)
        
        events = detector.process_video_batch(frames, timestamps)
        
        # No events because yolo signal is False
        assert len(events) == 0


