from flask import jsonify, request

from src.tools.config_assistant.routes.shared import ConfigManagerProxy
from src.tools.config_assistant.utils import validate_identifier

config_manager = ConfigManagerProxy()


def register_routes(bp) -> None:
    @bp.route("/game/list", methods=["GET"])
    def list_games():
        games = config_manager.list_games()
        return jsonify({"games": games})

    @bp.route("/games", methods=["GET"])
    def list_games_legacy():
        return jsonify(config_manager.list_games())

    @bp.route("/game/create", methods=["POST"])
    def create_game():
        data = request.json
        game_name = data.get("game_name")
        try:
            game_name = validate_identifier(game_name, "game_name")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if config_manager.create_game(game_name):
            return jsonify({"message": f"Game '{game_name}' created successfully", "game": game_name})
        return jsonify({"error": f"Failed to create game '{game_name}'. It might already exist."}), 400
