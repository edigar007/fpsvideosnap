from flask import jsonify, request

from src.tools.config_assistant.routes.shared import ConfigManagerProxy
from src.tools.config_assistant.services.rule_validation import validate_rules

config_manager = ConfigManagerProxy()


def register_routes(bp) -> None:
    @bp.route("/config/<game>/rules", methods=["GET"])
    def get_rules(game):
        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404

        rules = config.get("detection", {}).get("rules", [])
        return jsonify({"rules": rules})

    @bp.route("/config/<game>/rules", methods=["PUT"])
    def update_rules(game):
        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404

        data = request.json
        rules = data.get("rules")

        if rules is None:
            return jsonify({"error": "'rules' field is required"}), 400

        try:
            validate_rules(rules)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if config_manager.update_config_section(game, "detection.rules", rules):
            config = config_manager.get_config(game)
            return jsonify({"message": "Rules updated", "config": config})
        return jsonify({"error": "Failed to update rules"}), 500
