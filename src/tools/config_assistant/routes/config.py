import os

from flask import jsonify, request

from src.tools.config_assistant.config_manager import PROJECT_ROOT
from src.tools.config_assistant.routes.shared import ConfigManagerProxy
from src.tools.config_assistant.services.config_mutation_service import ConfigMutationService
from src.tools.config_assistant.services.config_test_service import ConfigTestService

config_manager = ConfigManagerProxy()
mutation_service = ConfigMutationService(config_manager)


def register_routes(bp) -> None:
    @bp.route("/config/<game>", methods=["GET"])
    def get_config(game):
        config = mutation_service.get_config_or_error(game)
        if config:
            return jsonify(config)
        return jsonify({"error": f"Config for {game} not found"}), 404

    @bp.route("/config/<game>/roi", methods=["PUT"])
    def update_roi(game):
        data = request.json or {}
        roi = data.get("roi")
        rule_name = data.get("rule_name")

        if not isinstance(roi, list) or len(roi) != 4:
            return jsonify({"error": "Invalid ROI format. Expected [x, y, w, h]"}), 400

        success = mutation_service.update_detection_or_rule(game, rule_name, "killfeed_roi", roi)
        if success:
            config = mutation_service.get_config_or_error(game)
            return jsonify({"message": "ROI updated successfully", "config": config})
        return jsonify({"error": "Failed to update ROI"}), 500

    @bp.route("/config/<game>/ocr", methods=["PUT"])
    def update_ocr(game):
        data = request.json or {}
        enabled = data.get("enabled", True)
        keywords = data.get("keywords")
        similarity = data.get("similarity_threshold", 0.8)
        rule_name = data.get("rule_name")

        if not isinstance(keywords, list):
            return jsonify({"error": "Keywords must be a list"}), 400

        success = (
            mutation_service.update_detection_or_rule(game, rule_name, "ocr.enabled", enabled)
            and mutation_service.update_detection_or_rule(game, rule_name, "ocr.keywords", keywords)
            and mutation_service.update_detection_or_rule(game, rule_name, "ocr.similarity_threshold", similarity)
        )

        if success:
            config = mutation_service.get_config_or_error(game)
            return jsonify({"message": "OCR configuration updated successfully", "config": config})
        return jsonify({"error": "Failed to update OCR configuration"}), 500

    @bp.route("/config/<game>/export", methods=["GET"])
    def export_config(game):
        yaml_str = config_manager.export_config_yaml(game)
        if yaml_str:
            return jsonify({"yaml": yaml_str})
        return jsonify({"error": f"Failed to export config for {game}"}), 404

    @bp.route("/config/<game>/test-image", methods=["POST"])
    def test_config_image(game):
        config = mutation_service.get_config_or_error(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404

        data = request.json or {}
        image_path = data.get("image_path")
        if not image_path:
            return jsonify({"error": "image_path is required"}), 400
        if not os.path.exists(image_path):
            return jsonify({"error": f"Image file not found: {image_path}"}), 404

        try:
            response = ConfigTestService(PROJECT_ROOT).test_image(game, config, image_path)
        except ValueError:
            return jsonify({"error": "Failed to load image"}), 400
        return jsonify(response)
