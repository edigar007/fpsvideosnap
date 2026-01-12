import os
import shutil
import cv2
import numpy as np
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from PIL import Image
from src.tools.config_assistant.utils import rgb_to_hsv, calculate_hsv_range, validate_identifier
from src.tools.config_assistant.ocr_service import ocr_service
from src.tools.config_assistant.config_manager import config_manager, PROJECT_ROOT # Imported PROJECT_ROOT
from src.utils.logger import get_logger

logger = get_logger("config_assistant.api")
api_bp = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    if not isinstance(roi, list) or len(roi) != 4:
        return jsonify({"error": "Invalid ROI format. Expected [x, y, w, h]"}), 400
    
    if config_manager.update_config_section(game, "detection.killfeed_roi", roi):
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
    
    if not isinstance(keywords, list):
        return jsonify({"error": "Keywords must be a list"}), 400
        
    config_manager.update_config_section(game, "detection.ocr.enabled", enabled)
    config_manager.update_config_section(game, "detection.ocr.keywords", keywords)
    config_manager.update_config_section(game, "detection.ocr.similarity_threshold", similarity)
    
    # Return updated config for preview
    config = config_manager.get_config(game)
    return jsonify({"message": "OCR configuration updated successfully", "config": config})

@api_bp.route("/config/<game>/templates", methods=["PUT", "POST"])
def update_templates_config(game):
    data = request.json
    
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
            
        templates = config.get("detection", {}).get("templates", {})
        template_data = {"roi": roi, "threshold": threshold}
        if path:
            template_data["path"] = path
        templates[name] = template_data
        
        if config_manager.update_config_section(game, "detection.templates", templates):
            config = config_manager.get_config(game)
            return jsonify({"message": f"Template '{name}' added successfully", "config": config})
        return jsonify({"error": "Failed to add template"}), 500
    
    # PUT: Update all templates
    templates = data.get("templates")
    if not isinstance(templates, dict):
        return jsonify({"error": "Templates must be a dictionary"}), 400
        
    if config_manager.update_config_section(game, "detection.templates", templates):
        config = config_manager.get_config(game)
        return jsonify({"message": "Templates configuration updated successfully", "config": config})
    return jsonify({"error": "Failed to update templates configuration"}), 500

@api_bp.route("/config/<game>/templates/<name>/threshold", methods=["PATCH"])
def update_template_threshold(game, name):
    data = request.json
    threshold = data.get("threshold")
    
    if threshold is None:
        return jsonify({"error": "threshold is required"}), 400
    
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    templates = config.get("detection", {}).get("templates", {})
    if name not in templates:
        return jsonify({"error": f"Template '{name}' not found"}), 404
    
    templates[name]["threshold"] = threshold
    
    if config_manager.update_config_section(game, "detection.templates", templates):
        config = config_manager.get_config(game)
        return jsonify({"message": f"Template '{name}' threshold updated", "config": config})
    return jsonify({"error": "Failed to update threshold"}), 500

@api_bp.route("/config/<game>/templates/<name>", methods=["DELETE"])
def delete_template_from_config(game, name):
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    templates = config.get("detection", {}).get("templates", {})
    if name not in templates:
        return jsonify({"error": f"Template '{name}' not found"}), 404
    
    del templates[name]
    
    if config_manager.update_config_section(game, "detection.templates", templates):
        config = config_manager.get_config(game)
        return jsonify({"message": f"Template '{name}' deleted from config", "config": config})
    return jsonify({"error": "Failed to delete template"}), 500

@api_bp.route("/config/<game>/colors", methods=["PUT", "POST"])
def update_colors(game):
    data = request.json
    
    # POST: Add a single color
    if request.method == "POST":
        name = data.get("name")
        hsv_lower = data.get("hsv_lower")
        hsv_upper = data.get("hsv_upper")
        tolerance = data.get("tolerance", 20)
        
        if not name or hsv_lower is None or hsv_upper is None:
            return jsonify({"error": "name, hsv_lower and hsv_upper are required"}), 400
        
        # Get current colors
        config = config_manager.get_config(game)
        if not config:
            return jsonify({"error": f"Config for {game} not found"}), 404
            
        colors = config.get("detection", {}).get("colors", {})
        colors[name] = {
            "hsv_lower": hsv_lower,
            "hsv_upper": hsv_upper,
            "tolerance": tolerance
        }
        
        if config_manager.update_config_section(game, "detection.colors", colors):
            config = config_manager.get_config(game)
            return jsonify({"message": f"Color '{name}' added successfully", "config": config})
        return jsonify({"error": "Failed to add color"}), 500
    
    # PUT: Update all colors
    colors = data.get("colors")
    if not isinstance(colors, dict):
        return jsonify({"error": "Colors must be a dictionary"}), 400
        
    if config_manager.update_config_section(game, "detection.colors", colors):
        config = config_manager.get_config(game)
        return jsonify({"message": "Colors configuration updated successfully", "config": config})
    return jsonify({"error": "Failed to update colors configuration"}), 500

@api_bp.route("/config/<game>/colors/<name>/tolerance", methods=["PATCH"])
def update_color_tolerance(game, name):
    data = request.json
    tolerance = data.get("tolerance")
    
    if tolerance is None:
        return jsonify({"error": "tolerance is required"}), 400
    
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    colors = config.get("detection", {}).get("colors", {})
    if name not in colors:
        return jsonify({"error": f"Color '{name}' not found"}), 404
    
    # Recalculate hsv_lower and hsv_upper based on new tolerance
    color = colors[name]
    # Assuming we have the original HSV value stored, or we use the midpoint
    # For simplicity, let's just update the tolerance value
    color["tolerance"] = tolerance
    
    if config_manager.update_config_section(game, "detection.colors", colors):
        config = config_manager.get_config(game)
        return jsonify({"message": f"Color '{name}' tolerance updated", "config": config})
    return jsonify({"error": "Failed to update tolerance"}), 500

@api_bp.route("/config/<game>/colors/<name>", methods=["DELETE"])
def delete_color_from_config(game, name):
    config = config_manager.get_config(game)
    if not config:
        return jsonify({"error": f"Config for {game} not found"}), 404
    
    colors = config.get("detection", {}).get("colors", {})
    if name not in colors:
        return jsonify({"error": f"Color '{name}' not found"}), 404
    
    del colors[name]
    
    if config_manager.update_config_section(game, "detection.colors", colors):
        config = config_manager.get_config(game)
        return jsonify({"message": f"Color '{name}' deleted from config", "config": config})
    return jsonify({"error": "Failed to delete color"}), 500

@api_bp.route("/config/<game>/export", methods=["GET"])
def export_config(game):
    yaml_str = config_manager.export_config_yaml(game)
    if yaml_str:
        return jsonify({"yaml": yaml_str})
    return jsonify({"error": f"Failed to export config for {game}"}), 404

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
        results = ocr_service.detect(image_path, roi)
        logger.info(f"OCR API returning {len(results)} results")
        return jsonify({"results": results})
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

@api_bp.route("/color/pick", methods=["POST"])
def pick_color():
    data = request.json
    image_path = data.get("image_path")
    x_rel = data.get("x") # relative 0-1
    y_rel = data.get("y") # relative 0-1
    tolerance = data.get("tolerance", [10, 50, 50])
    
    if image_path is None or x_rel is None or y_rel is None:
        return jsonify({"error": "Missing parameters"}), 400
        
    if not os.path.exists(image_path):
        return jsonify({"error": "Image not found"}), 404
        
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            x = int(x_rel * w)
            y = int(y_rel * h)
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
