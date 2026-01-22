# Learnings - Incremental Rebuild Feature

## 2026-01-22 Implementation Complete

### Patterns Discovered

1. **Config Fingerprint Generation**
   - Use `json.dumps(data, sort_keys=True)` for stable hashing across Python runs
   - SHA256 with 16-char truncation provides sufficient uniqueness
   - Per-section hashes enable granular invalidation

2. **Stage Invalidation Mapping**
   - `video.*` changes → invalidate from `frames`
   - `detection.*` or `ai.*` changes → invalidate from `detection`
   - `highlights.*` changes → invalidate from `clips`
   - `global.*` changes → invalidate from `audio`

3. **Checkpoint Versioning**
   - Added `CHECKPOINT_VERSION = 2` for future compatibility
   - Old checkpoints without version are treated as incompatible (fresh run)
   - `video_path` stored and validated to prevent cross-video checkpoint reuse

4. **Path Hashing for Checkpoint Naming**
   - Format: `checkpoint_{base_name}_{pathhash8}.json`
   - 8-char SHA256 of full absolute path
   - Prevents different directories with same filename from sharing checkpoint

### Successful Approaches

1. **Fingerprint Module Separation**
   - Created `src/config/fingerprint.py` as standalone module
   - Clean imports into pipeline.py
   - Easy to test independently (10 tests pass without heavy deps)

2. **Chain Fallback for Missing Intermediates**
   - When final output missing + joined_video missing → re-run join stage
   - Clips checked before attempting join
   - Graceful degradation if clips also missing

3. **Unique Output Path Function**
   - `get_unique_output_path(base_path)` finds `_1`, `_2`, `_3`... suffix
   - Only applied when actually re-running audio stage
   - Safety limit of 9999 attempts

4. **Test Mocking Strategy**
   - Created `tests/conftest.py` to mock heavy ML deps (torch, paddleocr)
   - Patches `importlib.util.find_spec` to return None for mocked modules
   - Enables tests to run in environments without GPU libraries

### Technical Gotchas

1. **Windows Path Handling**
   - PowerShell required for reliable command execution
   - Backslash escaping in paths: `\\` in strings

2. **Import Order for Mocking**
   - Heavy deps (torch, etc) must be mocked BEFORE importing pipeline
   - `conftest.py` runs before test collection, ideal location

3. **os.path.exists Mocking Conflicts**
   - Existing tests mock `os.path.exists` globally to return True
   - This breaks `get_unique_output_path` which loops infinitely
   - New tests use targeted mocking with tempfile.TemporaryDirectory
