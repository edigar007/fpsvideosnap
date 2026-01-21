"""
Config fingerprint generation for incremental rebuild.

This module provides functions to compute stable fingerprints (hashes) of configuration
sections, enabling detection of configuration changes between pipeline runs.

Fingerprint mapping (config section -> affected stage):
- video.* -> frames
- detection.* or ai.* -> detection
- highlights.* -> clips
- global.* -> audio (output paths, etc.)
"""
import hashlib
import json
import os
from typing import Dict, Any, Optional


# Stage order for invalidation logic
STAGE_ORDER = ["metadata", "frames", "detection", "clips", "join", "audio", "report", "history", "cleanup"]

# Mapping from fingerprint key to the stage that should be invalidated when it changes
FINGERPRINT_TO_STAGE = {
    "video_hash": "frames",
    "ai_hash": "detection",
    "detection_hash": "detection",
    "highlights_hash": "clips",
    "global_hash": "audio",
}


def _stable_hash(data: Any) -> str:
    """
    Compute a stable hash of any JSON-serializable data.
    
    Uses sorted keys and deterministic JSON serialization for stability
    across Python runs and dict key ordering.
    """
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()[:16]


def compute_config_fingerprints(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Compute fingerprints for each config section and the overall config.
    
    Args:
        config: The full merged configuration dict (after YAML merge + CLI overrides)
        
    Returns:
        Dict containing:
        - config_hash: Hash of entire config
        - video_hash: Hash of video section
        - detection_hash: Hash of detection section
        - ai_hash: Hash of ai section
        - highlights_hash: Hash of highlights section
        - global_hash: Hash of global section
    """
    fingerprints = {}
    
    # Per-section hashes
    for section in ["video", "detection", "ai", "highlights", "global"]:
        section_data = config.get(section, {})
        fingerprints[f"{section}_hash"] = _stable_hash(section_data)
    
    # Overall config hash (for quick comparison)
    fingerprints["config_hash"] = _stable_hash(config)
    
    return fingerprints


def get_earliest_invalidation_stage(
    old_fingerprints: Dict[str, str],
    new_fingerprints: Dict[str, str],
) -> Optional[str]:
    """
    Determine the earliest stage that needs to be invalidated based on fingerprint diff.
    
    Args:
        old_fingerprints: Fingerprints from the checkpoint
        new_fingerprints: Fingerprints computed from current config
        
    Returns:
        The name of the earliest stage that needs re-execution, or None if no change.
    """
    # Quick check: if overall hash matches, nothing changed
    if old_fingerprints.get("config_hash") == new_fingerprints.get("config_hash"):
        return None
    
    # Find the earliest stage affected by any changed fingerprint
    earliest_stage = None
    earliest_index = len(STAGE_ORDER)  # Start beyond the list
    
    for fp_key, stage in FINGERPRINT_TO_STAGE.items():
        old_val = old_fingerprints.get(fp_key)
        new_val = new_fingerprints.get(fp_key)
        
        if old_val != new_val:
            stage_index = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else len(STAGE_ORDER)
            if stage_index < earliest_index:
                earliest_index = stage_index
                earliest_stage = stage
    
    return earliest_stage


def compute_path_hash(path: str, length: int = 8) -> str:
    """
    Compute a short hash of a file path for checkpoint naming.
    
    This ensures different videos with the same filename but different directories
    have different checkpoint files.
    
    Args:
        path: The absolute path to the video file
        length: The length of the returned hash (default 8 characters)
        
    Returns:
        An 8-character hex string hash of the path
    """
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:length]


def get_stages_to_invalidate(from_stage: str) -> list:
    """
    Get all stages that should be invalidated starting from a given stage.
    
    Args:
        from_stage: The stage to start invalidation from
        
    Returns:
        List of stage names to invalidate (from_stage and all subsequent stages)
    """
    if from_stage not in STAGE_ORDER:
        return []
    
    start_index = STAGE_ORDER.index(from_stage)
    return STAGE_ORDER[start_index:]


def get_unique_output_path(base_path: str) -> str:
    """
    Find a unique output path by appending _1, _2, _3... suffix if base_path exists.
    
    This is used for final output video naming to avoid overwriting existing files
    when re-running the pipeline with config changes.
    
    Args:
        base_path: The desired output path (e.g., "output/video_highlights.mp4")
        
    Returns:
        A unique path that doesn't exist yet. Returns base_path if it doesn't exist,
        otherwise returns base_path with _N suffix before extension.
        
    Examples:
        - "output/video_highlights.mp4" -> "output/video_highlights.mp4" (if doesn't exist)
        - "output/video_highlights.mp4" -> "output/video_highlights_1.mp4" (if base exists)
        - "output/video_highlights.mp4" -> "output/video_highlights_2.mp4" (if _1 also exists)
    """
    if not os.path.exists(base_path):
        return base_path
    
    # Split into directory, stem, and extension
    directory = os.path.dirname(base_path)
    filename = os.path.basename(base_path)
    
    # Handle files with extensions
    if "." in filename:
        # Find the last dot to split stem and extension
        stem, ext = os.path.splitext(filename)
    else:
        stem = filename
        ext = ""
    
    # Find a unique suffix
    counter = 1
    while True:
        new_filename = f"{stem}_{counter}{ext}"
        new_path = os.path.join(directory, new_filename) if directory else new_filename
        if not os.path.exists(new_path):
            return new_path
        counter += 1
        # Safety limit to prevent infinite loop
        if counter > 9999:
            raise RuntimeError(f"Could not find unique output path after 9999 attempts: {base_path}")
