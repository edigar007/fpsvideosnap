from src.tools.config_assistant.routes import color
from src.tools.config_assistant.routes import config
from src.tools.config_assistant.routes import games
from src.tools.config_assistant.routes import general
from src.tools.config_assistant.routes import legacy
from src.tools.config_assistant.routes import ocr
from src.tools.config_assistant.routes import rules
from src.tools.config_assistant.routes import template


def register_routes(bp) -> None:
    general.register_routes(bp)
    games.register_routes(bp)
    config.register_routes(bp)
    legacy.register_routes(bp)
    ocr.register_routes(bp)
    template.register_routes(bp)
    color.register_routes(bp)
    rules.register_routes(bp)

