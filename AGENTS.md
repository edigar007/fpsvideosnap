# AGENTS.md - AI Agent Guidelines for FPS Video Snap

## Project Overview

**FPS Video Snap** is an AI-powered automatic highlight generator for FPS gameplay videos. It uses multi-signal fusion detection (YOLOv8-nano, PaddleOCR, OpenCV template matching) to identify kill moments and automatically generates highlight clips with transitions and background music.

**Platform**: Windows 10/11 with NVIDIA GPU (CUDA)

---

## Build, Lint, and Test Commands

### Virtual Environment
```bash
# Project uses .venv in root directory
.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

### Install Dependencies
```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Run Application
```bash
# Standard run
.venv\Scripts\python.exe main.py --video input.mp4 --game battlefield6

# With debug mode
.venv\Scripts\python.exe main.py --video sample.mp4 --game battlefield6 --debug --debug-visual

# Config assistant (web UI)
.venv\Scripts\python.exe main.py config-assistant --port 8080
```

### Run Tests
```bash
# Run all tests
.venv\Scripts\python.exe -m pytest tests/

# Run a single test file
.venv\Scripts\python.exe -m pytest tests/test_config.py

# Run a specific test function
.venv\Scripts\python.exe -m pytest tests/test_config.py::TestConfigLoader::test_load_default_config

# Run with verbose output
.venv\Scripts\python.exe -m pytest tests/ -v

# Run tests matching a pattern
.venv\Scripts\python.exe -m pytest tests/ -k "pipeline"

# Run integration tests
.venv\Scripts\python.exe -m pytest tests/integration/
```

---

## Project Architecture (Pipeline Pattern)

```
src/
  ai/           # Detection modules (YoloDetector, OCRDetector, OpenCVMatcher, KillDetector)
  audio/        # Audio mixing
  clip/         # Clip extraction
  config/       # Configuration loading
  debug/        # Detection debugging tools
  pipeline/     # Main processing pipeline
  report/       # Report generation
  tools/        # Config assistant web UI
  utils/        # Logger, progress bars, temp file management
  video/        # FFmpeg integration (frame extraction, clip cutting, video joining)

config/
  default_config.yaml      # Global defaults
  games/                   # Game-specific configs (battlefield6.yaml, etc.)

tests/
  integration/             # Integration tests
  test_*.py               # Unit tests (pytest-style)
```

---

## Code Style Guidelines

### Imports
```python
# Standard library first
import os
import sys
import subprocess
from typing import List, Dict, Optional

# Third-party libraries
import numpy as np
import cv2
import yaml

# Local imports (use explicit src. prefix)
from src.utils.logger import get_logger
from src.ai.yolo_detector import YoloDetector
```

### Naming Conventions
- **Classes**: PascalCase (`KillDetector`, `FrameExtractor`)
- **Functions/Methods**: snake_case (`process_frame`, `_prefilter`)
- **Private methods**: Single underscore prefix (`_calculate_confidence`)
- **Constants**: UPPER_SNAKE_CASE
- **Variables**: snake_case

### Type Hints (Required)
```python
def process_frame(self, frame: np.ndarray) -> Dict:
    ...

def extract_frames(
    self,
    video_path: str,
    output_dir: str,
    interval_ms: int = 100,
    start_ms: Optional[int] = None,
) -> List[str]:
```

### Docstrings
```python
def _prefilter(self, frame: np.ndarray) -> bool:
    """
    Fast color detection to decide if we should run heavy AI models.
    Returns True if the frame passes pre-filter (potential kill frame).
    """
```

### Error Handling
- Use specific exception types, not bare `except:`
- Log errors with context before raising
- Provide clear error messages indicating: config error, model error, or FFmpeg dependency

```python
try:
    subprocess.run(cmd, check=True, capture_output=True)
except subprocess.CalledProcessError as e:
    logger.error(f"FFmpeg extraction failed at {timestamp_ms}ms: {e.stderr}")
    raise
```

### Logging
```python
from src.utils.logger import get_logger
logger = get_logger(__name__)

logger.info(f"Loaded config for game: {args.game}")
logger.debug(f"Final Configuration: {config}")
logger.warning(f"Fallback to precise mode: {e}")
logger.error(f"Failed to load configuration: {e}")
```

---

## Critical Development Rules

### 1. Config-Driven Design (MANDATORY)
- Detection parameters (ROI, color thresholds, confidence) MUST be in `config/games/*.yaml`
- Code defines abstract interfaces; config provides game-specific values
- Never hardcode detection thresholds

### 2. FFmpeg Usage
- Always support hardware acceleration: `-hwaccel cuda`, `-c:v h264_nvenc`
- Frame timestamps: `frame_{timestamp_ms}.jpg` format
- Prefer stream copy (`-c copy`) unless re-encoding is needed

### 3. GPU Optimization
- Implement batch inference in AI detectors
- Clean up temp files via `src/utils/temp_manager.py`
- Target optimization for NVIDIA 4070 Ti Super

### 4. Offline-Only (NO CLOUD APIs)
- This is a local tool - NO cloud API calls or network requests
- Exception: Model download during initial setup

### 5. Testing
- Use pytest for new tests
- Mock external dependencies (FFmpeg, GPU models)
- Test files in `tests/` directory
- Fixtures for common config patterns

---

## Test Patterns

### Pytest Fixtures
```python
@pytest.fixture
def mock_config():
    return {
        "global": {"output_dir": "test_output", "debug": True},
        "video": {"ffmpeg_path": "ffmpeg", "hwaccel": None},
        "detection": {"killfeed_roi": [0, 0, 1, 1], "colors": {}}
    }
```

### Mocking External Dependencies
```python
@patch("src.pipeline.pipeline.VideoInfo")
@patch("src.pipeline.pipeline.FrameExtractor")
@patch("cv2.imread")
def test_pipeline_full_flow(mock_imread, mock_frame_ext, mock_video_info, mock_config):
    mock_video_info.return_value.duration = 10
    mock_frame_ext.return_value.extract_frames.return_value = ["frame_1000.jpg"]
    ...
```

---

## Configuration Reference

### Game Config Structure (YAML)
```yaml
game_name: battlefield6
detection:
  ocr:
    enabled: true
    keywords: ["击杀", "爆头"]
    similarity_threshold: 0.9
  killfeed_roi: [0.27, 0.54, 0.20, 0.22]  # [x, y, width, height] as ratios
  colors:
    kill_red:
      hsv_lower: [147, 25, 43]
      hsv_upper: [180, 105, 123]
      tolerance: 20
  prefilter:
    enabled: true
    color_threshold: 0.01
  confidence_threshold: 0.5
  weights:
    ocr: 0.4
    template: 0.3
    color: 0.2
    yolo: 0.1
highlights:
  pre_kill_time: 5.0
  post_kill_time: 1.5
  transition_type: random
```

---

## Common Pitfalls

1. **CUDA DLL Loading**: On Windows, CUDA DLLs must be loaded BEFORE importing torch. See `main.py` for the pattern.

2. **PaddleOCR GPU Conflicts**: PaddleOCR and PyTorch can conflict. The project uses subprocess isolation for OCR.

3. **Timestamp Precision**: Use millisecond timestamps throughout. Frame filenames use `frame_{ms}.jpg` format.

4. **ROI Coordinates**: All ROIs are normalized (0.0-1.0), converted to pixels when needed.

5. **GIL Limitations**: Multi-threading gains are limited by Python GIL and GPU inference. Batch processing is preferred.

---

## Existing Agent Instructions

Additional agent instructions are available in:
- `.github/copilot-instructions.md` - Copilot/AI coding guidelines (Chinese)
- `.github/agents/` - GitHub Copilot agent configurations
