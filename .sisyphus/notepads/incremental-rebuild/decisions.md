# Decisions - Incremental Rebuild Feature

## 2026-01-22

### Decision 1: Fingerprint Granularity
**Choice**: Coarse-grained (per config section)
**Rationale**: User requested simplicity. Fine-grained per-field tracking adds complexity without clear benefit.
**Trade-off**: If any field in a section changes, entire section's stages re-run (acceptable).

### Decision 2: Checkpoint Version Handling
**Choice**: Reject old checkpoints without version (fresh run)
**Rationale**: Safer than attempting migration. Old checkpoints lack video_path and fingerprints, can't validate.
**Trade-off**: One-time re-run after upgrade (acceptable).

### Decision 3: Final Output Naming
**Choice**: Only suffix `_1`, `_2` when actually re-running audio stage
**Rationale**: User explicitly wanted: "config unchanged + final exists → skip entirely (no new `_n`)".
**Implementation**: Check `need_audio_mixing` && `final_video_exists` before calling `get_unique_output_path`.

### Decision 4: Chain Fallback Scope
**Choice**: Minimal chain - only rebuild what's needed for final
**Rationale**: User said "mainly focus on final output existence". Don't validate entire intermediate chain.
**Implementation**: If final missing, check joined_video; if that's missing, check clips; rebuild as needed.

### Decision 5: Test Environment
**Choice**: Mock heavy ML deps in conftest.py
**Rationale**: Project venv may not have torch/paddleocr installed in CI environments.
**Implementation**: Pre-mock modules in sys.modules before any test imports.
