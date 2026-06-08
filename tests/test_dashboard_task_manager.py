from queue import Queue
from unittest.mock import patch

from src.pipeline.pipeline import StageStatus
from src.pipeline.results import PipelineRunResult
from src.tools.dashboard.task_manager import _run_processing_task
from src.tools.dashboard.task_manager import _make_output_file


class _CancelEvent:
    def is_set(self):
        return False


def test_make_output_file_metadata(tmp_path):
    output_path = tmp_path / "highlights.mp4"
    output_path.write_bytes(b"video")

    result = _make_output_file(str(output_path), "高光视频", "video")

    assert result["path"] == str(output_path.resolve())
    assert result["name"] == "highlights.mp4"
    assert result["label"] == "高光视频"
    assert result["type"] == "video"
    assert result["exists"] is True
    assert result["size"] == 5


def test_make_output_file_missing_path_returns_none():
    assert _make_output_file(None, "高光视频", "video") is None


def test_processing_task_fails_when_pipeline_run_fails(tmp_path):
    video_path = str(tmp_path / "input.mp4")
    progress_queue = Queue()
    result_queue = Queue()

    class FailingPipeline:
        def __init__(self, config, progress_callback=None):
            self.results = {}
            self.stages = {name: type("Stage", (), {"status": StageStatus.PENDING})() for name in [
                "metadata",
                "frames",
                "detection",
                "clips",
                "join",
                "audio",
            ]}

        def run_full_result(self, path):
            return PipelineRunResult(
                success=False,
                mode="full",
                video_path=path,
                failed_stage="detection",
                error="detection failed",
            )

    with patch("src.config.config_loader.get_config", return_value={}), \
         patch("src.pipeline.pipeline.Pipeline", FailingPipeline):
        _run_processing_task([video_path], "battlefield6", progress_queue, result_queue, _CancelEvent())

    result = result_queue.get_nowait()

    assert result["success"] is False
    assert result["error"] == "detection failed"
    assert result["failed_video"] == video_path
    assert result["failed_stage"] == "detection"


def test_processing_task_forwards_real_detection_progress(tmp_path):
    video_path = str(tmp_path / "input.mp4")
    progress_queue = Queue()
    result_queue = Queue()

    class ProgressPipeline:
        def __init__(self, config, progress_callback=None):
            self.progress_callback = progress_callback
            self.results = {"frames": ["f1.jpg", "f2.jpg", "f3.jpg"], "events": [], "clips": []}
            self.stages = {name: type("Stage", (), {"status": StageStatus.PENDING})() for name in [
                "metadata",
                "frames",
                "detection",
                "clips",
                "join",
                "audio",
            ]}

        def run_full_result(self, path):
            self.stages["detection"].status = StageStatus.RUNNING
            self.progress_callback({"stage": "detection", "processed": 2, "total": 3, "detected": 1})
            self.stages["detection"].status = StageStatus.SUCCESS
            return PipelineRunResult(success=True, mode="full", video_path=path)

    with patch("src.config.config_loader.get_config", return_value={}), \
         patch("src.pipeline.pipeline.Pipeline", ProgressPipeline):
        _run_processing_task([video_path], "battlefield6", progress_queue, result_queue, _CancelEvent())

    progress_messages = []
    while not progress_queue.empty():
        progress_messages.append(progress_queue.get_nowait())

    assert any(
        msg.get("type") == "progress"
        and msg.get("current_stage") == "detection"
        and msg.get("detection_progress") == 2
        and msg.get("detection_total") == 3
        and msg.get("detected_kills") == 1
        for msg in progress_messages
    )
    assert result_queue.get_nowait()["success"] is True
