import os

from flask import current_app, jsonify, request
from PIL import Image

from src.tools.config_assistant.utils import safe_join, sanitize_filename

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def register_routes(bp) -> None:
    @bp.route("/upload", methods=["POST"])
    def upload_file():
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400
        try:
            safe_name = sanitize_filename(file.filename)
            if not allowed_file(safe_name):
                return jsonify({"error": "File type not allowed"}), 400

            upload_folder = current_app.config["UPLOAD_FOLDER"]
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)

            filepath = safe_join(upload_folder, safe_name)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        file.save(filepath)

        with Image.open(filepath) as img:
            width, height = img.size

        return jsonify(
            {
                "url": f"/uploads/{safe_name}",
                "filename": safe_name,
                "path": filepath,
                "width": width,
                "height": height,
            }
        )

