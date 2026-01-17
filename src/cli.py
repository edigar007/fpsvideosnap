import argparse
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="FPS Video Snap - AI-powered Kill Highlight Generator")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: run (default behavior)
    run_parser = subparsers.add_parser("run", help="Generate highlights from a video")
    run_parser.add_argument(
        "--video", 
        type=str, 
        nargs='+',
        required=True, 
        help="Path(s) to input gameplay video(s). Multiple files will be merged into one highlight."
    )
    
    run_parser.add_argument(
        "--game", 
        type=str, 
        default="battlefield6", 
        help="Select game-specific config (e.g., battlefield6)"
    )
    
    run_parser.add_argument(
        "--config", 
        type=str, 
        help="Optional path to an override YAML config file"
    )
    
    run_parser.add_argument(
        "--output", 
        type=str, 
        help="Output directory (overrides config)"
    )
    
    run_parser.add_argument(
        "--music", 
        type=str, 
        help="Path to background music file"
    )
    
    run_parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    
    run_parser.add_argument(
        "--debug-visual", 
        action="store_true", 
        help="Generate a debug video with detection overlays"
    )

    # Command: config-assistant
    config_parser = subparsers.add_parser("config-assistant", help="Start the web-based configuration assistant tool")
    config_parser.add_argument(
        "--port", 
        type=int, 
        default=8080, 
        help="Port to run the assistant tool on (default: 8080)"
    )
    config_parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug mode for the Flask server"
    )

    # Default to 'run' if no command is provided and we have arguments
    # This maintains backward compatibility for `python main.py --video ...`
    if len(sys.argv) > 1 and sys.argv[1] not in ["run", "config-assistant", "-h", "--help"]:
        sys.argv.insert(1, "run")
    
    # If no arguments at all, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()
