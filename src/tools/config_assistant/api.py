import os
import shutil
import cv2
import numpy as np
import yaml
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from PIL import Image
from src.ai.opencv_matcher import OpenCVMatcher
from src.tools.config_assistant.utils import rgb_to_hsv, calculate_hsv_range, validate_identifier
from src.tools.config_assistant.ocr_service import get_ocr_service, OCRUnavailableError
from src.tools.config_assistant.config_manager import config_manager, PROJECT_ROOT # Imported PROJECT_ROOT
from src.utils.logger import get_logger

logger = get_logger("config_assistant.api")
api_bp = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _normalize_roi(roi: Optional[List[float]]) -> List[float]:
    """Clamp a normalized [x, y, w, h] ROI to image-relative bounds."""
    if not isinstance(roi, list) or len(roi) != 4:
        return [0.0, 0.0, 1.0, 1.0]

    try:
        x, y, w, h = [float(v) for v in roi]
    except (TypeError, ValueError):
        return [0.0, 0.0, 1.0, 1.0]

    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.0, min(1.0 - x, w))
    h = max(0.0, min(1.0 - y, h))

    if w <= 0.0 or h <= 0.0:
        return [0.0, 0.0, 1.0, 1.0]
    return [x, y, w, h]


def _get_color_bounds(color_cfg: Dict[str, Any]) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """
    Return HSV bounds using the same rules as KillDetector:
    explicit lower/upper values win; tolerance applies only to center HSV.
    """
    hsv_lower = color_cfg.get("hsv_lower", color_cfg.get("lower"))
    hsv_upper = color_cfg.get("hsv_upper", color_cfg.get("upper"))
    if hsv_lower and hsv_upper:
        return hsv_lower, hsv_upper

    hsv = color_cfg.get("hsv")
    if not hsv:
        return None, None

    tolerance = color_cfg.get("tolerance", 0)
    if isinstance(tolerance, (int, float)):
        tolerance = [tolerance, tolerance * 2, tolerance * 2]

    if not isinstance(tolerance, (list, tuple)) or len(tolerance) != 3:
        return None, None

    return (
        [
            max(0, hsv[0] - tolerance[0]),
            max(0, hsv[1] - tolerance[1]),
            max(0, hsv[2] - tolerance[2]),
        ],
        [
            min(179, hsv[0] + tolerance[0]),
            min(255, hsv[1] + tolerance[1]),
            min(255, hsv[2] + tolerance[2]),
        ],
    )


def _merge_detection_config(detection_cfg: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
    """Merge rule.detection_overrides into the global detection config."""
    effective_cfg = deepcopy(detection_cfg)
    overrides = rule.get("detection_overrides", {})
    if not isinstance(overrides, dict):
        return effective_cfg

    for key, value in overrides.items():
        if isinstance(effective_cfg.get(key), dict) and isinstance(value, dict):
            merged = deepcopy(effective_cfg[key])
            merged.update(value)
            effective_cfg[key] = merged
        else:
            effective_cfg[key] = deepcopy(value)
    return effective_cfg


def _text_similarity(text: str, keyword: str) -> float:
    """Return a simple fuzzy similarity in the same 0.0-1.0 range used by OCRDetector."""
    if not text or not keyword:
        return 0.0
    return SequenceMatcher(None, text.lower(), keyword.lower()).ratio()


def _match_ocr_keywords(detections: List[Dict[str, Any]], ocr_cfg: Dict[str, Any]) -> Dict[str, Any]:
    keywords = ocr_cfg.get("keywords", []) or []
    threshold = float(ocr_cfg.get("similarity_threshold", ocr_cfg.get("threshold", 0.8)))

    best = {
        "found": False,
        "signal": 0.0,
        "matched_keyword": None,
        "text": None,
        "similarity": 0.0,
        "confidence": 0.0,
    }

    for det in detections:
        text = str(det.get("text", "")).strip()
        confidence = float(det.get("confidence", 0.0) or 0.0)
        for keyword in keywords:
            similarity = _text_similarity(text, str(keyword))
            if similarity >= threshold and similarity > best["similarity"]:
                best.update({
                    "found": True,
                    "signal": confidence,
                    "matched_keyword": keyword,
                    "text": text,
                    "similarity": similarity,
                    "confidence": confidence,
                })

    return best


def _evaluate_test_signals(
    frame: np.ndarray,
    image_path: str,
    detection_cfg: Dict[str, Any],
    matcher: OpenCVMatcher,
) -> Dict[str, Any]:
    """Run local, single-image signals used by the config assistant test endpoint."""
    roi = _normalize_roi(detection_cfg.get("killfeed_roi", [0, 0, 1, 1]))
    prefilter_cfg = detection_cfg.get("prefilter", {}) or {}
    color_threshold = float(prefilter_cfg.get("color_threshold", 0.01))

    color_details = []
    max_color_pct = 0.0
    for color_name, color_cfg in (detection_cfg.get("colors", {}) or {}).items():
        if not isinstance(color_cfg, dict):
            continue
        hsv_lower, hsv_upper = _get_color_bounds(color_cfg)
        if not hsv_lower or not hsv_upper:
            color_details.append({
                "name": color_name,
                "matched": False,
                "match_percent": 0.0,
                "error": "HSV range missing",
            })
            continue

        match_percent = matcher.detect_color(frame, hsv_lower, hsv_upper, roi=roi)
        max_color_pct = max(max_color_pct, match_percent)
        color_details.append({
            "name": color_name,
            "matched": match_percent >= color_threshold,
            "match_percent": match_percent,
            "threshold": color_threshold,
            "hsv_lower": hsv_lower,
            "hsv_upper": hsv_upper,
        })

    color_signal = min(max_color_pct * 50, 1.0)

    template_details = []
    max_template_score = 0.0
    templates_cfg = detection_cfg.get("templates", {}) or {}
    template_names = list(templates_cfg.keys()) if templates_cfg else list(matcher.templates.keys())
    for template_name in template_names:
        template_cfg = templates_cfg.get(template_name, {}) if isinstance(templates_cfg, dict) else {}
        threshold = template_cfg.get("threshold", 0.8) if isinstance(template_cfg, dict) else 0.8
        location, score = matcher.match_template(frame, template_name, threshold=threshold, roi=roi)
        max_template_score = max(max_template_score, float(score or 0.0))
        template_details.append({
            "name": template_name,
            "matched": location is not None,
            "score": float(score or 0.0),
            "threshold": threshold,
            "loaded": template_name in matcher.templates,
        })

    ocr_cfg = detection_cfg.get("ocr", {}) or {}
    ocr_details = {
        "enabled": bool(ocr_cfg.get("enabled", False)),
        "available": False,
        "detections": [],
        "match": {
            "found": False,
            "signal": 0.0,
            "matched_keyword": None,
            "text": None,
            "similarity": 0.0,
            "confidence": 0.0,
        },
    }
    warnings = []

    if ocr_details["enabled"]:
        try:
            ocr_service = get_ocr_service()
            detections = ocr_service.detect(image_path, roi)
            ocr_details["available"] = True
            ocr_details["detections"] = detections
            ocr_details["match"] = _match_ocr_keywords(detections, ocr_cfg)
        except OCRUnavailableError as e:
            warnings.append(f"OCR unavailable: {e}")
            ocr_details["error"] = str(e)
        except Exception as e:
            logger.error(f"Config test OCR failed: {e}", exc_info=True)
            warnings.append(f"OCR failed: {e}")
            ocr_details["error"] = str(e)

    yolo_details = {
        "available": False,
        "signal": 0.0,
        "note": "YOLO is not run inside the config assistant image test.",
    }

    return {
        "roi": roi,
        "signals": {
            "ocr": float(ocr_details["match"]["signal"]),
            "template": float(max_template_score),
            "color": float(color_signal),
            "yolo": 0.0,
        },
        "booleans": {
            "ocr": bool(ocr_details["match"]["found"]),
            "template": any(item["matched"] for item in template_details),
            "color": max_color_pct >= color_threshold,
            "yolo": False,
        },
        "color": {
            "max_match_percent": max_color_pct,
            "threshold": color_threshold,
            "items": color_details,
        },
        "templates": {
            "loaded_count": len(matcher.templates),
            "items": template_details,
        },
        "ocr": ocr_details,
        "yolo": yolo_details,
        "warnings": warnings,
    }


def _calculate_weighted_confidence(
    signals: Dict[str, float],
    detection_cfg: Dict[str, Any],
    templates_loaded: bool,
    ocr_active: bool,
    yolo_active: bool = False,
) -> float:
    weights = detection_cfg.get("weights", {
        "ocr": 0.4,
        "template": 0.3,
        "color": 0.2,
        "yolo": 0.1,
    })

    active_weights = {
        "color": float(weights.get("color", 0.2)),
    }
    if templates_loaded:
        active_weights["template"] = float(weights.get("template", 0.3))
    if ocr_active:
        active_weights["ocr"] = float(weights.get("ocr", 0.4))
    if yolo_active:
        active_weights["yolo"] = float(weights.get("yolo", 0.1))

    total_weight = sum(active_weights.values())
    if total_weight == 0:
        return 0.0

    return sum(float(signals.get(name, 0.0)) * (weight / total_weight) for name, weight in active_weights.items())


def _evaluate_rules_for_test(
    frame: np.ndarray,
    image_path: str,
    detection_cfg: Dict[str, Any],
    matcher: OpenCVMatcher,
) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
    rules = detection_cfg.get("rules", []) or []
    enabled_rules = [rule for rule in rules if rule.get("enabled", True)]
    rule_results = []
    warnings = []

    for rule in enabled_rules:
        effective_cfg = _merge_detection_config(detection_cfg, rule)
        result = _evaluate_test_signals(frame, image_path, effective_cfg, matcher)
        required = rule.get("require", []) or []
        matched = bool(required) and all(result["booleans"].get(signal, False) for signal in required)
        missing = [signal for signal in required if not result["booleans"].get(signal, False)]
        if "yolo" in required:
            warnings.append(f"Rule '{rule.get('name', 'unnamed')}' requires YOLO, which is not run by this test.")

        rule_results.append({
            "name": rule.get("name", "unnamed"),
            "enabled": True,
            "require": required,
            "matched": matched,
            "missing": missing,
            "signals": result["signals"],
            "booleans": result["booleans"],
        })

    return any(item["matched"] for item in rule_results), rule_results, warnings

# --- General API ---

@api_bp.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, file.filename)
        file.save(filepath)
        
        with Image.open(filepath) as img:
            width, height = img.size
            
        return jsonify({
            "url": f"/uploads/{file.filename}",
            "path": filepath,
            "width": width,
            "height": height
        })
    return jsonify({"error": "File type not allowed"}), 400

# --- Game Management API ---

@api_bp.route("/game/list", methods=["GET"])
def list_games():
    games = config_manager.list_games()
    return jsonify({"games": games})

@api_bp.route("/games", methods=["GET"])
def list_games_legacy():
    return jsonify(config_manager.list_games())

@api_bp.route("/game/create", methods=["POST"])
def create_game():
    data = request.json
    game_name = data.get("game_name")
    try:
        game_name = validate_identifier(game_name, "game_name")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if config_manager.create_game(game_name):
        return jsonify({"message": f"Game '{game_name}' created successfully", "game": game_name})
    else:
        return jsonify({"error": f"Failed to create game '{game_name}'. It might already exist."}), 400

# --- Configuration API ---

@api_bp.route("/config/<game>", methods=["GET"])
def get_config(game):
    config = config_manager.get_config(game)
    if config:
        return jsonify(config)
    return jsonify({"error": f"Config for {game} not found"}), 404

@api_bp.route("/config/<game>/roi", methods=["PUT"])
def update_roi(game):
    data = request.json
    roi = data.get("roi") # [x, y, w, h] as relative coordinates
    rule_name = data.get("rule_name")
    
    if not isinstance(roi, list) or len(roi) != 4:
        return jsonify({"error": "Invalid ROI format. Expected [x, y, w, h]"}), 400
    
    if rule_name:
        success = config_manager.update_rule_override(game, rule_name, "killfeed_roi", roi)
    else:
        success = config_manager.update_config_section(game, "detection.killfeed_roi", roi)
        
    if success:
        # Return updated config for preview
        config = config_manager.get_config(game)
        return jsonify({"message": "ROI updated successfully", "config": config})
    return jsonify({"error": "Failed to update ROI"}), 500

@api_bp.route("/config/<game>/ocr", methods=["PUT"])
def update_ocr(game):
    data = request.json
    enabled = data.get("enabled", True)
    keywords = data.get("keywords")
    similarity = data.get("similarity_threshold", 0.8)
    rule_name = data.get("rule_name")
    
    if not isinstance(keywords, list):
        return jsonify({"error": "Keywords must be a list"}), 400
    
    if rule_name:
        s1 = config_manager.update_rule_override(game, rule_name, "ocr.enabled", enabled)
        s2 = config_manager.update_rule_override(game, rule_name, "ocr.keywords", keywords)
        s3 = config_manager.update_rule_override(game, rule_name, "ocr.similarity_threshold", similarity)
        success = s1 and s2 and s3
    else:
        s1 = config_manager.update_config_section(game, "detection.ocr.enabled", enabled)
        s2 = config_manager.update_config_section(game, "detection.ocr.keywords", keywords)
        s3 = config_manager.update_config_section(game, "detection.ocr.similarity_threshold", similarity)
        success = s1 and s2 and s3
    
    if success:
        # Return updated config for preview
        config = config_manager.get_config(game)
        return jsonify({"message": "OCR configuration updated successfully", "config": config})
    return jsonify({"error": "Failed to update OCR configuration"}), 500

@api_bp.route("/config/<game>/templates", methods=["PUT", "POST"])
def update_templates_config(game):
    data = request.json
    rule_name = data.get("rule_name")
    
    # POST: Add a single template
    if request.method == "POST":
        name = data.get("name")
        roi = data.get("roi")
        path = data.get("path")
        threshold = data.get("threshold", 0.8)
        
        if not name or not roi:
            return jsonify({"error": "name and roi are required"}), 400
        
        # Get current templates
        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404
            
        if rule_name:
            rules = config.get("detection", {}).get("rules", [])
            target_rule = next((r for r in rules if r.get("name") == rule_name), None)
            if target_rule:
                templates = target_rule.get("detection_overrides", {}).get("templates", {})
            else:
                templates = {}
        else:
            templates = config.get("detection", {}).get("templates", {})
            
        template_data = {"roi": roi, "threshold": threshold}
        if path:
            template_data["path"] = path
        templates[name] = template_data
        
        if rule_name:
            success = config_manager.update_rule_override(game, rule_name, "templates", templates)
        else:
            success = config_manager.update_config_section(game, "detection.templates", templates)
            
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": f"Template '{name}' added successfully", "config": config})
        return jsonify({"error": "Failed to add template"}), 500
    
    # PUT: Update all templates
    templates = data.get("templates")
    if not isinstance(templates, dict):
        return jsonify({"error": "Templates must be a dictionary"}), 400
        
    if rule_name:
        success = config_manager.update_rule_override(game, rule_name, "templates", templates)
    else:
        success = config_manager.update_config_section(game, "detection.templates", templates)
        
    if success:
        config = config_manager.get_config(game)
        return jsonify({"message": "Templates configuration updated successfully", "config": config})
    return jsonify({"error": "Failed to update templates configuration"}), 500


@api_bp.route("/config/<game>/templates/<name>/threshold", methods=["PATCH"])
def update_template_threshold(game, name):
    data = request.json
    threshold = data.get("threshold")
    rule_name = data.get("rule_name")
    
    if threshold is None:
        return jsonify({"error": "threshold is required"}), 400
    
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    if rule_name:
        rules = config.get("detection", {}).get("rules", [])
        target_rule = next((r for r in rules if r.get("name") == rule_name), None)
        templates = target_rule.get("detection_overrides", {}).get("templates", {}) if target_rule else {}
    else:
        templates = config.get("detection", {}).get("templates", {})
    if name not in templates:
        return jsonify({"error": f"Template '{name}' not found"}), 404
    
    templates[name]["threshold"] = threshold
    
    if rule_name:
        success = config_manager.update_rule_override(game, rule_name, "templates", templates)
    else:
        success = config_manager.update_config_section(game, "detection.templates", templates)

    if success:
        config = config_manager.get_config(game)
        return jsonify({"message": f"Template '{name}' threshold updated", "config": config})
    return jsonify({"error": "Failed to update threshold"}), 500

@api_bp.route("/config/<game>/templates/<name>", methods=["DELETE"])
def delete_template_from_config(game, name):
    rule_name = request.args.get("rule_name")
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    if rule_name:
        rules = config.get("detection", {}).get("rules", [])
        target_rule = next((r for r in rules if r.get("name") == rule_name), None)
        templates = target_rule.get("detection_overrides", {}).get("templates", {}) if target_rule else {}
    else:
        templates = config.get("detection", {}).get("templates", {})
    if name not in templates:
        return jsonify({"error": f"Template '{name}' not found"}), 404
    
    del templates[name]
    
    if rule_name:
        success = config_manager.update_rule_override(game, rule_name, "templates", templates)
    else:
        success = config_manager.update_config_section(game, "detection.templates", templates)

    if success:
        config = config_manager.get_config(game)
        return jsonify({"message": f"Template '{name}' deleted from config", "config": config})
    return jsonify({"error": "Failed to delete template"}), 500

@api_bp.route("/config/<game>/colors", methods=["PUT", "POST"])
def update_colors(game):
    data = request.json
    rule_name = data.get("rule_name")
    
    # POST: Add a single color
    if request.method == "POST":
        name = data.get("name")
        hsv = data.get("hsv")
        hsv_lower = data.get("hsv_lower")
        hsv_upper = data.get("hsv_upper")
        tolerance = data.get("tolerance", 20)
        
        if not name or hsv_lower is None or hsv_upper is None:
            return jsonify({"error": "name, hsv_lower and hsv_upper are required"}), 400
        
        # Get current colors
        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404
            
        if rule_name:
            rules = config.get("detection", {}).get("rules", [])
            target_rule = next((r for r in rules if r.get("name") == rule_name), None)
            if target_rule:
                colors = target_rule.get("detection_overrides", {}).get("colors", {})
            else:
                colors = {}
        else:
            colors = config.get("detection", {}).get("colors", {})
            
        colors[name] = {
            "hsv": hsv,
            "hsv_lower": hsv_lower,
            "hsv_upper": hsv_upper,
            "tolerance": tolerance
        }
        if hsv is None:
            colors[name].pop("hsv")
        
        if rule_name:
            success = config_manager.update_rule_override(game, rule_name, "colors", colors)
        else:
            success = config_manager.update_config_section(game, "detection.colors", colors)
            
        if success:
            config = config_manager.get_config(game)
            return jsonify({"message": f"Color '{name}' added successfully", "config": config})
        return jsonify({"error": "Failed to add color"}), 500
    
    # PUT: Update all colors
    colors = data.get("colors")
    if not isinstance(colors, dict):
        return jsonify({"error": "Colors must be a dictionary"}), 400
        
    if rule_name:
        success = config_manager.update_rule_override(game, rule_name, "colors", colors)
    else:
        success = config_manager.update_config_section(game, "detection.colors", colors)
        
    if success:
        config = config_manager.get_config(game)
        return jsonify({"message": "Colors configuration updated successfully", "config": config})
    return jsonify({"error": "Failed to update colors configuration"}), 500


@api_bp.route("/config/<game>/colors/<name>/tolerance", methods=["PATCH"])
def update_color_tolerance(game, name):
    data = request.json
    tolerance = data.get("tolerance")
    rule_name = data.get("rule_name")
    
    if tolerance is None:
        return jsonify({"error": "tolerance is required"}), 400
    
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    if rule_name:
        rules = config.get("detection", {}).get("rules", [])
        target_rule = next((r for r in rules if r.get("name") == rule_name), None)
        colors = target_rule.get("detection_overrides", {}).get("colors", {}) if target_rule else {}
    else:
        colors = config.get("detection", {}).get("colors", {})
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
    
    if rule_name:
        success = config_manager.update_rule_override(game, rule_name, "colors", colors)
    else:
        success = config_manager.update_config_section(game, "detection.colors", colors)

    if success:
        config = config_manager.get_config(game)
        return jsonify({"message": f"Color '{name}' tolerance updated", "config": config})
    return jsonify({"error": "Failed to update tolerance"}), 500

@api_bp.route("/config/<game>/colors/<name>", methods=["DELETE"])
def delete_color_from_config(game, name):
    rule_name = request.args.get("rule_name")
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    if rule_name:
        rules = config.get("detection", {}).get("rules", [])
        target_rule = next((r for r in rules if r.get("name") == rule_name), None)
        colors = target_rule.get("detection_overrides", {}).get("colors", {}) if target_rule else {}
    else:
        colors = config.get("detection", {}).get("colors", {})
    if name not in colors:
        return jsonify({"error": f"Color '{name}' not found"}), 404
    
    del colors[name]
    
    if rule_name:
        success = config_manager.update_rule_override(game, rule_name, "colors", colors)
    else:
        success = config_manager.update_config_section(game, "detection.colors", colors)

    if success:
        config = config_manager.get_config(game)
        return jsonify({"message": f"Color '{name}' deleted from config", "config": config})
    return jsonify({"error": "Failed to delete color"}), 500

@api_bp.route("/config/<game>/export", methods=["GET"])
def export_config(game):
    yaml_str = config_manager.export_config_yaml(game)
    if yaml_str:
        return jsonify({"yaml": yaml_str})
    return jsonify({"error": f"Failed to export config for {game}"}), 404


@api_bp.route("/config/<game>/test-image", methods=["POST"])
def test_config_image(game):
    """Run the current game configuration against one uploaded reference image."""
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404

    data = request.json or {}
    image_path = data.get("image_path")
    if not image_path:
        return jsonify({"error": "image_path is required"}), 400
    if not os.path.exists(image_path):
        return jsonify({"error": f"Image file not found: {image_path}"}), 404

    frame = cv2.imread(image_path)
    if frame is None:
        return jsonify({"error": "Failed to load image"}), 400

    detection_cfg = config.get("detection", {}) or {}
    matcher = OpenCVMatcher()
    matcher.load_templates_from_config(detection_cfg, PROJECT_ROOT)

    base_result = _evaluate_test_signals(frame, image_path, detection_cfg, matcher)
    warnings = list(base_result.get("warnings", []))

    prefilter_passed = True
    if detection_cfg.get("colors"):
        prefilter_passed = bool(base_result["booleans"]["color"])

    ocr_required = bool((detection_cfg.get("ocr", {}) or {}).get("required", False))
    if ocr_required and not base_result["booleans"]["ocr"]:
        prefilter_passed = False
        warnings.append("OCR is marked required but no OCR keyword matched.")

    rules = detection_cfg.get("rules", []) or []
    rule_results = []
    mode = "weighted"
    confidence = 0.0
    is_kill = False

    if not prefilter_passed:
        confidence = 0.0
        is_kill = False
    elif rules:
        mode = "rules"
        is_kill, rule_results, rule_warnings = _evaluate_rules_for_test(
            frame,
            image_path,
            detection_cfg,
            matcher,
        )
        warnings.extend(rule_warnings)
        confidence = 1.0 if is_kill else 0.0
    else:
        confidence = _calculate_weighted_confidence(
            base_result["signals"],
            detection_cfg,
            templates_loaded=base_result["templates"]["loaded_count"] > 0,
            ocr_active=bool((detection_cfg.get("ocr", {}) or {}).get("enabled", False)) and base_result["ocr"]["available"],
        )
        confidence_threshold = float(detection_cfg.get("confidence_threshold", 0.5))
        is_kill = confidence >= confidence_threshold

    response = {
        "game": game,
        "image_path": image_path,
        "status": "success" if is_kill else "failure",
        "is_kill": is_kill,
        "confidence": confidence,
        "confidence_threshold": float(detection_cfg.get("confidence_threshold", 0.5)),
        "mode": mode,
        "prefilter_passed": prefilter_passed,
        "signals": base_result["signals"],
        "booleans": base_result["booleans"],
        "details": {
            "roi": base_result["roi"],
            "color": base_result["color"],
            "templates": base_result["templates"],
            "ocr": base_result["ocr"],
            "yolo": base_result["yolo"],
            "rules": rule_results,
        },
        "warnings": warnings,
    }
    return jsonify(response)


# --- Legacy v1 Compatibility API ---

@api_bp.route("/load-config/<game>", methods=["GET"])
def load_config_legacy(game):
    config = config_manager.get_config(game)
    if config is None:
        return jsonify({"error": f"Config for {game} not found"}), 404
    return jsonify(config)


@api_bp.route("/generate-config", methods=["POST"])
def generate_config_legacy():
    data = request.json or {}
    game_name = data.get("game_name")
    try:
        game_name = validate_identifier(game_name, "game_name")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

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


@api_bp.route("/save-template", methods=["POST"])
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
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

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
    except Exception as e:
        logger.error(f"Error saving template: {e}")
        return jsonify({"error": str(e)}), 500

# --- OCR API ---

@api_bp.route("/ocr/detect", methods=["POST"])
def ocr_detect():
    data = request.json
    image_path = data.get("image_path")
    roi = data.get("roi") # [x, y, w, h] relative
    
    logger.info(f"OCR API called with image_path={image_path}, roi={roi}")
    
    if not image_path:
        logger.error("OCR API: image_path is missing")
        return jsonify({"error": "image_path is required"}), 400
    
    if not os.path.exists(image_path):
        logger.error(f"OCR API: image file not found: {image_path}")
        return jsonify({"error": f"Image file not found: {image_path}"}), 404
    
    try:
        ocr_service = get_ocr_service()
        results = ocr_service.detect(image_path, roi)
        
        # Supplement 'box' field [x, y, w, h] (0-1 relative to ROI) for frontend
        if roi and results:
            try:
                with Image.open(image_path) as img:
                    img_w, img_h = img.size
                
                rx, ry, rw, rh = roi
                roi_px = [rx * img_w, ry * img_h, rw * img_w, rh * img_h]
                
                for res in results:
                    bbox = res.get("bbox")
                    if bbox and isinstance(bbox, list) and len(bbox) >= 4:
                        # bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        xs = [p[0] for p in bbox]
                        ys = [p[1] for p in bbox]
                        min_x, max_x = min(xs), max(xs)
                        min_y, max_y = min(ys), max(ys)
                        
                        # Clamp to ROI boundaries
                        c_min_x = max(roi_px[0], min(roi_px[0] + roi_px[2], min_x))
                        c_max_x = max(roi_px[0], min(roi_px[0] + roi_px[2], max_x))
                        c_min_y = max(roi_px[1], min(roi_px[1] + roi_px[3], min_y))
                        c_max_y = max(roi_px[1], min(roi_px[1] + roi_px[3], max_y))
                        
                        # Convert to relative coordinates within ROI
                        if roi_px[2] > 0 and roi_px[3] > 0:
                            box_x = (c_min_x - roi_px[0]) / roi_px[2]
                            box_y = (c_min_y - roi_px[1]) / roi_px[3]
                            box_w = (c_max_x - c_min_x) / roi_px[2]
                            box_h = (c_max_y - c_min_y) / roi_px[3]
                            res["box"] = [float(box_x), float(box_y), float(box_w), float(box_h)]
            except Exception as e:
                logger.error(f"Error calculating relative boxes for OCR: {e}")

        logger.info(f"OCR API returning {len(results)} results")
        return jsonify({"results": results})
    except OCRUnavailableError as e:
        logger.warning(f"OCR unavailable: {e}")
        return jsonify({
            "error": "OCR unavailable",
            "detail": str(e),
            "help": "Install .venv_paddle environment or set FPSVSNAP_CONFIG_OCR_DEVICE=disabled"
        }), 503
    except Exception as e:
        logger.error(f"OCR API error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# --- Template API ---

@api_bp.route("/template/crop", methods=["POST"])
def crop_template():
    data = request.json
    image_path = data.get("image_path")
    game = data.get("game")
    name = data.get("name")
    roi = data.get("roi") # [x, y, w, h] relative (main ROI)
    sub_roi = data.get("sub_roi") # [x, y, w, h] relative (sub ROI within main ROI or absolute relative to image)
    
    if not all([image_path, game, name, sub_roi]):
        return jsonify({"error": "Missing parameters"}), 400
        
    try:
        name = validate_identifier(name, "template_name")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, f"{name}.png")
    
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            # sub_roi is relative [x, y, w, h]
            left = int(sub_roi[0] * w)
            top = int(sub_roi[1] * h)
            right = int((sub_roi[0] + sub_roi[2]) * w)
            bottom = int((sub_roi[1] + sub_roi[3]) * h)
            
            cropped = img.crop((left, top, right, bottom))
            cropped.save(target_path)
            
        rel_path = f"models/templates/{game}/{name}.png"
        return jsonify({"message": "Template cropped successfully", "path": rel_path})
    except Exception as e:
        logger.error(f"Error cropping template: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/template/<game>/list", methods=["GET"])
def list_templates(game):
    target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
    if not os.path.exists(target_dir):
        return jsonify([])
        
    templates = []
    for filename in os.listdir(target_dir):
        if filename.endswith((".png", ".jpg", ".jpeg")):
            templates.append({
                "name": os.path.splitext(filename)[0],
                "filename": filename,
                "url": f"/api/template/{game}/view/{filename}"
            })
    return jsonify(templates)

@api_bp.route("/template/<game>/view/<filename>", methods=["GET"])
def view_template(game, filename):
    target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
    return send_from_directory(target_dir, filename)

@api_bp.route("/template/<game>/<name>", methods=["DELETE"])
def delete_template(game, name):
    target_dir = os.path.join(PROJECT_ROOT, "models", "templates", game)
    # Try different extensions
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

# --- Color API ---

@api_bp.route("/pick-color", methods=["POST"])
@api_bp.route("/color/pick", methods=["POST"])
def pick_color():
    data = request.json
    image_path = data.get("image_path")
    x_value = data.get("x") # relative 0-1, or legacy absolute pixel coordinate
    y_value = data.get("y") # relative 0-1, or legacy absolute pixel coordinate
    tolerance = data.get("tolerance", [10, 50, 50])
    
    if image_path is None or x_value is None or y_value is None:
        return jsonify({"error": "Missing parameters"}), 400
        
    if not os.path.exists(image_path):
        return jsonify({"error": "Image not found"}), 404
        
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            if 0 <= x_value <= 1 and 0 <= y_value <= 1:
                x = int(x_value * w)
                y = int(y_value * h)
            else:
                x = int(x_value)
                y = int(y_value)
            # Ensure within bounds
            x = max(0, min(w - 1, x))
            y = max(0, min(h - 1, y))
            
            rgb = img.convert("RGB").getpixel((x, y))
            r, g, b = rgb
            
        h_val, s_val, v_val = rgb_to_hsv(r, g, b)
        lower, upper = calculate_hsv_range(h_val, s_val, v_val, tuple(tolerance))
        
        return jsonify({
            "rgb": [r, g, b],
            "hsv": [h_val, s_val, v_val],
            "hsv_range": {
                "lower": lower,
                "upper": upper
            }
        })
    except Exception as e:
        logger.error(f"Error picking color: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/color/preview", methods=["POST"])
def preview_color():
    data = request.json
    image_path = data.get("image_path")
    roi = data.get("roi") # [x, y, w, h] relative
    lower = data.get("lower") # [h, s, v]
    upper = data.get("upper") # [h, s, v]
    
    if not all([image_path, lower, upper]):
        return jsonify({"error": "Missing parameters"}), 400
        
    try:
        image = cv2.imread(image_path)
        if image is None:
            return jsonify({"error": "Failed to load image"}), 400
            
        h_img, w_img = image.shape[:2]
        if roi:
            rx, ry, rw, rh = roi
            x1, y1 = int(rx * w_img), int(ry * h_img)
            x2, y2 = int((rx + rw) * w_img), int((ry + rh) * h_img)
            region = image[y1:y2, x1:x2]
        else:
            region = image
            
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        
        # Encode mask as PNG and return as blob
        _, buffer = cv2.imencode('.png', mask)
        return buffer.tobytes(), 200, {'Content-Type': 'image/png'}
    except Exception as e:
        logger.error(f"Error previewing color: {e}")
        return jsonify({"error": str(e)}), 500


# --- Rules API ---

VALID_SIGNALS = {"ocr", "template", "color", "yolo"}


def _validate_rules(rules):
    """Validate rules structure. Raises ValueError with descriptive message on failure."""
    if not isinstance(rules, list):
        raise ValueError("detection.rules must be a list")
    
    seen_names = set()
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"detection.rules[{i}] must be a dict")
        
        # Check required fields
        if "name" not in rule:
            raise ValueError(f"detection.rules[{i}].name is required")
        if "enabled" not in rule:
            raise ValueError(f"detection.rules[{i}].enabled is required")
        if "require" not in rule:
            raise ValueError(f"detection.rules[{i}].require is required")
        
        name = rule["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"detection.rules[{i}].name must be a non-empty string")
        
        if not isinstance(rule["enabled"], bool):
            raise ValueError(f"detection.rules[{i}].enabled must be a boolean")
        
        require = rule["require"]
        if not isinstance(require, list):
            raise ValueError(f"detection.rules[{i}].require must be a list")
        if len(require) == 0:
            raise ValueError(f"detection.rules[{i}].require cannot be empty")
        
        for j, signal in enumerate(require):
            if not isinstance(signal, str):
                raise ValueError(f"detection.rules[{i}].require[{j}] must be a string")
            if signal not in VALID_SIGNALS:
                raise ValueError(f"detection.rules[{i}].require[{j}]: unknown signal '{signal}'. Valid: {VALID_SIGNALS}")
        
        # Check for duplicate names
        if name in seen_names:
            raise ValueError(f"detection.rules[{i}].name: duplicate name '{name}'")
        seen_names.add(name)

        # Validate detection_overrides if present
        if "detection_overrides" in rule:
            overrides = rule["detection_overrides"]
            if not isinstance(overrides, dict):
                raise ValueError(f"detection.rules[{i}].detection_overrides must be a dict")
            
            # ROI validation
            if "killfeed_roi" in overrides:
                roi = overrides["killfeed_roi"]
                if not isinstance(roi, list) or len(roi) != 4:
                    raise ValueError(f"detection.rules[{i}].detection_overrides.killfeed_roi must be a list of 4 numbers")
            
            # OCR validation
            if "ocr" in overrides:
                ocr = overrides["ocr"]
                if not isinstance(ocr, dict):
                    raise ValueError(f"detection.rules[{i}].detection_overrides.ocr must be a dict")
                if "keywords" in ocr and not isinstance(ocr["keywords"], list):
                    raise ValueError(f"detection.rules[{i}].detection_overrides.ocr.keywords must be a list")
                if "similarity_threshold" in ocr and not isinstance(ocr["similarity_threshold"], (int, float)):
                    raise ValueError(f"detection.rules[{i}].detection_overrides.ocr.similarity_threshold must be a number")
                if "similarity_threshold" in ocr and not (0 <= ocr["similarity_threshold"] <= 1):
                    raise ValueError(f"detection.rules[{i}].detection_overrides.ocr.similarity_threshold must be 0-1")
            
            # Templates validation
            if "templates" in overrides:
                if not isinstance(overrides["templates"], dict):
                    raise ValueError(f"detection.rules[{i}].detection_overrides.templates must be a dict")
            
            # Colors validation
            if "colors" in overrides:
                colors = overrides["colors"]
                if not isinstance(colors, dict):
                    raise ValueError(f"detection.rules[{i}].detection_overrides.colors must be a dict")
                for cname, cdata in colors.items():
                    if not isinstance(cdata, dict):
                        raise ValueError(f"detection.rules[{i}].detection_overrides.colors.{cname} must be a dict")
                    if "hsv_lower" not in cdata or "hsv_upper" not in cdata:
                        raise ValueError(f"detection.rules[{i}].detection_overrides.colors.{cname} must have hsv_lower and hsv_upper")


@api_bp.route("/config/<game>/rules", methods=["GET"])
def get_rules(game):
    """Get detection rules for a game."""
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    rules = config.get("detection", {}).get("rules", [])
    return jsonify({"rules": rules})


@api_bp.route("/config/<game>/rules", methods=["PUT"])
def update_rules(game):
    """Update detection rules for a game."""
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    data = request.json
    rules = data.get("rules")
    
    if rules is None:
        return jsonify({"error": "'rules' field is required"}), 400
    
    try:
        _validate_rules(rules)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    if config_manager.update_config_section(game, "detection.rules", rules):
        config = config_manager.get_config(game)
        return jsonify({"message": "Rules updated", "config": config})
    return jsonify({"error": "Failed to update rules"}), 500
