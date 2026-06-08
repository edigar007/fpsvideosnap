"""
Flask API endpoints for the Dashboard.
"""
import os
from flask import Blueprint, request, jsonify
from src.tools.dashboard.task_manager import task_manager
from src.utils.logger import get_logger

logger = get_logger("dashboard.api")
api_bp = Blueprint("dashboard_api", __name__)

# Video file extensions to scan
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}

# --- Game API ---

@api_bp.route("/games", methods=["GET"])
def list_games():
    """List available game configurations."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(base_dir, "..", "..", ".."))
        games_dir = os.path.join(project_root, "config", "games")
        
        games = []
        if os.path.exists(games_dir):
            for filename in os.listdir(games_dir):
                if filename.endswith(".yaml") or filename.endswith(".yml"):
                    game_name = os.path.splitext(filename)[0]
                    games.append(game_name)
        
        return jsonify({"games": sorted(games)})
    except Exception as e:
        logger.error(f"Error listing games: {e}")
        return jsonify({"error": str(e)}), 500


# --- Directory Scan API ---

@api_bp.route("/scan", methods=["POST"])
def scan_directory():
    """Scan a directory for video files."""
    data = request.json or {}
    directory = data.get("directory", "").strip()
    
    if not directory:
        return jsonify({"error": "Directory path is required"}), 400
    
    if not os.path.exists(directory):
        return jsonify({"error": f"Directory not found: {directory}"}), 404
    
    if not os.path.isdir(directory):
        return jsonify({"error": f"Path is not a directory: {directory}"}), 400
    
    try:
        videos = []
        for filename in os.listdir(directory):
            ext = os.path.splitext(filename)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                filepath = os.path.join(directory, filename)
                try:
                    size = os.path.getsize(filepath)
                    videos.append({
                        "path": filepath,
                        "name": filename,
                        "size": size,
                        "size_formatted": _format_size(size)
                    })
                except OSError:
                    continue
        
        videos.sort(key=lambda v: v["name"].lower())
        
        return jsonify({
            "directory": directory,
            "videos": videos,
            "count": len(videos)
        })
    except Exception as e:
        logger.error(f"Error scanning directory: {e}")
        return jsonify({"error": str(e)}), 500


def _format_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# --- Task API ---

@api_bp.route("/task/start", methods=["POST"])
def start_task():
    """Start a video processing task."""
    data = request.json or {}
    videos = data.get("videos", [])
    game = data.get("game", "battlefield6")
    
    if not videos:
        return jsonify({"error": "No videos provided"}), 400
    
    if not isinstance(videos, list):
        videos = [videos]
    
    result = task_manager.start_task(videos, game)
    
    if result.get("success"):
        return jsonify(result)
    else:
        return jsonify(result), 400


@api_bp.route("/task/status", methods=["GET"])
def get_task_status():
    """Get current task status with progress information."""
    status = task_manager.get_status()
    return jsonify(status)


@api_bp.route("/task/cancel", methods=["POST"])
def cancel_task():
    """Cancel the current running task."""
    result = task_manager.cancel_task()
    
    if result.get("success"):
        return jsonify(result)
    else:
        return jsonify(result), 400


@api_bp.route("/task/clear", methods=["POST"])
def clear_task():
    """Clear task state to start fresh."""
    task_manager.clear()
    return jsonify({"success": True, "message": "Task cleared"})


@api_bp.route("/task/errors", methods=["GET"])
def get_errors():
    """
    Get error/warning logs.
    
    Query params:
    - since: error index to start from (default: 0)
    """
    since = int(request.args.get("since", 0))
    errors = task_manager.get_errors(since)
    status = task_manager.get_status()
    
    return jsonify({
        "errors": errors,
        "next_index": since + len(errors),
        "status": status["status"]
    })
