# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Windows setup (recommended)
scripts\setup.bat

# Manual environment setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Verify CUDA is visible to PyTorch
.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"

# Run the main pipeline (the CLI auto-inserts `run` if omitted)
.venv\Scripts\python.exe main.py --video path/to/gameplay.mp4 --game battlefield6

# Run with debug logging + visual debug output
.venv\Scripts\python.exe main.py --video sample.mp4 --game battlefield6 --debug --debug-visual

# Launch the configuration assistant web UI
.venv\Scripts\python.exe main.py config-assistant --port 8080

# Launch the batch-processing dashboard web UI
.venv\Scripts\python.exe main.py dashboard --port 8081

# Run all tests
.venv\Scripts\python.exe -m pytest tests/

# Run one test file
.venv\Scripts\python.exe -m pytest tests/test_config.py

# Run one test function
.venv\Scripts\python.exe -m pytest tests/test_config.py::TestConfigLoader::test_load_default_config

# Run a filtered subset
.venv\Scripts\python.exe -m pytest tests/ -k "pipeline"
```

There is no dedicated lint/build target checked into the repo; `pytest` is the main validation path documented in-repo.

If you are working on Config Assistant OCR preview issues on Windows, the optional standalone PaddleOCR environment is:

```bash
uv venv --python 3.12.11 .venv_paddle
uv pip install --python .venv_paddle -r requirements-win-paddleocr-gpu-standalone.txt
```

## Big picture

FPS Video Snap is a Windows-first, local/offline FPS highlight generator. The core flow is:

1. load layered YAML config
2. extract frames with FFmpeg
3. detect kill moments with multi-signal fusion
4. cut highlight clips
5. join clips and mix audio
6. write report/history artifacts

The project is intentionally config-driven: game-specific detection behavior should live in `config/games/*.yaml`, not in hardcoded thresholds.

## Entry points

- `main.py` is the true process entry point. It sets up Windows CUDA/Paddle DLL search paths **before** importing the rest of the app, then dispatches to the CLI, Config Assistant, or Dashboard.
- `src/cli.py` defines three subcommands: `run`, `config-assistant`, and `dashboard`. For backward compatibility, `python main.py --video ...` is rewritten to `python main.py run --video ...`.

If you touch startup/import order, preserve the early Windows DLL setup pattern from `main.py`.

## Pipeline architecture

- `src/pipeline/batch_processor.py` handles input expansion and mode selection.
  - Single video: run the full pipeline and emit one result.
  - Multiple videos / directories / glob patterns: run each video only through clip extraction, then merge all clips into one combined highlight.
- `src/pipeline/pipeline.py` is the stage orchestrator. Its stages are:
  - `metadata`
  - `frames`
  - `detection`
  - `clips`
  - `join`
  - `audio`
  - `report`
  - `history`
  - `cleanup`
- The pipeline supports checkpoint/resume. Checkpoints live under the configured temp directory and are invalidated selectively using config fingerprints from `src/config/fingerprint.py`.
  - `video.*` changes invalidate frame extraction onward.
  - `detection.*` / `ai.*` changes invalidate detection onward.
  - `highlights.*` changes invalidate clip generation onward.
  - `global.*` changes invalidate audio onward.

Important working directories:

- `output/` — final highlights and reports
- `temp/` — checkpoints, extracted frames, temporary clips/uploads
- `history/` — per-run detection/history artifacts

## Detection stack

`src/ai/kill_detector.py` is the core detection brain.

- Stage 1: fast color prefilter across all frames.
- Stage 2: precise detection on candidate frames using OCR, template matching, and YOLO.
- YOLO is batched for candidate frames; OCR/template checks are then applied per candidate.

Detection has two modes:

- **Rules mode**: if `detection.rules` is non-empty, detection uses OR-of-AND logic. Any enabled rule can match; each rule requires all listed signals.
- **Legacy mode**: if `detection.rules` is empty, detection falls back to weighted confidence scoring.

Per-rule `detection_overrides` are important in this repo: a rule can override ROI, OCR settings, templates, colors, and prefilter settings without changing the global detection block.

## Configuration model

Configuration is merged in this order:

1. `config/default_config.yaml`
2. `config/games/{game}.yaml`
3. CLI `--config` override YAML

Keep these repo-specific semantics in mind:

- ROIs are normalized `[x, y, w, h]` ratios, not pixel coordinates.
- Template assets usually live under `models/templates/<game>/`.
- `config/default_game_template.yaml` is the scaffold used when the Config Assistant creates a new game config.
- `docs/CONFIG.md` is the best reference for YAML semantics, especially `detection.rules` and per-rule overrides.

## Web tools

### Config Assistant

The Config Assistant is a Flask app under `src/tools/config_assistant/`.

- `server.py` creates the app, cleans temporary uploads, pre-warms OCR in a background thread, and opens a browser on an available localhost port.
- `api.py` exposes endpoints for image upload, ROI editing, OCR settings, templates, colors, game creation, and rules CRUD.
- `config_manager.py` reads/writes the actual YAML files in `config/games/` and creates template directories under `models/templates/<game>/`.

Important repo behavior: saving a per-rule override through the Config Assistant can auto-create the missing rule in YAML if it does not exist yet.

OCR preview is optional. `ocr_service.py` lazy-loads OCR and uses subprocess isolation on Windows to avoid DLL conflicts. If PaddleOCR/CUDA is unavailable, the assistant should still work for non-OCR features.

### Dashboard

The Dashboard is a separate Flask app under `src/tools/dashboard/`.

- `api.py` lists games, scans directories for video files, starts/cancels jobs, and returns progress/error state.
- `task_manager.py` runs processing in a separate process and streams progress back to the web UI.

When changing the dashboard, remember it is not just a static wrapper around CLI calls: it has its own process isolation and progress model.

## Testing notes

- Most automated tests are under `tests/`; `tests/integration/` contains higher-level cases and `tests/manual/` contains ad-hoc/manual scripts.
- `tests/conftest.py` mocks heavy ML dependencies (`torch`, `ultralytics`, `paddle`, `paddleocr`) so most pytest runs do **not** require a GPU-capable environment.
- There are focused tests around rules/per-rule overrides and Config Assistant behavior; check those first when changing detection rules or YAML-writing APIs.

## Repo-specific constraints

- This is a local tool. Avoid introducing cloud/network dependencies except model download/setup behavior already documented.
- Prefer preserving FFmpeg hardware acceleration settings (`video.hwaccel: cuda`, `video.encoder: h264_nvenc`) unless you are deliberately fixing compatibility issues.
- For Windows/PaddleOCR environment problems, `docs/TROUBLESHOOTING.md` is the authoritative reference.
