import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="FPS Video Snap - AI-powered Kill Highlight Generator")
    
    parser.add_argument(
        "--video", 
        type=str, 
        required=True, 
        help="Path to the input gameplay video"
    )
    
    parser.add_argument(
        "--game", 
        type=str, 
        default="battlefield6", 
        help="Select game-specific config (e.g., battlefield6)"
    )
    
    parser.add_argument(
        "--config", 
        type=str, 
        help="Optional path to an override YAML config file"
    )
    
    parser.add_argument(
        "--output", 
        type=str, 
        help="Output directory (overrides config)"
    )
    
    parser.add_argument(
        "--music", 
        type=str, 
        help="Path to background music file"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging and visualization"
    )
    
    return parser.parse_args()
