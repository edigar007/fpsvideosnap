---
goal: Stabilize FPS Video Snap pipeline by fixing clip metadata, timestamp persistence, and joining reliability
version: 1.0
date_created: 2026-01-12
last_updated: 2026-01-12
owner: GitHub Copilot (for user ediga)
status: 'Planned'
tags: ['feature', 'bugfix', 'pipeline', 'ai', 'video']
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan delivers a deterministic fix set for FPS Video Snap to unblock the highlight pipeline: propagate clip metadata to downstream stages, persist detection timestamps, and harden FFmpeg joining/reporting so the end-to-end run completes without manual intervention.

## 1. Requirements & Constraints

- **REQ-001**: Maintain compatibility with existing CLI (`main.py`, `src/cli.py`) and config schema (`config/default_config.yaml`).
- **REQ-002**: Preserve current GPU acceleration options (CUDA/NVENC) while adding Stream Copy fallback.
- **REQ-003**: Detection timestamps must be persisted to JSON for every run (per `src/ai/timestamp_recorder.py`).
- **SEC-001**: Do not introduce external services or network calls; all processing remains local.
- **PER-001**: Fixes must not regress current test-suite execution time beyond 10%.
- **CON-001**: Only Python stdlib + declared dependencies may be used.
- **GUD-001**: Follow config-driven behavior; no hard-coded paths outside config files.
- **PAT-001**: Keep pipeline staged execution model in `src/pipeline/pipeline.py`.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Normalize clip metadata so downstream join/report stages receive deterministic paths and timing info.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Update `src/clip/clip_extractor.py` to write `path`, `start_ms`, `end_ms`, and canonical filenames for every clip; ensure metadata JSON mirrors the same structure. | ✅ | 2026-01-12 |
| TASK-002 | Modify `src/pipeline/pipeline.py` join stage to read `clip['path']` (falling back to `output_path` if needed) and validate file existence before invoking `VideoJoiner`. | ✅ | 2026-01-12 |
| TASK-003 | Extend `tests/test_pipeline.py` and `tests/test_clip.py` to assert presence of the new metadata fields and verify the pipeline consumes them without mocks stripping keys. | ✅ | 2026-01-12 |

### Implementation Phase 2

- GOAL-002: Persist detection evidence (timestamps/templates) and integrate it into clip extraction.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Instantiate `TimestampRecorder` inside `Pipeline` detection stage, stream every event to `history/run_*` JSON, and pass the saved path to `ClipExtractor.extract_from_json`. | ✅ | 2026-01-12 |
| TASK-005 | Add `detection.template_dir` to `config/default_config.yaml` and `config/games/battlefield6.yaml`; load templates via `OpenCVMatcher.load_templates` before batch processing. | ✅ | 2026-01-12 |
| TASK-006 | Write regression tests in `tests/test_ai.py` (or new test) that mock template assets and confirm detection weights incorporate template scores when templates exist. | ✅ | 2026-01-12 |

### Implementation Phase 3

- GOAL-003: Harden FFmpeg joining/reporting accuracy and enforce performance guidelines.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Fix `src/video/video_joiner.py` to read durations via `VideoInfo.duration` (float seconds) and guard against missing metadata; add unit tests in `tests/test_transitions.py`. | ✅ | 2026-01-12 |
| TASK-008 | Update `src/report/report_generator.py` to consume `start_ms`/`end_ms`; ensure clip extraction populates these values and add assertions in `tests/test_report.py`. | ✅ | 2026-01-12 |
| TASK-009 | Enhance `src/video/clip_cutter.py` to prefer `-c copy` stream copy when `transition_type` is `none` or single-clip exports, falling back to re-encode otherwise; cover via `tests/test_video.py`. | ✅ | 2026-01-12 |

## 3. Alternatives

- **ALT-001**: Rewriting the pipeline to use a database for timestamps was rejected for adding stateful complexity and violating local-only constraint.
- **ALT-002**: Switching to MoviePy for joins was rejected because FFmpeg already satisfies performance targets and only requires metadata fixes.

## 4. Dependencies

- **DEP-001**: Existing FFmpeg installation with NVENC support (no new deps).
- **DEP-002**: Ultralytics YOLO + PyTorch already present; ensure versions remain unchanged.

## 5. Files

- **FILE-001**: `src/clip/clip_extractor.py` — add metadata fields and filename handling.
- **FILE-002**: `src/pipeline/pipeline.py` — integrate timestamp recorder and clip path consumption.
- **FILE-003**: `src/video/video_joiner.py` — correct duration sourcing.
- **FILE-004**: `src/video/clip_cutter.py` — implement Stream Copy logic.
- **FILE-005**: `src/report/report_generator.py` — render ms-based timings.
- **FILE-006**: `config/default_config.yaml`, `config/games/battlefield6.yaml` — declare template directories.
- **FILE-007**: `tests/test_clip.py`, `tests/test_pipeline.py`, `tests/test_ai.py`, `tests/test_transitions.py`, `tests/test_video.py`, `tests/test_report.py` — expand coverage for fixes.

## 6. Testing

- **TEST-001**: Execute `pytest tests/test_clip.py tests/test_pipeline.py` to verify metadata propagation and pipeline consumption.
- **TEST-002**: Run `pytest tests/test_ai.py` to confirm template loading and timestamp recording logic.
- **TEST-003**: Run `pytest tests/test_transitions.py tests/test_video.py tests/test_report.py` to validate joining, clip cutting, and reporting changes.

## 7. Risks & Assumptions

- **RISK-001**: Stream copy may fail on videos lacking keyframes near cut points; mitigation: auto-fallback to re-encode when FFmpeg returns non-zero.
- **RISK-002**: Large timestamp files could grow history dir; mitigation: reuse existing history cleanup settings.
- **ASSUMPTION-001**: Template assets for Battlefield 6 already exist or can be stubbed for tests.

## 8. Related Specifications / Further Reading

- [plan/feature-fps-video-snap-1.md](feature-fps-video-snap-1.md)
- [../prd.md](../prd.md)