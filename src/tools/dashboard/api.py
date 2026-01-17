"""
Flask API endpoints for the Dashboard.
"""
import os
import json
import time
from flask import Blueprint, request, jsonify, Response
from src.tools.dashboard.task_manager import task_manager, TaskStatus
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
        # Get project root
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
    """
    Scan a directory for video files.
    
    Request body:
    {
        "directory": "D:\\videos\\gameplay"
    }
    
    Response:
    {
        "videos": [
            {"path": "...", "name": "...", "size": 1234567, "size_formatted": "1.2 GB"}
        ]
    }
    """
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
        
        # Sort by name
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
    """
    Start a video processing task.
    
    Request body:
    {
        "videos": ["D:\\video1.mp4", "D:\\video2.mp4"],
        "game": "battlefield6"
    }
    """
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
    """Get current task status."""
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


@api_bp.route("/task/logs", methods=["GET"])
def get_logs_sse():
    """
    Server-Sent Events endpoint for log streaming.
    
    Query params:
    - poll: if "true", use polling mode instead of SSE (returns JSON array)
    - since: log index to start from (for polling)
    """
    poll_mode = request.args.get("poll", "false").lower() == "true"
    
    if poll_mode:
        # Polling mode: return logs as JSON
        since = int(request.args.get("since", 0))
        logs = task_manager.get_logs(since)
        status = task_manager.get_status()
        return jsonify({
            "logs": logs,
            "next_index": since + len(logs),
            "status": status["status"]
        })
    
    # SSE mode
    def generate():
        last_index = 0
        
        while True:
            # Get new logs
            logs = task_manager.get_logs(last_index)
            
            for log in logs:
                data = json.dumps(log)
                yield f"data: {data}\n\n"
                last_index += 1
            
            # Check if task is still running
            status = task_manager.get_status()
            if status["status"] not in (TaskStatus.RUNNING.value, "running"):
                # Send final status event
                yield f"event: done\ndata: {json.dumps(status)}\n\n"
                break
            
            time.sleep(0.2)
    
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
