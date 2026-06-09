# FPS Video Snap

AI-assisted highlight generation for FPS gameplay videos.

FPS Video Snap is a local Windows tool that detects kill moments in gameplay footage, cuts highlight clips, and optionally joins them with transitions and background music. Detection is config-driven and combines fast color prefiltering, OpenCV template matching, optional PaddleOCR, and YOLO-backed inference.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![YOLOv8](https://img.shields.io/badge/AI-YOLOv8-green.svg)](https://github.com/ultralytics/ultralytics)
[![FFmpeg](https://img.shields.io/badge/Video-FFmpeg-orange.svg)](https://ffmpeg.org/)
[![CUDA Ready](https://img.shields.io/badge/GPU-CUDA-76b900.svg)](https://developer.nvidia.com/cuda-zone)

## Features

- Multi-signal kill detection: color prefiltering, template matching, OCR, and YOLO signal fusion.
- Game-specific YAML configs for ROIs, colors, templates, thresholds, and rules.
- Local web Config Assistant for tuning ROIs, templates, colors, OCR keywords, and OR-of-AND detection rules.
- Batch Dashboard for scanning video folders and running multiple videos with live progress.
- FFmpeg-based frame extraction, clip cutting, joining, transitions, and audio mixing.
- Checkpoint/resume support for long-running jobs.
- Windows/NVIDIA GPU path with CUDA, NVENC, and optional PaddleOCR isolation.

## Requirements

- Windows 10/11
- Python 3.10+
- FFmpeg and FFprobe available on `PATH`
- NVIDIA GPU with CUDA support recommended
- Local model files under `models/`

The project is designed to run offline. Network access is not required during normal processing. Model download is only expected during initial setup when explicitly enabled.

## Quick Start

Create or use the project virtual environment, then install dependencies:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Check CUDA availability:

```powershell
.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

Process one video:

```powershell
.venv\Scripts\python.exe main.py --video input.mp4 --game battlefield6
```

Run with debug output and visual overlays:

```powershell
.venv\Scripts\python.exe main.py --video sample.mp4 --game battlefield6 --debug --debug-visual
```

Process multiple videos as one highlight set:

```powershell
.venv\Scripts\python.exe main.py --video video1.mp4 video2.mp4 --game battlefield_1
```

## Web Tools

Start the Config Assistant:

```powershell
.venv\Scripts\python.exe main.py config-assistant --port 8080
```

Start the batch Dashboard:

```powershell
.venv\Scripts\python.exe main.py dashboard --port 8081
```

Both web tools are intended for trusted local use and should stay bound to `127.0.0.1`.

## Game Configuration

Game configs live in `config/games/*.yaml`. Detection settings should stay config-driven: ROIs, color thresholds, template paths, OCR keywords, confidence thresholds, and detection rules belong in YAML rather than hardcoded Python.

Example game configs:

- `config/games/battlefield6.yaml`
- `config/games/battlefield4.yaml`
- `config/games/battlefield_1.yaml`

Validate a config:

```powershell
.venv\Scripts\python.exe main.py validate-config --game battlefield_1
```

## Project Layout

```text
config/      Global and game-specific YAML configs
docs/        User, troubleshooting, review, and engineering notes
models/      YOLO models and template images
src/ai/      Detection, signal extraction, fusion, OCR, and rules
src/audio/   Audio processing and mixing
src/clip/    Highlight clip extraction and metadata
src/pipeline/Processing stages, checkpoints, and orchestration
src/tools/   Config Assistant and Dashboard web tools
src/video/   FFmpeg frame extraction, cutting, joining, and transitions
tests/       Pytest unit and integration tests
```

## Tests

Run the full suite:

```powershell
.venv\Scripts\python.exe -m pytest tests/
```

Run focused web-tool tests:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py tests/test_dashboard_api.py -q
```

## Documentation

- Chinese README: [README.zh-CN.md](README.zh-CN.md)
- Installation: [docs/INSTALL.md](docs/INSTALL.md)
- Configuration: [docs/CONFIG.md](docs/CONFIG.md)
- Config Assistant guide: [docs/config-assistant-guide.md](docs/config-assistant-guide.md)
- Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Known limitations: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)

## License

This project is for learning and research use.
