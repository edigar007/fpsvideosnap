from src.tools.dashboard.task_manager import _make_output_file


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
