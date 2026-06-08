import os

from flask import current_app, has_app_context

from src.tools.config_assistant.config_manager import config_manager as default_config_manager


def get_config_manager():
    import src.tools.config_assistant.api as api_mod

    manager = api_mod.config_manager
    if not has_app_context():
        return manager

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    manager_root = getattr(manager, "project_root", "")
    if upload_folder and manager_root:
        try:
            upload_folder_abs = os.path.abspath(upload_folder)
            manager_root_abs = os.path.abspath(manager_root)
            if os.path.commonpath([upload_folder_abs, manager_root_abs]) == manager_root_abs:
                return manager
        except ValueError:
            pass

    return default_config_manager


class ConfigManagerProxy:
    def __getattr__(self, name):
        return getattr(get_config_manager(), name)
