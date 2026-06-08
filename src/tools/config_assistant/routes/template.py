import os

from flask import jsonify, request, send_from_directory

from src.tools.config_assistant.config_manager import PROJECT_ROOT
from src.tools.config_assistant.services.image_tools import crop_relative_region, list_template_files
from src.tools.config_assistant.utils import validate_identifier
from src.utils.logger import get_logger

logger = get_logger("config_assistant.routes.template")


def register_routes(bp) -> None:
    @bp.route("/template/crop", methods=["POST"])
    def crop_template():
        data = request.json
        image_path = data.get("image_path")
        game = data.get("game")
        name = data.get("name")
        sub_roi = data.get("sub_roi")

        if not all([image_path, game, name, sub_roi]):
            return jsonify({"error": "Missing parameters"}), 400

        try:
            name = validate_identifier(name, "template_name")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, f"{name}.png")

        try:
            crop_relative_region(image_path, target_path, sub_roi)
            rel_path = f"models/templates/{game}/{name}.png"
            return jsonify({"message": "Template cropped successfully", "path": rel_path})
        except Exception as exc:
            logger.error(f"Error cropping template: {exc}")
            return jsonify({"error": str(exc)}), 500

    @bp.route("/template/<game>/list", methods=["GET"])
    def list_templates(game):
        target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
        templates = list_template_files(target_dir)
        for template in templates:
            template["url"] = f"/api/template/{game}/view/{template['filename']}"
        return jsonify(templates)

    @bp.route("/template/<game>/view/<filename>", methods=["GET"])
    def view_template(game, filename):
        target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
        return send_from_directory(target_dir, filename)

    @bp.route("/template/<game>/<name>", methods=["DELETE"])
    def delete_template(game, name):
        target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
        deleted = False
        for ext in [".png", ".jpg", ".jpeg"]:
            target_path = os.path.join(target_dir, f"{name}{ext}")
            if os.path.exists(target_path):
                os.remove(target_path)
                deleted = True
                break

        if deleted:
            return jsonify({"message": f"Template '{name}' deleted"})
        return jsonify({"error": f"Template '{name}' not found"}), 404

