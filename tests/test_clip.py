import pytest
from unittest.mock import MagicMock, patch
from src.clip.time_calculator import TimeCalculator
from src.clip.overlap_merger import OverlapMerger
from src.clip.multikill_detector import MultiKillDetector
from src.clip.clip_extractor import ClipExtractor

def test_time_calculator():
    calc = TimeCalculator(pre_kill_time=3.0, post_kill_time=1.0)
    events = [
        {"timestamp_ms": 10000, "type": "kill"} # 10s
    ]
    segments = calc.calculate_segments(events)
    assert len(segments) == 1
    assert segments[0]["start"] == 7.0
    assert segments[0]["end"] == 11.0

def test_overlap_merger():
    merger = OverlapMerger()
    segments = [
        {"start": 10.0, "end": 15.0, "event": {"id": 1}},
        {"start": 14.0, "end": 20.0, "event": {"id": 2}}, # Overlaps
        {"start": 30.0, "end": 35.0, "event": {"id": 3}}  # Gap
    ]
    merged = merger.merge(segments)
    assert len(merged) == 2
    assert merged[0]["start"] == 10.0
    assert merged[0]["end"] == 20.0
    assert len(merged[0]["events"]) == 2
    assert merged[1]["start"] == 30.0
    assert merged[1]["end"] == 35.0

def test_multikill_detector():
    detector = MultiKillDetector()
    merged_clips = [
        {
            "events": [
                {"timestamp_ms": 10000},
                {"timestamp_ms": 11000}
            ]
        },
        {
            "events": [
                {"timestamp_ms": 30000}
            ]
        }
    ]
    processed = detector.detect(merged_clips)
    assert processed[0]["kill_type"] == "double_kill"
    assert processed[1]["kill_type"] == "single_kill"

@patch("src.clip.clip_extractor.ClipCutter")
def test_clip_extractor_logic(mock_cutter_class):
    mock_cutter = mock_cutter_class.return_value
    config = {
        "highlights": {"pre_kill_time": 2, "post_kill_time": 1},
        "video": {"ffmpeg_path": "ffmpeg", "hwaccel": "cpu"}
    }
    extractor = ClipExtractor(config)
    
    events = [
        {"timestamp_ms": 5000, "type": "kill"},
        {"timestamp_ms": 6000, "type": "kill"}
    ]
    
    # Mock extract_clips internal behavior or just call it
    # We need to make sure output_dir exists or mock os.makedirs
    with patch("os.makedirs"), patch("src.clip.clip_extractor.open", create=True):
        clips = extractor.extract_clips("test.mp4", events, "output/test")
        
    assert len(clips) == 1
    assert clips[0]["kill_type"] == "double_kill"
    mock_cutter.cut_segment.assert_called_once()
