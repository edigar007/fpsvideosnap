"""
Flask server for the Dashboard web interface.
"""
import os
import socket
import threading
import time
import webbrowser
from flask import Flask, send_from_directory
from src.tools.dashboard.api import api_bp
from src.utils.logger import get_logger, setup_logger

logger = get_logger("dashboard.server")


def create_app():
    """Create and configure the Flask application."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    static_folder = os.path.join(base_dir, "static")
    
    app = Flask(__name__, static_folder=static_folder)
    
    # Register API blueprint
    app.register_blueprint(api_bp, url_prefix="/api")
    
    # Serve static files
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")
    
    @app.route("/css/<path:filename>")
    def css(filename):
        return send_from_directory(os.path.join(app.static_folder, "css"), filename)
    
    @app.route("/js/<path:filename>")
    def js(filename):
        return send_from_directory(os.path.join(app.static_folder, "js"), filename)
    
    return app


def _find_available_port(start_port: int, attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No available port found starting from {start_port}")


def run_server(port: int = 8081, debug: bool = False):
    """
    Start the Dashboard server and open the browser.
    
    Args:
        port: Port to run the server on (default: 8081)
        debug: Enable Flask debug mode
    """
    app = create_app()
    
    try:
        chosen_port = _find_available_port(port)
    except RuntimeError as exc:
        logger.error(str(exc))
        return
    
    url = f"http://127.0.0.1:{chosen_port}"
    
    def open_browser():
        # Wait for server to start
        time.sleep(1.5)
        logger.info(f"Opening browser at {url}")
        webbrowser.open(url)
    
    # Launch browser in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    logger.info(f"[bold blue]Starting Dashboard Server on {url}[/bold blue]")
    logger.info("Press [bold red]Ctrl+C[/bold red] to stop the server")
    
    try:
        # Use threaded mode for SSE support
        app.run(
            host="127.0.0.1",
            port=chosen_port,
            debug=debug,
            use_reloader=False,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")


if __name__ == "__main__":
    setup_logger(debug=True)
    run_server(port=8081, debug=True)
