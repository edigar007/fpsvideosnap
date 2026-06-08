"""
Pytest configuration and fixtures for FPS Video Snap tests.

This file mocks heavy ML dependencies (torch, paddle, etc.) to allow
unit tests to run without GPU libraries installed.
"""
import importlib.util
import sys
from unittest.mock import MagicMock

# Mock heavy ML dependencies before any test imports
# This allows tests to run in environments without GPU libraries
# NOTE: cv2 (opencv-python) is NOT mocked because OpenCVMatcher tests need real cv2 functions
_mock_modules = [
    'torch',
    'torch.cuda',
    'torch.nn',
    'ultralytics',
    'paddle',
    'paddleocr',
]

for mod_name in _mock_modules:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Special handling for importlib.util.find_spec to not break on mocked modules
_original_find_spec = importlib.util.find_spec

def _patched_find_spec(name, package=None):
    """Patched find_spec that handles mocked modules gracefully."""
    if name in _mock_modules:
        # Return None to indicate module is not found (skip optional features)
        return None
    return _original_find_spec(name, package)

importlib.util.find_spec = _patched_find_spec
