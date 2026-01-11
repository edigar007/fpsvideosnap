import os
import shutil
import pytest
import json
import yaml
from src.report.report_generator import ReportGenerator
from src.history.history_manager import HistoryManager

@pytest.fixture
def temp_dirs():
    test_output = "temp_test_output"
    test_history = "temp_test_history"
    os.makedirs(test_output, exist_ok=True)
    os.makedirs(test_history, exist_ok=True)
    yield test_output, test_history
    if os.path.exists(test_output):
        shutil.rmtree(test_output)
    if os.path.exists(test_history):
        shutil.rmtree(test_history)

def test_report_generation(temp_dirs):
    output_dir, _ = temp_dirs
    generator = ReportGenerator(output_dir)
    
    video_info = {
        "video_path": "test_video.mp4",
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "duration_str": "00:05:30"
    }
    
    clips = [
        {"start_ms": 1000, "end_ms": 6000, "kill_count": 1, "kill_type": "single_kill"},
        {"start_ms": 20000, "end_ms": 30000, "kill_count": 3, "kill_type": "triple_kill", "events": [{"timestamp_ms": 25000}]}
    ]
    
    config = {
        "global": {"debug": True},
        "detection": {"confidence_threshold": 0.5},
        "highlights": {"pre_kill_time": 3.0}
    }
    
    logs = ["[INFO] Starting", "[DEBUG] Frame 1 processed"]
    
    report_path = generator.generate(video_info, clips, config, logs)
    
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# FPS Video Snap Processing Report" in content
        assert "1920x1080" in content
        assert "Total Kills Detected**: 4" in content
        assert "Triple Kill: 1" in content
        assert "Detailed Clips List" in content
        assert "test_video.mp4" in content

def test_report_empty_cases(temp_dirs):
    output_dir, _ = temp_dirs
    generator = ReportGenerator(output_dir)
    
    video_info = {}
    clips = []
    config = {}
    
    report_path = generator.generate(video_info, clips, config)
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "No kills detected" in content

def test_history_manager(temp_dirs):
    _, history_dir = temp_dirs
    config = {
        "global": {
            "keep_history_days": 1,
            "max_history_files": 4
        }
    }
    manager = HistoryManager(history_dir, config)
    
    test_config = {"key": "val"}
    test_results = [{"clip": 1}]
    
    # Save 3 runs (6 files total)
    manager.save_run(test_config, test_results)
    manager.save_run(test_config, test_results)
    manager.save_run(test_config, test_results)
    
    files = os.listdir(history_dir)
    # Since max_history_files is 4, it should have cleaned up 2 files from the first run
    # (Actually my logic cleans up based on total file count > max_history_files)
    assert len(files) <= 4

def test_history_cleanup_by_age(temp_dirs, monkeypatch):
    _, history_dir = temp_dirs
    config = {
        "global": {
            "keep_history_days": 0, # Expire immediately for testing
            "max_history_files": 100
        }
    }
    manager = HistoryManager(history_dir, config)
    
    # Create an old file
    old_file = os.path.join(history_dir, "config_old.yaml")
    with open(old_file, "w") as f: f.write("old")
    
    # Set its mtime to 2 days ago
    two_days_ago = os.path.getmtime(old_file) - (2 * 24 * 3600)
    os.utime(old_file, (two_days_ago, two_days_ago))
    
    manager.cleanup()
    
    assert not os.path.exists(old_file)
