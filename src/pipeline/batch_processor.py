import os
import glob
from typing import List, Dict, Any
from src.utils.logger import get_logger
from src.pipeline.pipeline import Pipeline
from src.pipeline.multi_video import merge_clips_to_highlight
from src.video.video_joiner import VideoJoiner
from src.audio.audio_mixer import AudioMixer
from src.report.report_generator import ReportGenerator

logger = get_logger(__name__)


class BatchProcessor:
    """
    Handles processing of multiple video files.
    When multiple videos are provided, extracts clips from each and merges all into one final highlight.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def process(self, video_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Processes video files and merges all clips into a single highlight video.

        Args:
            video_paths: List of video file paths (can include glob patterns)

        Returns:
            List of result dicts with processing status
        """
        all_video_files = self._resolve_video_paths(video_paths)

        if not all_video_files:
            logger.warning("No video files found to process.")
            return []

        is_multi_video = len(all_video_files) > 1

        if is_multi_video:
            return self._process_multi_video(all_video_files)
        else:
            return self._process_single_video(all_video_files[0])

    def _resolve_video_paths(self, video_paths: List[str]) -> List[str]:
        """Resolves glob patterns and directories to actual video file paths."""
        video_files = []

        for pattern in video_paths:
            if os.path.isdir(pattern):
                for ext in ['.mp4', '.avi', '.mkv', '.mov']:
                    video_files.extend(glob.glob(os.path.join(pattern, f"*{ext}")))
                    video_files.extend(glob.glob(os.path.join(pattern, f"*{ext.upper()}")))
            elif os.path.isfile(pattern):
                video_files.append(pattern)
            else:
                matched = glob.glob(pattern)
                video_files.extend(matched)

        seen = set()
        unique_files = []
        for f in video_files:
            abs_path = os.path.abspath(f)
            if abs_path not in seen:
                seen.add(abs_path)
                unique_files.append(abs_path)

        return unique_files

    def _process_single_video(self, video_path: str) -> List[Dict[str, Any]]:
        """Process a single video file using the full pipeline."""
        logger.info(f"[bold blue]Processing single video: {video_path}[/bold blue]")

        pipeline = Pipeline(self.config)
        run_result = pipeline.run_full_result(video_path)

        result = {
            "path": video_path,
            "success": run_result.success,
            "summary": pipeline.get_summary(),
            "final_video": run_result.final_video,
            "clips_count": len(run_result.clips),
        }
        if run_result.error:
            result["error"] = run_result.error
            result["failed_stage"] = run_result.failed_stage

        logger.info(pipeline.get_summary())
        return [result]

    def _process_multi_video(self, video_files: List[str]) -> List[Dict[str, Any]]:
        """
        Process multiple videos: extract clips from each, then merge all into one highlight.
        """
        logger.info(f"[bold magenta]Multi-video mode: Processing {len(video_files)} videos[/bold magenta]")

        results = []
        all_clips = []

        for i, video_path in enumerate(video_files):
            logger.info(
                f"\n[bold cyan]({i + 1}/{len(video_files)}) "
                f"Extracting clips from: {os.path.basename(video_path)}[/bold cyan]"
            )

            pipeline = Pipeline(self.config)
            run_result = pipeline.run_until_clips_result(video_path)
            clips = run_result.clips

            result = {
                "path": video_path,
                "success": run_result.success,
                "clips_count": len(clips),
                "clips": clips,
            }
            if run_result.error:
                result["error"] = run_result.error
                result["failed_stage"] = run_result.failed_stage
            results.append(result)

            if not run_result.success:
                logger.error(f"Skipping clips from failed video: {video_path}")
                continue

            for clip in clips:
                clip_path = clip.get("path") or clip.get("output_path")
                if clip_path and os.path.exists(clip_path):
                    all_clips.append(clip)
                else:
                    logger.warning(f"Clip missing or invalid path: {clip}")

        if not all_clips:
            logger.warning("[yellow]No clips extracted from any video. Nothing to merge.[/yellow]")
            return results

        logger.info(f"\n[bold green]Merging {len(all_clips)} clips from {len(video_files)} videos...[/bold green]")
        merged_result = merge_clips_to_highlight(
            self.config,
            video_files,
            all_clips,
            video_joiner_cls=VideoJoiner,
            audio_mixer_cls=AudioMixer,
            report_generator_cls=ReportGenerator,
        )
        if not merged_result:
            return results

        logger.info("\n[bold green]Multi-video merge complete![/bold green]")
        logger.info(f"  Total clips: {merged_result['total_clips']}")
        logger.info(f"  Output: [cyan]{merged_result['final_video']}[/cyan]")
        logger.info(f"  Report: {merged_result['report_path']}")

        results.append(merged_result)

        return results
