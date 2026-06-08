import random
from typing import Optional
from src.utils.logger import logger

class TransitionManager:
    """Manages video transition selection and configuration."""
    
    SUPPORTED_TRANSITIONS = [
        "fade", "wipeleft", "wiperight", "slideup", "slidedown", 
        "circleopen", "circleclose", "rectcrop", "distance", "pixelize", "radial"
    ]

    def __init__(self, transition_type: str = "random", duration: float = 0.5):
        self.transition_type = transition_type.lower()
        self.duration = duration
        
    def get_transition(self) -> Optional[str]:
        """Returns a transition name based on the configuration."""
        if self.transition_type == "none":
            return None
            
        if self.transition_type == "random":
            return random.choice(self.SUPPORTED_TRANSITIONS)
            
        if self.transition_type in self.SUPPORTED_TRANSITIONS:
            return self.transition_type
            
        logger.warning(f"Transition type '{self.transition_type}' not supported. Falling back to 'fade'.")
        return "fade"

    def get_duration(self) -> float:
        """Returns the transition duration in seconds."""
        return self.duration

    @classmethod
    def is_supported(cls, transition: str) -> bool:
        """Checks if a transition type is supported by FFmpeg xfade."""
        return transition.lower() in cls.SUPPORTED_TRANSITIONS or transition.lower() in ["random", "none"]
