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


def test_audio_mixer_uses_silent_audio_when_video_has_no_audio():
    config = {
        "video": {
            "join_fix": {
                "safe_audio_rate": 48000,
                "safe_channel_layout": "stereo",
            }
        },
        "highlights": {
            "music_enabled": True,
            "music_path": "music.mp3",
            "game_volume": 0.5,
            "music_volume": 0.5,
        },
    }
    mixer = AudioMixer(config)

    with patch('src.audio.audio_mixer.VideoInfo') as mock_info, \
         patch.object(mixer, '_has_audio_stream', return_value=False), \
         patch.object(mixer.music_processor, 'process_music', return_value='processed.wav'), \
         patch('os.path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_info.return_value.duration = 5.0
        mock_run.return_value = MagicMock(returncode=0)

        result = mixer.mix_audio('joined.mp4', 'final.mp4')

    assert result == 'final.mp4'
    cmd = mock_run.call_args[0][0]
    cmd_str = ' '.join(cmd)
    assert '-f lavfi' in cmd_str
    assert 'anullsrc=channel_layout=stereo:sample_rate=48000' in cmd_str
    assert '[1:a]volume=0.5[a1]' in cmd_str
    assert '[2:a]volume=0.5[a2]' in cmd_str
