from unittest.mock import MagicMock, patch

from src.pipeline.batch_processor import BatchProcessor
from src.pipeline.results import PipelineRunResult


def _base_config(debug=False, keep_intermediates=False):
    return {
        "global": {
            "output_dir": "output",
            "debug": debug,
        },
        "video": {
            "join_fix": {
                "keep_intermediates": keep_intermediates,
            }
        },
        "highlights": {
            "music_enabled": False,
        },
    }


@patch("src.pipeline.batch_processor.ReportGenerator")
@patch("src.pipeline.batch_processor.AudioMixer")
@patch("src.pipeline.batch_processor.VideoJoiner")
@patch("src.pipeline.batch_processor.Pipeline")
def test_batch_processor_keeps_merged_file_when_config_requests_it(
    mock_pipeline_cls,
    mock_joiner_cls,
    mock_mixer_cls,
    mock_report_cls,
):
    config = _base_config(debug=False, keep_intermediates=True)
    processor = BatchProcessor(config)

    mock_pipeline = MagicMock()
    mock_pipeline.run_until_clips_result.return_value = PipelineRunResult(
        success=True,
        mode="clips",
        video_path="video.mp4",
        clips=[{"path": "clip1.mp4"}],
    )
    mock_pipeline.stages = {"clips": MagicMock(status=MagicMock(value="SUCCESS"))}
    mock_pipeline_cls.return_value = mock_pipeline

    mock_joiner_cls.return_value.join_clips.return_value = True
    mock_mixer_cls.return_value.mix_audio.return_value = "output/combined_highlights_20260101_010101.mp4"
    mock_report_cls.return_value.generate.return_value = "output/report.md"

    with patch("os.path.exists") as mock_exists, \
         patch("os.makedirs"), \
         patch("os.remove") as mock_remove:
        def exists_side_effect(path):
            if path == "clip1.mp4":
                return True
            if path.startswith("output"):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        processor._process_multi_video(["video1.mp4", "video2.mp4"])

    mock_remove.assert_not_called()


@patch("src.pipeline.batch_processor.ReportGenerator")
@patch("src.pipeline.batch_processor.AudioMixer")
@patch("src.pipeline.batch_processor.VideoJoiner")
@patch("src.pipeline.batch_processor.Pipeline")
def test_batch_processor_removes_merged_file_by_default(
    mock_pipeline_cls,
    mock_joiner_cls,
    mock_mixer_cls,
    mock_report_cls,
):
    config = _base_config(debug=False, keep_intermediates=False)
    processor = BatchProcessor(config)

    mock_pipeline = MagicMock()
    mock_pipeline.run_until_clips_result.return_value = PipelineRunResult(
        success=True,
        mode="clips",
        video_path="video.mp4",
        clips=[{"path": "clip1.mp4"}],
    )
    mock_pipeline.stages = {"clips": MagicMock(status=MagicMock(value="SUCCESS"))}
    mock_pipeline_cls.return_value = mock_pipeline

    mock_joiner_cls.return_value.join_clips.return_value = True
    mock_mixer_cls.return_value.mix_audio.return_value = "output/combined_highlights_20260101_010101.mp4"
    mock_report_cls.return_value.generate.return_value = "output/report.md"

    with patch("os.path.exists") as mock_exists, \
         patch("os.makedirs"), \
         patch("os.remove") as mock_remove:
        def exists_side_effect(path):
            if path == "clip1.mp4":
                return True
            if path.startswith("output"):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        processor._process_multi_video(["video1.mp4", "video2.mp4"])

    mock_remove.assert_called_once()


@patch("src.pipeline.batch_processor.merge_clips_to_highlight")
@patch("src.pipeline.batch_processor.Pipeline")
def test_batch_processor_marks_failed_video_without_merging(mock_pipeline_cls, mock_merge):
    processor = BatchProcessor(_base_config())
    mock_pipeline = MagicMock()
    mock_pipeline.run_until_clips_result.return_value = PipelineRunResult(
        success=False,
        mode="clips",
        video_path="video1.mp4",
        failed_stage="detection",
        error="detection failed",
    )
    mock_pipeline_cls.return_value = mock_pipeline

    results = processor._process_multi_video(["video1.mp4", "video2.mp4"])

    assert results[0]["success"] is False
    assert results[0]["failed_stage"] == "detection"
    assert results[0]["error"] == "detection failed"
    mock_merge.assert_not_called()
