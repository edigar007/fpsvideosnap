import sys
import os

# Windows GPU 支持：在所有导入之前添加 CUDA DLL 目录
if sys.platform == 'win32':
    try:
        import site
        site_packages_list = site.getsitepackages()
        for site_packages in site_packages_list:
            nvidia_base = os.path.join(site_packages, 'nvidia')
            if os.path.exists(nvidia_base):
                # 获取所有 nvidia 子目录中的 bin 文件夹
                for nvidia_pkg in os.listdir(nvidia_base):
                    bin_path = os.path.join(nvidia_base, nvidia_pkg, 'bin')
                    if os.path.exists(bin_path):
                        try:
                            # Python 3.8+ Windows 10+ 使用 add_dll_directory
                            if hasattr(os, 'add_dll_directory'):
                                os.add_dll_directory(bin_path)
                            # 同时添加到 PATH（兼容性）
                            if bin_path not in os.environ.get('PATH', ''):
                                os.environ['PATH'] = bin_path + os.pathsep + os.environ.get('PATH', '')
                        except Exception:
                            pass
                print(f"[GPU] CUDA DLL directories configured for PaddleOCR GPU support")
                break
    except Exception as e:
        print(f"[GPU] Warning: Could not configure CUDA paths: {e}")

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
    
    # 3. Dispatch by Command
    if args.command == "config-assistant":
        from src.tools.config_assistant.server import run_server
        logger.info("[bold blue]Launching Config Assistant...[/bold blue]")
        run_server(port=args.port, debug=args.debug)
        return

    # Default 'run' behavior
    logger.info("[bold blue]Starting FPS Video Snap Highlights Generator...[/bold blue]")
    
    # 4. Load Configuration
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
    if hasattr(args, 'debug_visual') and args.debug_visual:
        config['global']['debug_visual'] = True
        
    logger.debug(f"Final Configuration: {config}")
    
    # 4. Process Video(s)
    from src.pipeline.batch_processor import BatchProcessor
    
    try:
        processor = BatchProcessor(config)
        results = processor.process(args.video)  # args.video is now a list
        
        # Final Summary
        if not results:
            logger.warning("No videos were processed.")
            return
            
        # Check if multi-video merge was performed
        merged_result = next((r for r in results if r.get("path") == "MERGED"), None)
        
        if merged_result:
            logger.info(f"\n[bold green]Multi-video merge complete![/bold green]")
            logger.info(f"  Source videos: {merged_result.get('source_videos', 0)}")
            logger.info(f"  Total clips: {merged_result.get('total_clips', 0)}")
            logger.info(f"  Output: [cyan]{merged_result.get('final_video')}[/cyan]")
        else:
            success_count = sum(1 for r in results if r.get('success'))
            logger.info(f"\n[bold green]Processing finished![/bold green]")
            logger.info(f"Successfully processed: [green]{success_count}/{len(results)}[/green]")
        
    except Exception as e:
        logger.exception(f"An unexpected error occurred during processing: {e}")

if __name__ == "__main__":
    main()
