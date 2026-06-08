from unittest.mock import MagicMock, patch

import pytest

from src.ai.model_manager import ModelManager


def test_model_manager_rejects_missing_model_by_default():
    manager = ModelManager("models/missing.pt")

    with patch("os.path.exists", return_value=False), \
         patch("src.ai.model_manager.YOLO") as mock_yolo:
        with pytest.raises(FileNotFoundError, match="YOLO model not found"):
            manager.load_model()

    mock_yolo.assert_not_called()


def test_model_manager_allows_explicit_download_path():
    manager = ModelManager("models/missing.pt", allow_model_download=True)
    model = MagicMock()

    with patch("os.path.exists", return_value=False), \
         patch("os.makedirs") as mock_makedirs, \
         patch("src.ai.model_manager.YOLO", return_value=model) as mock_yolo:
        loaded = manager.load_model()

    assert loaded is model
    mock_makedirs.assert_called_once_with("models", exist_ok=True)
    mock_yolo.assert_called_once_with("models/missing.pt")
    model.to.assert_called_once_with(manager.get_device())
