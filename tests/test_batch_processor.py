from unittest.mock import MagicMock, patch

from src.pipeline.batch_processor import BatchProcessor


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
    mock_pipeline.run_until_clips.return_value = [{"path": "clip1.mp4"}]
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
    mock_pipeline.run_until_clips.return_value = [{"path": "clip1.mp4"}]
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
