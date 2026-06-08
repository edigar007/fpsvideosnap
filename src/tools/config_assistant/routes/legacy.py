import os

import yaml
from flask import jsonify, request
from PIL import Image

from src.tools.config_assistant.config_manager import PROJECT_ROOT
from src.tools.config_assistant.routes.shared import ConfigManagerProxy
from src.tools.config_assistant.utils import validate_identifier
from src.utils.logger import get_logger

logger = get_logger("config_assistant.routes.legacy")
config_manager = ConfigManagerProxy()


def register_routes(bp) -> None:
    @bp.route("/load-config/<game>", methods=["GET"])
    def load_config_legacy(game):
        config = config_manager.get_config(game)
        if config is None:
            return jsonify({"error": f"Config for {game} not found"}), 404
        return jsonify(config)

    @bp.route("/generate-config", methods=["POST"])
    def generate_config_legacy():
        data = request.json or {}
        game_name = data.get("game_name")
        try:
            game_name = validate_identifier(game_name, "game_name")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        rois = data.get("rois", [])
        colors = data.get("colors", [])

        killfeed_roi = [0, 0, 1, 1]
        for roi in rois:
            if roi.get("name") == "killfeed":
                killfeed_roi = [roi.get("x", 0), roi.get("y", 0), roi.get("w", 1), roi.get("h", 1)]
                break

        color_config = {}
        for color in colors:
            name = color.get("name")
            if not name:
                continue
            color_config[name] = {
                "hsv_lower": color.get("hsv_lower", color.get("lower")),
                "hsv_upper": color.get("hsv_upper", color.get("upper")),
                "tolerance": color.get("tolerance", 0),
            }

        config = {
            "game_name": game_name,
            "detection": {
                "killfeed_roi": killfeed_roi,
                "template_dir": f"models/templates/{game_name}",
                "templates": {},
                "colors": color_config,
            },
        }
        return jsonify({"yaml": yaml.dump(config, allow_unicode=True, sort_keys=False)})

    @bp.route("/save-template", methods=["POST"])
    def save_template_legacy():
        data = request.json or {}
        image_path = data.get("image_path")
        game = data.get("game_name")
        name = data.get("template_name")
        roi = data.get("roi")

        if not all([image_path, game, name]):
            return jsonify({"error": "image_path, game_name and template_name are required"}), 400

        try:
            game = validate_identifier(game, "game_name")
            name = validate_identifier(name, "template_name")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if not os.path.exists(image_path):
            return jsonify({"error": "Image not found"}), 404

        target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, f"{name}.png")

        try:
            with Image.open(image_path) as img:
                if roi:
                    left = int(roi.get("x", 0))
                    top = int(roi.get("y", 0))
                    right = left + int(roi.get("w", img.width))
                    bottom = top + int(roi.get("h", img.height))
                    img = img.crop((left, top, right, bottom))
                img.save(target_path)

            rel_path = f"models/templates/{game}/{name}.png"
            return jsonify({"message": "Template saved successfully", "path": rel_path})
        except Exception as exc:
            logger.error(f"Error saving template: {exc}")
            return jsonify({"error": str(exc)}), 500
