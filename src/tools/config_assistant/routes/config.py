import os

from flask import jsonify, request

from src.tools.config_assistant.config_manager import PROJECT_ROOT
from src.tools.config_assistant.routes.shared import ConfigManagerProxy
from src.tools.config_assistant.services.config_test_service import ConfigTestService

config_manager = ConfigManagerProxy()


def _rule_override_values(game: str, rule_name: str, section: str) -> dict:
    config = config_manager.get_config(game)
    if not config:
        return {}
    rules = config.get("detection", {}).get("rules", [])
    target_rule = next((r for r in rules if r.get("name") == rule_name), None)
    return target_rule.get("detection_overrides", {}).get(section, {}) if target_rule else {}


def _config_section_values(game: str, section: str) -> dict:
    config = config_manager.get_config(game)
    if not config:
        return {}
    return config.get("detection", {}).get(section, {})


def _update_detection_or_rule(game: str, rule_name: str | None, key: str, value) -> bool:
    if rule_name:
        return config_manager.update_rule_override(game, rule_name, key, value)
    return config_manager.update_config_section(game, f"detection.{key}", value)


def register_routes(bp) -> None:
    @bp.route("/config/<game>", methods=["GET"])
    def get_config(game):
        config = config_manager.get_config(game)
        if config:
            return jsonify(config)
        return jsonify({"error": f"Config for {game} not found"}), 404

    @bp.route("/config/<game>/roi", methods=["PUT"])
    def update_roi(game):
        data = request.json
        roi = data.get("roi")
        rule_name = data.get("rule_name")

        if not isinstance(roi, list) or len(roi) != 4:
            return jsonify({"error": "Invalid ROI format. Expected [x, y, w, h]"}), 400

        success = _update_detection_or_rule(game, rule_name, "killfeed_roi", roi)
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": "ROI updated successfully", "config": config})
        return jsonify({"error": "Failed to update ROI"}), 500

    @bp.route("/config/<game>/ocr", methods=["PUT"])
    def update_ocr(game):
        data = request.json
        enabled = data.get("enabled", True)
        keywords = data.get("keywords")
        similarity = data.get("similarity_threshold", 0.8)
        rule_name = data.get("rule_name")

        if not isinstance(keywords, list):
            return jsonify({"error": "Keywords must be a list"}), 400

        success = (
            _update_detection_or_rule(game, rule_name, "ocr.enabled", enabled)
            and _update_detection_or_rule(game, rule_name, "ocr.keywords", keywords)
            and _update_detection_or_rule(game, rule_name, "ocr.similarity_threshold", similarity)
        )

        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": "OCR configuration updated successfully", "config": config})
        return jsonify({"error": "Failed to update OCR configuration"}), 500

    @bp.route("/config/<game>/templates", methods=["PUT", "POST"])
    def update_templates_config(game):
        data = request.json
        rule_name = data.get("rule_name")

        if request.method == "POST":
            name = data.get("name")
            roi = data.get("roi")
            path = data.get("path")
            threshold = data.get("threshold", 0.8)

            if not name or not roi:
                return jsonify({"error": "name and roi are required"}), 400

            config = config_manager.get_config(game)
            if not config:
                return jsonify({"error": f"Config for {game} not found"}), 404

            templates = (
                _rule_override_values(game, rule_name, "templates")
                if rule_name
                else _config_section_values(game, "templates")
            )
            template_data = {"roi": roi, "threshold": threshold}
            if path:
                template_data["path"] = path
            templates[name] = template_data

            success = _update_detection_or_rule(game, rule_name, "templates", templates)
            if success:
                config = config_manager.get_config(game)
                return jsonify({"message": f"Template '{name}' added successfully", "config": config})
            return jsonify({"error": "Failed to add template"}), 500

        templates = data.get("templates")
        if not isinstance(templates, dict):
            return jsonify({"error": "Templates must be a dictionary"}), 400

        success = _update_detection_or_rule(game, rule_name, "templates", templates)
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": "Templates configuration updated successfully", "config": config})
        return jsonify({"error": "Failed to update templates configuration"}), 500

    @bp.route("/config/<game>/templates/<name>/threshold", methods=["PATCH"])
    def update_template_threshold(game, name):
        data = request.json
        threshold = data.get("threshold")
        rule_name = data.get("rule_name")

        if threshold is None:
            return jsonify({"error": "threshold is required"}), 400

        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404

        templates = (
            _rule_override_values(game, rule_name, "templates")
            if rule_name
            else _config_section_values(game, "templates")
        )
        if name not in templates:
            return jsonify({"error": f"Template '{name}' not found"}), 404

        templates[name]["threshold"] = threshold
        success = _update_detection_or_rule(game, rule_name, "templates", templates)
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": f"Template '{name}' threshold updated", "config": config})
        return jsonify({"error": "Failed to update threshold"}), 500

    @bp.route("/config/<game>/templates/<name>", methods=["DELETE"])
    def delete_template_from_config(game, name):
        rule_name = request.args.get("rule_name")
        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404

        templates = (
            _rule_override_values(game, rule_name, "templates")
            if rule_name
            else _config_section_values(game, "templates")
        )
        if name not in templates:
            return jsonify({"error": f"Template '{name}' not found"}), 404

        del templates[name]
        success = _update_detection_or_rule(game, rule_name, "templates", templates)
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": f"Template '{name}' deleted from config", "config": config})
        return jsonify({"error": "Failed to delete template"}), 500

    @bp.route("/config/<game>/colors", methods=["PUT", "POST"])
    def update_colors(game):
        data = request.json
        rule_name = data.get("rule_name")

        if request.method == "POST":
            name = data.get("name")
            hsv = data.get("hsv")
            hsv_lower = data.get("hsv_lower")
            hsv_upper = data.get("hsv_upper")
            tolerance = data.get("tolerance", 20)

            if not name or hsv_lower is None or hsv_upper is None:
                return jsonify({"error": "name, hsv_lower and hsv_upper are required"}), 400

            config = config_manager.get_config(game)
            if not config:
                return jsonify({"error": f"Config for {game} not found"}), 404

            colors = (
                _rule_override_values(game, rule_name, "colors")
                if rule_name
                else _config_section_values(game, "colors")
            )
            colors[name] = {
                "hsv": hsv,
                "hsv_lower": hsv_lower,
                "hsv_upper": hsv_upper,
                "tolerance": tolerance,
            }
            if hsv is None:
                colors[name].pop("hsv")

            success = _update_detection_or_rule(game, rule_name, "colors", colors)
            if success:
                config = config_manager.get_config(game)
                return jsonify({"message": f"Color '{name}' added successfully", "config": config})
            return jsonify({"error": "Failed to add color"}), 500

        colors = data.get("colors")
        if not isinstance(colors, dict):
            return jsonify({"error": "Colors must be a dictionary"}), 400

        success = _update_detection_or_rule(game, rule_name, "colors", colors)
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": "Colors configuration updated successfully", "config": config})
        return jsonify({"error": "Failed to update colors configuration"}), 500

    @bp.route("/config/<game>/colors/<name>/tolerance", methods=["PATCH"])
    def update_color_tolerance(game, name):
        from src.tools.config_assistant.utils import calculate_hsv_range

        data = request.json
        tolerance = data.get("tolerance")
        rule_name = data.get("rule_name")

        if tolerance is None:
            return jsonify({"error": "tolerance is required"}), 400

        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404

        colors = (
            _rule_override_values(game, rule_name, "colors")
            if rule_name
            else _config_section_values(game, "colors")
        )
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

        success = _update_detection_or_rule(game, rule_name, "colors", colors)
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": f"Color '{name}' tolerance updated", "config": config})
        return jsonify({"error": "Failed to update tolerance"}), 500

    @bp.route("/config/<game>/colors/<name>", methods=["DELETE"])
    def delete_color_from_config(game, name):
        rule_name = request.args.get("rule_name")
        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404

        colors = (
            _rule_override_values(game, rule_name, "colors")
            if rule_name
            else _config_section_values(game, "colors")
        )
        if name not in colors:
            return jsonify({"error": f"Color '{name}' not found"}), 404

        del colors[name]
        success = _update_detection_or_rule(game, rule_name, "colors", colors)
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": f"Color '{name}' deleted from config", "config": config})
        return jsonify({"error": "Failed to delete color"}), 500

    @bp.route("/config/<game>/export", methods=["GET"])
    def export_config(game):
        yaml_str = config_manager.export_config_yaml(game)
        if yaml_str:
            return jsonify({"yaml": yaml_str})
        return jsonify({"error": f"Failed to export config for {game}"}), 404

    @bp.route("/config/<game>/test-image", methods=["POST"])
    def test_config_image(game):
        config = config_manager.get_config(game)
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
