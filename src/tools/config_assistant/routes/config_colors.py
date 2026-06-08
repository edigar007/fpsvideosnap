from flask import jsonify, request

from src.tools.config_assistant.routes.shared import ConfigManagerProxy
from src.tools.config_assistant.services.config_mutation_service import ConfigMutationService
from src.tools.config_assistant.utils import calculate_hsv_range

config_manager = ConfigManagerProxy()
mutation_service = ConfigMutationService(config_manager)


def register_routes(bp) -> None:
    @bp.route("/config/<game>/colors", methods=["PUT", "POST"])
    def update_colors(game):
        data = request.json or {}
        rule_name = data.get("rule_name")

        if request.method == "POST":
            name = data.get("name")
            hsv = data.get("hsv")
            hsv_lower = data.get("hsv_lower")
            hsv_upper = data.get("hsv_upper")
            tolerance = data.get("tolerance", 20)

            if not name or hsv_lower is None or hsv_upper is None:
                return jsonify({"error": "name, hsv_lower and hsv_upper are required"}), 400

            colors = mutation_service.get_section(game, rule_name, "colors")
            if colors is None:
                return jsonify({"error": f"Config for {game} not found"}), 404

            colors[name] = {
                "hsv": hsv,
                "hsv_lower": hsv_lower,
                "hsv_upper": hsv_upper,
                "tolerance": tolerance,
            }
            if hsv is None:
                colors[name].pop("hsv")

            success = mutation_service.save_section(game, rule_name, "colors", colors)
            if success:
                config = mutation_service.get_config_or_error(game)
                return jsonify({"message": f"Color '{name}' added successfully", "config": config})
            return jsonify({"error": "Failed to add color"}), 500

        colors = data.get("colors")
        if not isinstance(colors, dict):
            return jsonify({"error": "Colors must be a dictionary"}), 400

        success = mutation_service.save_section(game, rule_name, "colors", colors)
        if success:
            config = mutation_service.get_config_or_error(game)
            return jsonify({"message": "Colors configuration updated successfully", "config": config})
        return jsonify({"error": "Failed to update colors configuration"}), 500

    @bp.route("/config/<game>/colors/<name>/tolerance", methods=["PATCH"])
    def update_color_tolerance(game, name):
        data = request.json or {}
        tolerance = data.get("tolerance")
        rule_name = data.get("rule_name")

        if tolerance is None:
            return jsonify({"error": "tolerance is required"}), 400

        colors = mutation_service.get_section(game, rule_name, "colors")
        if colors is None:
            return jsonify({"error": f"Config for {game} not found"}), 404
        if name not in colors:
            return jsonify({"error": f"Color '{name}' not found"}), 404

        color = colors[name]
        color["tolerance"] = tolerance
        hsv = color.get("hsv")
        if hsv is None:
            hsv_lower = color.get("hsv_lower")
            hsv_upper = color.get("hsv_upper")
            if hsv_lower and hsv_upper:
                hsv = [
                    int((hsv_lower[0] + hsv_upper[0]) / 2),
                    int((hsv_lower[1] + hsv_upper[1]) / 2),
                    int((hsv_lower[2] + hsv_upper[2]) / 2),
                ]
                color["hsv"] = hsv

        if hsv:
            lower, upper = calculate_hsv_range(hsv[0], hsv[1], hsv[2], (tolerance, tolerance * 2, tolerance * 2))
            color["hsv_lower"] = lower
            color["hsv_upper"] = upper

        success = mutation_service.save_section(game, rule_name, "colors", colors)
        if success:
            config = mutation_service.get_config_or_error(game)
            return jsonify({"message": f"Color '{name}' tolerance updated", "config": config})
        return jsonify({"error": "Failed to update tolerance"}), 500

    @bp.route("/config/<game>/colors/<name>", methods=["DELETE"])
    def delete_color_from_config(game, name):
        rule_name = request.args.get("rule_name")
        colors = mutation_service.get_section(game, rule_name, "colors")
        if colors is None:
            return jsonify({"error": f"Config for {game} not found"}), 404
        if name not in colors:
            return jsonify({"error": f"Color '{name}' not found"}), 404

        del colors[name]
        success = mutation_service.save_section(game, rule_name, "colors", colors)
        if success:
            config = mutation_service.get_config_or_error(game)
            return jsonify({"message": f"Color '{name}' deleted from config", "config": config})
        return jsonify({"error": "Failed to delete color"}), 500
