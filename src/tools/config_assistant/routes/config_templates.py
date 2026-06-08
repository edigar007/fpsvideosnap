from flask import jsonify, request

from src.tools.config_assistant.routes.shared import ConfigManagerProxy
from src.tools.config_assistant.services.config_mutation_service import ConfigMutationService

config_manager = ConfigManagerProxy()
mutation_service = ConfigMutationService(config_manager)


def register_routes(bp) -> None:
    @bp.route("/config/<game>/templates", methods=["PUT", "POST"])
    def update_templates_config(game):
        data = request.json or {}
        rule_name = data.get("rule_name")

        if request.method == "POST":
            name = data.get("name")
            roi = data.get("roi")
            path = data.get("path")
            threshold = data.get("threshold", 0.8)

            if not name or not roi:
                return jsonify({"error": "name and roi are required"}), 400

            templates = mutation_service.get_section(game, rule_name, "templates")
            if templates is None:
                return jsonify({"error": f"Config for {game} not found"}), 404

            template_data = {"roi": roi, "threshold": threshold}
            if path:
                template_data["path"] = path
            templates[name] = template_data

            success = mutation_service.save_section(game, rule_name, "templates", templates)
            if success:
                config = mutation_service.get_config_or_error(game)
                return jsonify({"message": f"Template '{name}' added successfully", "config": config})
            return jsonify({"error": "Failed to add template"}), 500

        templates = data.get("templates")
        if not isinstance(templates, dict):
            return jsonify({"error": "Templates must be a dictionary"}), 400

        success = mutation_service.save_section(game, rule_name, "templates", templates)
        if success:
            config = mutation_service.get_config_or_error(game)
            return jsonify({"message": "Templates configuration updated successfully", "config": config})
        return jsonify({"error": "Failed to update templates configuration"}), 500

    @bp.route("/config/<game>/templates/<name>/threshold", methods=["PATCH"])
    def update_template_threshold(game, name):
        data = request.json or {}
        threshold = data.get("threshold")
        rule_name = data.get("rule_name")

        if threshold is None:
            return jsonify({"error": "threshold is required"}), 400

        templates = mutation_service.get_section(game, rule_name, "templates")
        if templates is None:
            return jsonify({"error": f"Config for {game} not found"}), 404
        if name not in templates:
            return jsonify({"error": f"Template '{name}' not found"}), 404

        templates[name]["threshold"] = threshold
        success = mutation_service.save_section(game, rule_name, "templates", templates)
        if success:
            config = mutation_service.get_config_or_error(game)
            return jsonify({"message": f"Template '{name}' threshold updated", "config": config})
        return jsonify({"error": "Failed to update threshold"}), 500

    @bp.route("/config/<game>/templates/<name>", methods=["DELETE"])
    def delete_template_from_config(game, name):
        rule_name = request.args.get("rule_name")
        templates = mutation_service.get_section(game, rule_name, "templates")
        if templates is None:
            return jsonify({"error": f"Config for {game} not found"}), 404
        if name not in templates:
            return jsonify({"error": f"Template '{name}' not found"}), 404

        del templates[name]
        success = mutation_service.save_section(game, rule_name, "templates", templates)
        if success:
            config = mutation_service.get_config_or_error(game)
            return jsonify({"message": f"Template '{name}' deleted from config", "config": config})
        return jsonify({"error": "Failed to delete template"}), 500
