from flask import current_app, has_app_context

from src.tools.config_assistant.config_manager import config_manager as default_config_manager


def get_config_manager():
    if has_app_context():
        manager = current_app.config.get("CONFIG_MANAGER")
        if manager is not None:
            return manager

    import src.tools.config_assistant.api as api_mod

    return getattr(api_mod, "config_manager", default_config_manager)


class ConfigManagerProxy:
    def __getattr__(self, name):
        return getattr(get_config_manager(), name)
