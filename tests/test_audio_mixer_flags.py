from unittest.mock import MagicMock, patch

from src.audio.audio_mixer import AudioMixer


def test_audio_mixer_uses_safe_remux_flags():
    config = {
        "highlights": {
            "music_enabled": True,
            "music_path": "music.mp3",
            "game_volume": 0.5,
            "music_volume": 0.5,
        }
    }
    mixer = AudioMixer(config)

    with patch('src.audio.audio_mixer.VideoInfo') as mock_info, \
         patch.object(mixer.music_processor, 'process_music', return_value='processed.wav') as mock_process, \
         patch('os.path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_info.return_value.duration = 5.0
        mock_run.return_value = MagicMock(returncode=0)

        result = mixer.mix_audio('joined.mp4', 'final.mp4')

    assert result == 'final.mp4'
    cmd = mock_run.call_args[0][0]
    assert '-fflags' in cmd
    assert '+genpts' in cmd
    assert '-movflags' in cmd
    assert '+faststart' in cmd
    assert '-avoid_negative_ts' in cmd
    assert 'make_zero' in cmd
    assert '-max_interleave_delta' in cmd
    assert '0' in cmd
    mock_process.assert_called_once_with('music.mp3', 5.0)
