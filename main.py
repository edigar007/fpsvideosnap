import sys
import os

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.utils.cuda_dll import setup_cuda_dll_directories

# Windows GPU 支持：在所有导入之前添加 CUDA DLL 目录
if sys.platform == "win32":
    setup_cuda_dll_directories()

from src.cli import parse_args
from src.config.config_loader import get_config
from src.utils.logger import setup_logger

def main():
    # 1. Parse CLI arguments
    args = parse_args()
    
    # 2. Setup Logging
    logger = setup_logger(debug=args.debug)
    
    # 3. Dispatch by Command
    if args.command == "config-assistant":
        from src.tools.config_assistant.server import run_server
        logger.info("[bold blue]Launching Config Assistant...[/bold blue]")
        run_server(port=args.port, debug=args.debug)
        return
    
    if args.command == "dashboard":
        from src.tools.dashboard.server import run_server
        logger.info("[bold blue]Launching Dashboard...[/bold blue]")
        run_server(port=args.port, debug=args.debug)
        return

    if args.command == "validate-config":
        try:
            config = get_config(game_name=args.game, override_path=args.config)
            logger.info(f"Configuration valid for game: [yellow]{args.game}[/yellow]")
            logger.debug(f"Validated Configuration: {config}")
        except Exception as e:
            logger.error(f"Configuration invalid: {e}")
            raise SystemExit(1) from e
        return

    # Default 'run' behavior
    logger.info("[bold blue]Starting FPS Video Snap Highlights Generator...[/bold blue]")
    
    # 4. Load Configuration
    try:
        config = get_config(game_name=args.game, override_path=args.config)
        logger.info(f"Loaded config for game: [yellow]{args.game}[/yellow]")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise SystemExit(1) from e
    
    # Override config with CLI arguments if provided
    if args.output:
        config['global']['output_dir'] = args.output
    if args.music:
        config['highlights']['music_path'] = args.music
    if args.debug:
        config['global']['debug'] = True
    if hasattr(args, 'debug_visual') and args.debug_visual:
        config['global']['debug_visual'] = True
        
    logger.debug(f"Final Configuration: {config}")
    
    # 4. Process Video(s)
    from src.pipeline.batch_processor import BatchProcessor
    
    try:
        processor = BatchProcessor(config)
        results = processor.process(args.videos)
        
        # Final Summary
        if not results:
            logger.warning("No videos were processed.")
            raise SystemExit(1)
            
        # Check if multi-video merge was performed
        merged_result = next((r for r in results if r.get("path") == "MERGED"), None)
        
        if merged_result:
            logger.info("\n[bold green]Multi-video merge complete![/bold green]")
            logger.info(f"  Source videos: {merged_result.get('source_videos', 0)}")
            logger.info(f"  Total clips: {merged_result.get('total_clips', 0)}")
            logger.info(f"  Output: [cyan]{merged_result.get('final_video')}[/cyan]")
        else:
            success_count = sum(1 for r in results if r.get('success'))
            logger.info("\n[bold green]Processing finished![/bold green]")
            logger.info(f"Successfully processed: [green]{success_count}/{len(results)}[/green]")

        if any(not r.get("success") for r in results):
            raise SystemExit(1)
        
    except Exception as e:
        logger.exception(f"An unexpected error occurred during processing: {e}")
        raise SystemExit(1) from e

if __name__ == "__main__":
    main()
