import os
import json
import yaml
import time
from datetime import datetime
from typing import List, Dict, Any
from src.utils.logger import logger


class HistoryManager:
    """
    Manages saving configuration snapshots and detection results.
    Also handles cleanup of old history files.
    """

    def __init__(self, history_dir: str, config: Dict[str, Any] = None):
        self.history_dir = os.path.abspath(history_dir)
        self.config = config or {}

        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)

    def save_run(self, config_to_save: Dict[str, Any], results_to_save: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Saves the config and results with a timestamped filename.
        Returns a dict with the paths to the saved files.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        config_path = os.path.join(self.history_dir, f"config_{timestamp}.yaml")
        results_path = os.path.join(self.history_dir, f"results_{timestamp}.json")

        # Save Config (Snapshot)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_to_save, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Failed to save history config: {e}")

        # Save Results (JSON)
        try:
            with open(results_path, 'w', encoding='utf-8') as f:
                json.dump(results_to_save, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save history results: {e}")

        # Clean up old files
        self.cleanup()

        return {
            "config": config_path,
            "results": results_path
        }

    def cleanup(self):
        """
        Cleans up old history files based on keep_history_days and max_history_files.
        """
        global_cfg = self.config.get("global", {})
        keep_days = global_cfg.get("keep_history_days", 30)
        max_files = global_cfg.get("max_history_files", 100)

        if not os.path.exists(self.history_dir):
            return

        # List all history files
        files = []
        for f in os.listdir(self.history_dir):
            if f.startswith("config_") or f.startswith("results_"):
                path = os.path.join(self.history_dir, f)
                if os.path.isfile(path):
                    files.append({
                        "path": path,
                        "mtime": os.path.getmtime(path)
                    })

        if not files:
            return

        # Sort by mtime (oldest first)
        files.sort(key=lambda x: x["mtime"])

        # 1. Cleanup by days
        now = time.time()
        files_to_remove = []
        remaining_files = []

        for f in files:
            age_days = (now - f["mtime"]) / (24 * 3600)
            if age_days > keep_days:
                files_to_remove.append(f)
            else:
                remaining_files.append(f)

        # 2. Cleanup by count (max_files refers to pairs of config/results, so we double it)
        # Actually let's assume max_files is total files in history dir
        if len(remaining_files) > max_files:
            num_to_remove = len(remaining_files) - max_files
            files_to_remove.extend(remaining_files[:num_to_remove])

        # Perform removal
        for f in files_to_remove:
            try:
                os.remove(f["path"])
                logger.debug(f"Removed old history file: {f['path']}")
            except Exception as e:
                logger.warning(f"Failed to remove old history file {f['path']}: {e}")
