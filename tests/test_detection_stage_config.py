from pathlib import Path

from src.pipeline.context import PipelineContext
from src.pipeline.stages.detection_stage import run_detection_stage


class FakeModelManager:
    def __init__(self):
        self.model_path = ""

    def load_model(self):
        return object()


class FakeYoloDetector:
    def __init__(self, model, batch_size=16):
        self.model = model
        self.batch_size = batch_size


class FakeOpenCVMatcher:
    def __init__(self, config):
        self.config = config
        self.templates = {}


class FakeKillDetector:
    def __init__(self, yolo_detector, opencv_matcher, config):
        self.yolo = yolo_detector
        self.cv = opencv_matcher
        self.config = config
        self.ocr = None

    def process_video_batch(self, frames, timestamps_ms):
        return []


class FakeProgress:
    def __init__(self, total, desc):
        self.total = total
        self.desc = desc

    def update(self, count):
        pass

    def close(self):
        pass


def test_detection_stage_uses_detection_model_path(tmp_path):
    model_manager = FakeModelManager()
    model_path = str(tmp_path / "custom-model.pt")
    context = PipelineContext(
        config={
            "global": {"history_dir": str(tmp_path / "history")},
            "ai": {"model_dir": str(tmp_path / "unused"), "batch_size": 4},
            "detection": {"model_path": model_path},
        },
        video_path=str(tmp_path / "input.mp4"),
        base_name="input",
        temp_dir=str(tmp_path / "temp"),
    )

    result = run_detection_stage(
        context,
        frames=[],
        model_manager=model_manager,
        load_templates=lambda matcher: 0,
        progress_desc="Detecting",
        yolo_detector_cls=FakeYoloDetector,
        opencv_matcher_cls=FakeOpenCVMatcher,
        kill_detector_cls=FakeKillDetector,
        progress_factory=FakeProgress,
    )

    assert model_manager.model_path == model_path
    assert result.events == []
    assert Path(result.detection_json_path).is_file()

