import sys
import os

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.cli import parse_args
from src.config.config_loader import get_config
from src.utils.logger import setup_logger

def main():
    # 1. Parse CLI arguments
    args = parse_args()
    
    # 2. Setup Logging
    logger = setup_logger(debug=args.debug)
    logger.info("[bold blue]Starting FPS Video Snap...[/bold blue]")
    
    # 3. Load Configuration
    try:
        config = get_config(game_name=args.game, override_path=args.config)
        logger.info(f"Loaded config for game: [yellow]{args.game}[/yellow]")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return
    
    # Override config with CLI arguments if provided
    if args.output:
        config['global']['output_dir'] = args.output
    if args.music:
        config['highlights']['music_path'] = args.music
    if args.debug:
        config['global']['debug'] = True
        
    logger.debug(f"Final Configuration: {config}")
    
    # 4. Process Video(s)
    from src.pipeline.batch_processor import BatchProcessor
    
    try:
        processor = BatchProcessor(config)
        results = processor.process(args.video)
        
        # Final Summary
        success_count = sum(1 for r in results if r['success'])
        logger.info(f"\n[bold green]Batch processing finished![/bold green]")
        logger.info(f"Successfully processed: [green]{success_count}/{len(results)}[/green]")
        
    except Exception as e:
        logger.exception(f"An unexpected error occurred during processing: {e}")

if __name__ == "__main__":
    main()
