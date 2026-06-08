from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class PipelineContext:
    config: Dict[str, Any]
    video_path: str
    base_name: str
    temp_dir: str
    checkpoint_file: str = ""
    results: Dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
