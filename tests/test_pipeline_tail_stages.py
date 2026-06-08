import os
from unittest.mock import MagicMock

import pytest

from src.pipeline.context import PipelineContext
from src.pipeline.stages.audio_stage import run_audio_stage
from src.pipeline.stages.cleanup_stage import run_cleanup_stage
from src.pipeline.stages.join_stage import run_join_stage


def _context(tmp_path, config=None):
    return PipelineContext(
        config=config or {"global": {"output_dir": str(tmp_path / "output")}},
        video_path=str(tmp_path / "input.mp4"),
        base_name="input",
        temp_dir=str(tmp_path / "temp"),
        results={},
    )


def test_join_stage_skips_empty_clips(tmp_path):
    result = run_join_stage(_context(tmp_path), [])

    assert result.skipped is True
    assert result.values["joined_video"] is None


def test_join_stage_rejects_missing_path(tmp_path):
    with pytest.raises(RuntimeError, match="missing path field"):
        run_join_stage(_context(tmp_path), [{"id": "clip-1"}])


def test_join_stage_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_join_stage(_context(tmp_path), [{"path": str(tmp_path / "missing.mp4")}])


def test_join_stage_calls_joiner(tmp_path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"clip")
    joiner_cls = MagicMock()
    joiner_cls.return_value.join_clips.return_value = True

    result = run_join_stage(_context(tmp_path), [{"path": str(clip_path)}], video_joiner_cls=joiner_cls)

    assert result.skipped is False
    assert result.values["joined_video"] == os.path.join(str(temp_dir), "joined_no_audio.mp4")
    joiner_cls.return_value.join_clips.assert_called_once()


def test_audio_stage_skips_missing_joined_video(tmp_path):
    result = run_audio_stage(_context(tmp_path), str(tmp_path / "missing.mp4"))

    assert result.skipped is True
    assert result.values["final_video"] is None


def test_audio_stage_copies_joined_video_when_mixer_skips_music(tmp_path):
    joined = tmp_path / "joined.mp4"
    joined.write_bytes(b"joined")
    mixer_cls = MagicMock()
    mixer_cls.return_value.mix_audio.return_value = str(joined)

    result = run_audio_stage(_context(tmp_path), str(joined), audio_mixer_cls=mixer_cls)

    final_path = result.values["final_video"]
    assert os.path.exists(final_path)
    assert open(final_path, "rb").read() == b"joined"


def test_cleanup_stage_removes_only_context_temp_dir(tmp_path):
    temp_dir = tmp_path / "temp"
    other_dir = tmp_path / "other"
    temp_dir.mkdir()
    other_dir.mkdir()
    (temp_dir / "file.txt").write_text("delete", encoding="utf-8")
    (other_dir / "file.txt").write_text("keep", encoding="utf-8")

    context = _context(tmp_path, {"global": {"debug": False}})
    context.temp_dir = str(temp_dir)
    run_cleanup_stage(context)

    assert not temp_dir.exists()
    assert other_dir.exists()
