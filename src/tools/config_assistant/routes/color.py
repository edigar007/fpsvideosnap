import os

from flask import jsonify, request

from src.tools.config_assistant.services.image_tools import pick_color_sample, preview_color_mask
from src.utils.logger import get_logger

logger = get_logger("config_assistant.routes.color")


def register_routes(bp) -> None:
    @bp.route("/pick-color", methods=["POST"])
    @bp.route("/color/pick", methods=["POST"])
    def pick_color():
        data = request.json
        image_path = data.get("image_path")
        x_value = data.get("x")
        y_value = data.get("y")
        tolerance = data.get("tolerance", [10, 50, 50])

        if image_path is None or x_value is None or y_value is None:
            return jsonify({"error": "Missing parameters"}), 400

        if not os.path.exists(image_path):
            return jsonify({"error": "Image not found"}), 404

        try:
            return jsonify(pick_color_sample(image_path, x_value, y_value, tolerance))
        except Exception as exc:
            logger.error(f"Error picking color: {exc}")
            return jsonify({"error": str(exc)}), 500

    @bp.route("/color/preview", methods=["POST"])
    def preview_color():
        data = request.json
        image_path = data.get("image_path")
        roi = data.get("roi")
        lower = data.get("lower")
        upper = data.get("upper")

        if not all([image_path, lower, upper]):
            return jsonify({"error": "Missing parameters"}), 400

        try:
            mask = preview_color_mask(image_path, roi, lower, upper)
            if mask is None:
                return jsonify({"error": "Failed to load image"}), 400
            return mask, 200, {"Content-Type": "image/png"}
        except Exception as exc:
            logger.error(f"Error previewing color: {exc}")
            return jsonify({"error": str(exc)}), 500

