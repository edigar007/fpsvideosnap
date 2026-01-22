# Learnings - bug-paddleocr-init

## 2026-01-21 Session

### Successful Approaches
- **Lazy initialization pattern**: Replace global singleton instantiation (`obj = Class()`) with accessor function (`get_obj() -> Class`) to defer heavy initialization until first use.
- **Exception classification**: Differentiate between "expected" environment errors (DLL missing) and unexpected errors. Log expected errors as `warning` (no traceback), unexpected as `exception`.
- **Force subprocess mode**: When DLL conflicts are common, provide explicit opt-in for subprocess isolation (`force_subprocess=True`) rather than relying on runtime detection.

### Technical Gotchas
- **Import-time side effects**: `from module import singleton` at module top-level triggers initialization. Move to function scope or use accessor.
- **Windows DLL conflicts**: PyTorch and PaddlePaddle GPU can conflict when loaded in same process. Solution: `.venv_paddle` subprocess isolation.
- **Singleton reset in tests**: When testing lazy singletons, must reset `_instance = None` before and after each test.

### Project Conventions
- Config Assistant uses Flask Blueprint pattern
- OCR detection uses PaddleOCR preferred, EasyOCR fallback
- Subprocess OCR worker lives at `.venv_paddle` + `scripts/paddleocr_worker.py`
- Error responses: 503 for "service unavailable" (not 500 for config/environment issues)

### Commands
- Syntax check: `python -m py_compile <file>`
- Tests: `.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py -v`
