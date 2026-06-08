import pytest

from src.pipeline.results import (
    ALL_RESULT_KEYS,
    CLIPS,
    DEBUG_VIDEO,
    DETECTION_JSON,
    EVENTS,
    FINAL_VIDEO,
    FRAMES,
    JOINED_VIDEO,
    PipelineResult,
    PipelineRunResult,
    REPORT_PATH,
    StageResult,
    VIDEO_INFO,
    validate_result_keys,
)
from src.pipeline.stages.base import StageResult as StageResultFromStageBase


def test_pipeline_result_keys_are_stable_contract():
    assert ALL_RESULT_KEYS == frozenset(
        {
            "video_info",
            "frames",
            "events",
            "detection_json",
            "debug_video",
            "clips",
            "joined_video",
            "final_video",
            "report_path",
        }
    )
    assert VIDEO_INFO == "video_info"
    assert FRAMES == "frames"
    assert EVENTS == "events"
    assert DETECTION_JSON == "detection_json"
    assert DEBUG_VIDEO == "debug_video"
    assert CLIPS == "clips"
    assert JOINED_VIDEO == "joined_video"
    assert FINAL_VIDEO == "final_video"
    assert REPORT_PATH == "report_path"


def test_stage_result_rejects_unknown_result_key():
    with pytest.raises(KeyError, match="unknown"):
        StageResult({"unknown": "value"})


def test_pipeline_result_validates_updates():
    result = PipelineResult()

    result.set(FRAMES, ["frame_1000.jpg"])
    result.update({CLIPS: [{"path": "clip.mp4"}]})

    assert result.as_dict() == {
        FRAMES: ["frame_1000.jpg"],
        CLIPS: [{"path": "clip.mp4"}],
    }

    with pytest.raises(KeyError, match="bad_key"):
        result.update({"bad_key": "value"})


def test_pipeline_run_result_serializes_contract():
    result = PipelineRunResult(
        success=False,
        mode="clips",
        video_path="video.mp4",
        clips=[{"path": "clip.mp4"}],
        final_video=None,
        report_path="report.md",
        failed_stage="detection",
        error="boom",
    )

    assert result.as_dict() == {
        "success": False,
        "mode": "clips",
        "video_path": "video.mp4",
        "clips": [{"path": "clip.mp4"}],
        "final_video": None,
        "report_path": "report.md",
        "failed_stage": "detection",
        "error": "boom",
    }


def test_validate_result_keys_accepts_empty_and_known_keys():
    validate_result_keys({})
    validate_result_keys({VIDEO_INFO: {"duration": 10}, FINAL_VIDEO: "out.mp4"})


def test_stage_base_reexports_stage_result_for_existing_imports():
    assert StageResultFromStageBase is StageResult
