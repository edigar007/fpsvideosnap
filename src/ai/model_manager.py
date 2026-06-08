import torch
import os
from ultralytics import YOLO
from src.utils.logger import get_logger

logger = get_logger(__name__)

class ModelManager:
    """
    Manages the lifecycle of AI models, specifically YOLOv8.
    Handles device selection (CUDA/CPU) and model loading.
    """
    def __init__(self, model_path="models/yolov8n.pt", allow_model_download: bool = False):
        self.model_path = model_path
        self.allow_model_download = allow_model_download
        self._device = self._get_optimal_device()
        self.model = None
        
    def _get_optimal_device(self):
        """
        Detects if CUDA is available and returns the appropriate device string.
        """
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"CUDA detected: {device_name}. Using GPU for inference.")
            return "cuda"
        else:
            logger.warning("CUDA not found. Falling back to CPU. Inference will be slow.")
            return "cpu"

    def load_model(self):
        """
        Loads the YOLOv8 model from the specified path.
        Missing models fail by default to keep normal runs offline. Set
        allow_model_download=True during setup to permit Ultralytics downloads.
        """
        try:
            logger.info(f"Loading YOLOv8 model from {self.model_path} on {self._device}...")
            if not os.path.exists(self.model_path) and not self.allow_model_download:
                raise FileNotFoundError(
                    f"YOLO model not found: {self.model_path}. "
                    "Place the model file locally or set ai.allow_model_download=true for initial setup."
                )

            # Ensure the directory exists
            model_dir = os.path.dirname(self.model_path)
            if model_dir:
                os.makedirs(model_dir, exist_ok=True)
            
            self.model = YOLO(self.model_path)
            self.model.to(self._device)
            logger.info("Model loaded successfully.")
            return self.model
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise

    def get_device(self):
        return self._device

    def cleanup(self):
        """
        Clears the model from memory and GPU.
        """
        if self.model:
            logger.info("Cleaning up model and clearing GPU cache.")
            del self.model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.model = None
