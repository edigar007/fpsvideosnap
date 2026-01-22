"""
Tests for config fingerprint generation.
Used to detect configuration changes for incremental rebuild.
"""
import pytest
from typing import Dict, Any


class TestConfigFingerprint:
    """Tests for config fingerprint generation."""

    @pytest.fixture
    def base_config(self) -> Dict[str, Any]:
        """A minimal config structure for testing."""
        return {
            "global": {
                "output_dir": "output",
                "temp_dir": "temp",
                "debug": False,
            },
            "video": {
                "ffmpeg_path": "ffmpeg",
                "hwaccel": "cuda",
                "frame_interval_ms": 1000,
                "frame_extraction_mode": "bulk",
            },
            "detection": {
                "confidence_threshold": 0.5,
                "killfeed_roi": [0.0, 0.0, 1.0, 1.0],
                "ocr": {"enabled": True, "keywords": ["击杀"]},
            },
            "ai": {
                "model_dir": "models",
                "batch_size": 16,
            },
            "highlights": {
                "pre_kill_time": 3.0,
                "post_kill_time": 1.0,
                "music_path": "assets/music.mp3",
                "transition_type": "fade",
            },
        }

    def test_same_config_produces_same_fingerprints(self, base_config):
        """Identical configs should produce identical fingerprints."""
        from src.config.fingerprint import compute_config_fingerprints
        
        fp1 = compute_config_fingerprints(base_config)
        fp2 = compute_config_fingerprints(base_config)
        
        assert fp1 == fp2
        assert "config_hash" in fp1
        assert "video_hash" in fp1
        assert "detection_hash" in fp1
        assert "highlights_hash" in fp1
        assert "global_hash" in fp1

    def test_video_change_affects_video_hash(self, base_config):
        """Changing video section should change video_hash but not others."""
        from src.config.fingerprint import compute_config_fingerprints
        
        fp1 = compute_config_fingerprints(base_config)
        
        # Modify video config
        modified = base_config.copy()
        modified["video"] = base_config["video"].copy()
        modified["video"]["frame_interval_ms"] = 500  # Changed!
        
        fp2 = compute_config_fingerprints(modified)
        
        assert fp1["video_hash"] != fp2["video_hash"], "video_hash should change"
        assert fp1["detection_hash"] == fp2["detection_hash"], "detection_hash should NOT change"
        assert fp1["highlights_hash"] == fp2["highlights_hash"], "highlights_hash should NOT change"
        assert fp1["config_hash"] != fp2["config_hash"], "overall config_hash should change"

    def test_detection_change_affects_detection_hash(self, base_config):
        """Changing detection section should change detection_hash."""
        from src.config.fingerprint import compute_config_fingerprints
        
        fp1 = compute_config_fingerprints(base_config)
        
        # Modify detection config
        modified = base_config.copy()
        modified["detection"] = base_config["detection"].copy()
        modified["detection"]["confidence_threshold"] = 0.7  # Changed!
        
        fp2 = compute_config_fingerprints(modified)
        
        assert fp1["detection_hash"] != fp2["detection_hash"], "detection_hash should change"
        assert fp1["video_hash"] == fp2["video_hash"], "video_hash should NOT change"
        assert fp1["highlights_hash"] == fp2["highlights_hash"], "highlights_hash should NOT change"

    def test_highlights_change_affects_highlights_hash(self, base_config):
        """Changing highlights section should change highlights_hash."""
        from src.config.fingerprint import compute_config_fingerprints
        
        fp1 = compute_config_fingerprints(base_config)
        
        # Modify highlights config
        modified = base_config.copy()
        modified["highlights"] = base_config["highlights"].copy()
        modified["highlights"]["pre_kill_time"] = 5.0  # Changed!
        
        fp2 = compute_config_fingerprints(modified)
        
        assert fp1["highlights_hash"] != fp2["highlights_hash"], "highlights_hash should change"
        assert fp1["video_hash"] == fp2["video_hash"], "video_hash should NOT change"
        assert fp1["detection_hash"] == fp2["detection_hash"], "detection_hash should NOT change"

    def test_ai_change_affects_ai_hash(self, base_config):
        """Changing ai section should change ai_hash."""
        from src.config.fingerprint import compute_config_fingerprints
        
        fp1 = compute_config_fingerprints(base_config)
        
        # Modify ai config
        modified = base_config.copy()
        modified["ai"] = base_config["ai"].copy()
        modified["ai"]["batch_size"] = 32  # Changed!
        
        fp2 = compute_config_fingerprints(modified)
        
        assert fp1.get("ai_hash") != fp2.get("ai_hash"), "ai_hash should change"

    def test_fingerprints_are_stable_across_key_order(self, base_config):
        """Fingerprints should be stable regardless of dict key ordering."""
        from src.config.fingerprint import compute_config_fingerprints
        
        # Create config with different key order
        reordered = {
            "highlights": base_config["highlights"],
            "video": base_config["video"],
            "global": base_config["global"],
            "detection": base_config["detection"],
            "ai": base_config["ai"],
        }
        
        fp1 = compute_config_fingerprints(base_config)
        fp2 = compute_config_fingerprints(reordered)
        
        assert fp1 == fp2, "Fingerprints should be stable across key ordering"

    def test_get_invalidation_stage_for_fingerprint_diff(self, base_config):
        """Test determining which stage to invalidate based on fingerprint diff."""
        from src.config.fingerprint import (
            compute_config_fingerprints,
            get_earliest_invalidation_stage,
        )
        
        fp_original = compute_config_fingerprints(base_config)
        
        # Case 1: video changed -> invalidate from frames
        modified = base_config.copy()
        modified["video"] = base_config["video"].copy()
        modified["video"]["hwaccel"] = "cpu"
        fp_video_changed = compute_config_fingerprints(modified)
        
        stage = get_earliest_invalidation_stage(fp_original, fp_video_changed)
        assert stage == "frames"
        
        # Case 2: detection changed -> invalidate from detection
        modified = base_config.copy()
        modified["detection"] = base_config["detection"].copy()
        modified["detection"]["confidence_threshold"] = 0.8
        fp_detection_changed = compute_config_fingerprints(modified)
        
        stage = get_earliest_invalidation_stage(fp_original, fp_detection_changed)
        assert stage == "detection"
        
        # Case 3: highlights changed -> invalidate from clips
        modified = base_config.copy()
        modified["highlights"] = base_config["highlights"].copy()
        modified["highlights"]["post_kill_time"] = 2.0
        fp_highlights_changed = compute_config_fingerprints(modified)
        
        stage = get_earliest_invalidation_stage(fp_original, fp_highlights_changed)
        assert stage == "clips"
        
        # Case 4: no change -> None
        stage = get_earliest_invalidation_stage(fp_original, fp_original)
        assert stage is None

    def test_missing_sections_handled_gracefully(self):
        """Config missing sections should still produce fingerprints."""
        from src.config.fingerprint import compute_config_fingerprints
        
        minimal_config = {"global": {"output_dir": "out"}}
        
        fp = compute_config_fingerprints(minimal_config)
        
        assert "config_hash" in fp
        assert "global_hash" in fp
        # Missing sections should have empty or default hashes
        assert "video_hash" in fp
        assert "detection_hash" in fp


class TestPathHash:
    """Tests for video path hashing (for checkpoint naming)."""

    def test_path_hash_is_stable(self):
        """Same path should produce same hash."""
        from src.config.fingerprint import compute_path_hash
        
        path = "D:\\videos\\gameplay.mp4"
        h1 = compute_path_hash(path)
        h2 = compute_path_hash(path)
        
        assert h1 == h2
        assert len(h1) == 8  # 8 character hex string

    def test_different_paths_produce_different_hashes(self):
        """Different paths should produce different hashes."""
        from src.config.fingerprint import compute_path_hash
        
        h1 = compute_path_hash("D:\\videos\\game1.mp4")
        h2 = compute_path_hash("D:\\videos\\game2.mp4")
        h3 = compute_path_hash("E:\\other\\game1.mp4")
        
        assert h1 != h2
        assert h1 != h3
        assert h2 != h3
