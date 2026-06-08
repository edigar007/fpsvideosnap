from queue import Queue
from queue import Empty
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.pipeline.pipeline import StageStatus
from src.pipeline.results import PipelineRunResult
from src.tools.dashboard.task_manager import _make_output_file
from src.tools.dashboard.task_manager import ProgressInfo, TaskInfo, TaskManager, TaskRuntime, TaskStatus
from src.tools.dashboard.task_manager import _run_processing_task


class _CancelEvent:
    def __init__(self):
        self.cancelled = False

    def set(self):
        self.cancelled = True

    def is_set(self):
        return self.cancelled


class _FakeProcess:
    def __init__(self):
        self.started = False
        self.alive = True
        self.terminated = False
        self.killed = False
        self.join_calls = []

    def start(self):
        self.started = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_calls.append(timeout)

    def terminate(self):
        self.terminated = True
        self.alive = False

    def kill(self):
        self.killed = True
        self.alive = False


class _ClosableQueue:
    def __init__(self, item=None):
        self.item = item
        self.closed = False
        self.joined = False

    def get_nowait(self):
        if self.item is None:
            raise Empty
        item = self.item
        self.item = None
        return item

    def close(self):
        self.closed = True

    def join_thread(self):
        self.joined = True


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


def test_task_runtime_cancel_escalates_after_grace_period():
    process = _FakeProcess()
    cancel_event = _CancelEvent()
    progress_queue = _ClosableQueue()
    result_queue = _ClosableQueue()
    runtime = TaskRuntime(
        process=process,
        progress_queue=progress_queue,
        result_queue=result_queue,
        cancel_event=cancel_event,
    )

    runtime.request_cancel(graceful_timeout=0.01, terminate_timeout=0.02)

    assert cancel_event.is_set() is True
    assert process.join_calls == [0.01, 0.02]
    assert process.terminated is True
    assert process.killed is False


def test_task_runtime_close_releases_queues():
    process = _FakeProcess()
    process.alive = False
    progress_queue = _ClosableQueue()
    result_queue = _ClosableQueue()
    runtime = TaskRuntime(
        process=process,
        progress_queue=progress_queue,
        result_queue=result_queue,
        cancel_event=_CancelEvent(),
    )

    runtime.close()

    assert progress_queue.closed is True
    assert progress_queue.joined is True
    assert result_queue.closed is True
    assert result_queue.joined is True


def test_task_manager_monitor_keeps_cancelled_status_when_result_arrives():
    manager = TaskManager()
    manager.clear()
    process = _FakeProcess()
    process.alive = False
    cancel_event = _CancelEvent()
    cancel_event.set()
    manager.task_info = TaskInfo(status=TaskStatus.RUNNING, progress=ProgressInfo())
    manager.runtime = TaskRuntime(
        process=process,
        progress_queue=_ClosableQueue(),
        result_queue=_ClosableQueue({"success": True}),
        cancel_event=cancel_event,
    )

    manager._monitor_process()

    assert manager.task_info.status == TaskStatus.CANCELLED
    manager.clear()


def test_task_manager_clear_closes_runtime_and_status_is_safe():
    manager = TaskManager()
    manager.clear()
    fake_runtime = SimpleNamespace(close_called=False)

    def close():
        fake_runtime.close_called = True

    fake_runtime.close = close
    manager.runtime = fake_runtime
    manager.task_info = TaskInfo(status=TaskStatus.RUNNING)

    manager.clear()

    assert fake_runtime.close_called is True
    assert manager.get_status()["status"] == "idle"


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


def test_processing_task_cancel_before_multi_video_merge_skips_merge(tmp_path):
    videos = [str(tmp_path / "input1.mp4"), str(tmp_path / "input2.mp4")]
    progress_queue = Queue()
    result_queue = Queue()
    cancel_event = _CancelEvent()
    run_count = 0

    class ClipsPipeline:
        def __init__(self, config, progress_callback=None):
            self.results = {"frames": [], "events": [], "clips": []}
            self.stages = {name: type("Stage", (), {"status": StageStatus.PENDING})() for name in [
                "metadata",
                "frames",
                "detection",
                "clips",
                "join",
                "audio",
            ]}

        def run_until_clips_result(self, path):
            nonlocal run_count
            run_count += 1
            self.results["clips"] = [{"path": f"{path}.clip.mp4"}]
            if run_count == len(videos):
                cancel_event.set()
            return PipelineRunResult(
                success=True,
                mode="clips",
                video_path=path,
                clips=self.results["clips"],
            )

    merge = Mock(return_value={"final_video": str(tmp_path / "merged.mp4")})

    with patch("src.config.config_loader.get_config", return_value={}), \
         patch("src.pipeline.pipeline.Pipeline", ClipsPipeline), \
         patch("src.pipeline.multi_video.merge_clips_to_highlight", merge):
        _run_processing_task(videos, "battlefield6", progress_queue, result_queue, cancel_event)

    result = result_queue.get_nowait()

    assert result["success"] is False
    assert result["status"] == "cancelled"
    assert result["stage"] == "merge"
    merge.assert_not_called()


def test_processing_task_cancel_after_multi_video_merge_returns_cancelled(tmp_path):
    videos = [str(tmp_path / "input1.mp4"), str(tmp_path / "input2.mp4")]
    progress_queue = Queue()
    result_queue = Queue()
    cancel_event = _CancelEvent()

    class ClipsPipeline:
        def __init__(self, config, progress_callback=None):
            self.results = {"frames": [], "events": [], "clips": []}
            self.stages = {name: type("Stage", (), {"status": StageStatus.PENDING})() for name in [
                "metadata",
                "frames",
                "detection",
                "clips",
                "join",
                "audio",
            ]}

        def run_until_clips_result(self, path):
            self.results["clips"] = [{"path": f"{path}.clip.mp4"}]
            return PipelineRunResult(
                success=True,
                mode="clips",
                video_path=path,
                clips=self.results["clips"],
            )

    def merge_and_cancel(config, input_videos, clips, **kwargs):
        cancel_event.set()
        return {"final_video": str(tmp_path / "merged.mp4")}

    merge = Mock(side_effect=merge_and_cancel)

    with patch("src.config.config_loader.get_config", return_value={}), \
         patch("src.pipeline.pipeline.Pipeline", ClipsPipeline), \
         patch("src.pipeline.multi_video.merge_clips_to_highlight", merge):
        _run_processing_task(videos, "battlefield6", progress_queue, result_queue, cancel_event)

    result = result_queue.get_nowait()

    assert result["success"] is False
    assert result["status"] == "cancelled"
    assert result["stage"] == "merge"
    merge.assert_called_once()


def test_processing_task_merge_cancelled_result_returns_cancelled(tmp_path):
    videos = [str(tmp_path / "input1.mp4"), str(tmp_path / "input2.mp4")]
    progress_queue = Queue()
    result_queue = Queue()

    class ClipsPipeline:
        def __init__(self, config, progress_callback=None):
            self.results = {"frames": [], "events": [], "clips": []}
            self.stages = {name: type("Stage", (), {"status": StageStatus.PENDING})() for name in [
                "metadata",
                "frames",
                "detection",
                "clips",
                "join",
                "audio",
            ]}

        def run_until_clips_result(self, path):
            self.results["clips"] = [{"path": f"{path}.clip.mp4"}]
            return PipelineRunResult(
                success=True,
                mode="clips",
                video_path=path,
                clips=self.results["clips"],
            )

    merge = Mock(return_value={"success": False, "cancelled": True, "stage": "merge_audio"})

    with patch("src.config.config_loader.get_config", return_value={}), \
         patch("src.pipeline.pipeline.Pipeline", ClipsPipeline), \
         patch("src.pipeline.multi_video.merge_clips_to_highlight", merge):
        _run_processing_task(videos, "battlefield6", progress_queue, result_queue, _CancelEvent())

    result = result_queue.get_nowait()

    assert result["success"] is False
    assert result["status"] == "cancelled"
    assert result["stage"] == "merge"
    merge.assert_called_once()
    assert merge.call_args.kwargs["cancel_event"].is_set() is False
