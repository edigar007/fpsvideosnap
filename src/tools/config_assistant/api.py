import os
import shutil
import yaml
from flask import Blueprint, request, jsonify, current_app
from PIL import Image
from src.tools.config_assistant.utils import (
    rgb_to_hsv,
    calculate_hsv_range,
    sanitize_filename,
    validate_identifier,
    safe_join,
)
from src.utils.logger import get_logger

logger = get_logger("config_assistant.api")
api_bp = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TEMPLATE_ROOT = os.path.join(PROJECT_ROOT, "models", "templates")
CONFIG_GAMES_DIR = os.path.join(PROJECT_ROOT, "config", "games")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@api_bp.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        try:
            safe_name = sanitize_filename(file.filename)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if not allowed_file(safe_name):
            return jsonify({"error": "File type not allowed"}), 400

        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        try:
            filepath = safe_join(upload_folder, safe_name)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        file.save(filepath)
        
        with Image.open(filepath) as img:
            width, height = img.size
            
        return jsonify({
            "url": f"/uploads/{safe_name}",
            "path": filepath,
            "width": width,
            "height": height
        })
    return jsonify({"error": "File type not allowed"}), 400

@api_bp.route("/pick-color", methods=["POST"])
def pick_color():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    image_path = data.get("image_path")
    x = data.get("x")
    y = data.get("y")
    
    if image_path is None or x is None or y is None:
        return jsonify({"error": "Missing parameters"}), 400
    
    if not os.path.exists(image_path):
        return jsonify({"error": "Image not found at " + str(image_path)}), 404
        
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            try:
                x_int = int(x)
                y_int = int(y)
            except (TypeError, ValueError):
                return jsonify({"error": "Pixel coordinates must be integers"}), 400

            if not (0 <= x_int < width and 0 <= y_int < height):
                return jsonify({"error": "Pixel coordinates out of bounds"}), 400

            rgb = img.convert("RGB").getpixel((x_int, y_int))
            r, g, b = rgb
            
        h, s, v = rgb_to_hsv(r, g, b)
        lower, upper = calculate_hsv_range(h, s, v)
        
        return jsonify({
            "rgb": [r, g, b],
            "hsv": [h, s, v],
            "hsv_range": {
                "lower": lower,
                "upper": upper
            }
        })
    except Exception as e:
        logger.error(f"Error picking color: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/save-template", methods=["POST"])
def save_template():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    image_path = data.get("image_path")
    game_name = data.get("game_name")
    template_name = data.get("template_name")
    roi = data.get("roi") # {x, y, w, h} in pixels
    
    if not all([image_path, game_name, template_name]):
        return jsonify({"error": "Missing parameters"}), 400

    try:
        safe_game = validate_identifier(game_name, "game_name")
        safe_template = validate_identifier(template_name, "template_name")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    target_dir = safe_join(TEMPLATE_ROOT, safe_game)
    os.makedirs(target_dir, exist_ok=True)
    target_path = safe_join(target_dir, f"{safe_template}.png")
    try:
        if roi:
            try:
                left = int(roi['x'])
                top = int(roi['y'])
                width = int(roi['w'])
                height = int(roi['h'])
            except (KeyError, TypeError, ValueError):
                return jsonify({"error": "Invalid ROI payload"}), 400

            if width <= 0 or height <= 0:
                return jsonify({"error": "ROI width/height must be positive"}), 400

            with Image.open(image_path) as img:
                img_width, img_height = img.size
                left = max(0, min(left, img_width))
                top = max(0, min(top, img_height))
                right = max(left, min(left + width, img_width))
                bottom = max(top, min(top + height, img_height))
                if right == left or bottom == top:
                    return jsonify({"error": "ROI is outside of image bounds"}), 400
                cropped = img.crop((left, top, right, bottom))
                cropped.save(target_path)
        else:
            shutil.copy(image_path, target_path)
        return jsonify({"message": f"Template saved to {target_path}", "path": target_path})
    except Exception as e:
        logger.error(f"Error saving template: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/games", methods=["GET"])
def list_games():
    games_dir = CONFIG_GAMES_DIR
    if not os.path.exists(games_dir):
        return jsonify([])
    
    games = []
    for f in os.listdir(games_dir):
        if f.endswith(".yaml"):
            games.append(f.replace(".yaml", ""))
    return jsonify(games)

@api_bp.route("/generate-config", methods=["POST"])
def generate_config():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    raw_game = data.get("game_name") or "unknown"
    try:
        game_name = validate_identifier(raw_game, "game_name")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    rois = data.get("rois", [])
    colors = data.get("colors", [])
    
    # Transform colors to dictionary structure
    color_dict = {}
    for c in colors:
        name = c.get("name", "color").replace(" ", "_").lower()
        color_dict[name] = {
            "lower": c.get("lower"),
            "upper": c.get("upper")
        }

    config_dict = {
        "game_name": game_name,
        "detection": {
            "colors": color_dict,
            "template_dir": f"models/templates/{game_name}"
        },
        "highlights": {
            "pre_kill_time": 5.0,
            "post_kill_time": 1.5
        }
    }

    # Map ROIs - if one is named killfeed_roi, use it specifically
    for r in rois:
        try:
            name = r.get("name", "roi").replace(" ", "_").lower()
            key = f"{name}_roi" if not name.endswith("_roi") else name
            config_dict["detection"][key] = [
                round(float(r['x']), 4),
                round(float(r['y']), 4),
                round(float(r['w']), 4),
                round(float(r['h']), 4)
            ]
        except (KeyError, ValueError, TypeError):
            return jsonify({"error": "Invalid ROI data"}), 400

    class FlowDumper(yaml.SafeDumper):
        pass

    def list_representer(dumper, data):
        return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

    FlowDumper.add_representer(list, list_representer)
    yaml_str = yaml.dump(config_dict, sort_keys=False, allow_unicode=True, Dumper=FlowDumper)
    return jsonify({"yaml": yaml_str})

@api_bp.route("/save-config", methods=["POST"])
def save_config_file():
    data = request.json
    if not data or 'yaml' not in data or 'game_name' not in data:
        return jsonify({"error": "Missing data"}), 400
    
    try:
        game_name = validate_identifier(data['game_name'], "game_name")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    yaml_content = data['yaml']
    
    config_dir = CONFIG_GAMES_DIR
    os.makedirs(config_dir, exist_ok=True)
    try:
        file_path = safe_join(config_dir, f"{game_name}.yaml")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        return jsonify({"message": f"Config saved to {file_path}", "path": file_path})
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/load-config/<game_name>", methods=["GET"])
def load_config(game_name):
    # Try looking in config/games/{game_name}.yaml
    try:
        safe_game = validate_identifier(game_name, "game_name")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    config_path = safe_join(CONFIG_GAMES_DIR, f"{safe_game}.yaml")
    if not os.path.exists(config_path):
        return jsonify({"error": f"Config for {game_name} not found"}), 404
        
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        return jsonify(config_data)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return jsonify({"error": str(e)}), 500
