import os
import webbrowser
import threading
import time
import shutil
import socket
from flask import Flask, send_from_directory
from src.tools.config_assistant.api import api_bp
from src.utils.logger import get_logger, setup_logger

logger = get_logger("config_assistant.server")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    static_folder = os.path.join(base_dir, "static")
    
    app = Flask(__name__, static_folder=static_folder)
    
    # Configuration
    # We use absolute path for upload folder to be safe
    project_root = os.path.abspath(os.path.join(base_dir, "..", "..", ".."))
    upload_folder = os.path.join(project_root, "temp", "uploads")
    
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
    
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    # Route to serve uploads
    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/')
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app

def _find_available_port(start_port: int, attempts: int = 10) -> int:
    for port in range(start_port, start_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No available port found starting from {start_port}")

def _cleanup_uploads(upload_folder: str):
    if not upload_folder or not os.path.exists(upload_folder):
        return
    for entry in os.listdir(upload_folder):
        path = os.path.join(upload_folder, entry)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                os.remove(path)
            except OSError:
                continue

def run_server(port=8080, debug=False):
    """Start the Config Assistant server and open the browser."""
    # Ensure cleanup before starting
    app = create_app()
    upload_folder = app.config.get('UPLOAD_FOLDER')
    _cleanup_uploads(upload_folder)

    # OCR remains lazy for API correctness, but pre-warm only for real server runs.
    # create_app() is used by tests and should not spawn heavyweight workers.
    def init_ocr():
        try:
            logger.info("Pre-loading OCR models...")
            from src.tools.config_assistant.ocr_service import get_ocr_service
            service = get_ocr_service()
            service._ensure_initialized()
            if service._detector is not None:
                logger.info("OCR models loaded successfully.")
            else:
                logger.warning(f"OCR unavailable: {service._init_error or 'Unknown error'}")
        except Exception as e:
            logger.warning(f"OCR pre-loading failed (non-fatal): {e}")

    threading.Thread(target=init_ocr, daemon=True).start()

    try:
        chosen_port = _find_available_port(port)
    except RuntimeError as exc:
        logger.error(str(exc))
        return

    url = f"http://127.0.0.1:{chosen_port}"

    def open_browser():
        # Wait a bit for the server to start
        time.sleep(1.5)
        logger.info(f"Opening browser at {url}")
        webbrowser.open(url)

    # Launch browser in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()

    logger.info(f"Starting Config Assistant Server on {url}")
    logger.info("Press [bold red]Ctrl+C[/bold red] to stop the server (Uploads will be cleaned up)")

    try:
        app.run(host="127.0.0.1", port=chosen_port, debug=debug, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        logger.info("Cleaning up temporary uploads...")
        _cleanup_uploads(upload_folder)
        logger.info("Exit successful.")

if __name__ == "__main__":
    setup_logger(debug=True)
    run_server(port=5000, debug=True)
