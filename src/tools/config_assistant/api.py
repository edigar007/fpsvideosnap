from flask import Blueprint

from src.tools.config_assistant.config_manager import PROJECT_ROOT, config_manager
from src.tools.config_assistant.routes import register_routes

api_bp = Blueprint("api", __name__)
register_routes(api_bp)

__all__ = ["PROJECT_ROOT", "api_bp", "config_manager"]
