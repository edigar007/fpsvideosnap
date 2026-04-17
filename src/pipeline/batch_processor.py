import os
import glob
from typing import List, Dict, Any
from datetime import datetime
from src.utils.logger import get_logger
from src.pipeline.pipeline import Pipeline
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
        success = pipeline.run(video_path)

        result = {
            "path": video_path,
            "success": success,
            "summary": pipeline.get_summary(),
            "final_video": pipeline.results.get("final_video"),
            "clips_count": len(pipeline.results.get("clips", []))
        }

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
            logger.info(f"\n[bold cyan]({i+1}/{len(video_files)}) Extracting clips from: {os.path.basename(video_path)}[/bold cyan]")

            pipeline = Pipeline(self.config)
            clips = pipeline.run_until_clips(video_path)

            result = {
                "path": video_path,
                "success": len(clips) > 0 or pipeline.stages["clips"].status.value == "SKIPPED",
                "clips_count": len(clips),
                "clips": clips
            }
            results.append(result)

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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = self.config.get("global", {}).get("output_dir", "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        merged_no_audio = os.path.join(output_dir, f"combined_temp_{timestamp}.mp4")
        final_output = os.path.join(output_dir, f"combined_highlights_{timestamp}.mp4")

        joiner = VideoJoiner(self.config)
        clip_paths = [c.get("path") or c.get("output_path") for c in all_clips]

        if not joiner.join_clips(clip_paths, merged_no_audio):
            logger.error("[red]Failed to merge clips.[/red]")
            return results

        mixer = AudioMixer(self.config)
        result_path = mixer.mix_audio(merged_no_audio, final_output)

        if result_path == merged_no_audio:
            import shutil
            shutil.copy2(merged_no_audio, final_output)

        keep_intermediates = bool(self.config.get("global", {}).get("debug", False)) or bool(
            self.config.get("video", {}).get("join_fix", {}).get("keep_intermediates", False)
        )
        if os.path.exists(merged_no_audio) and merged_no_audio != final_output and not keep_intermediates:
            try:
                os.remove(merged_no_audio)
            except Exception:
                pass

        report_gen = ReportGenerator(output_dir)
        video_info = {
            "path": f"Combined from {len(video_files)} videos",
            "source_videos": [os.path.basename(v) for v in video_files]
        }
        report_path = report_gen.generate(video_info, all_clips, self.config)

        logger.info(f"\n[bold green]Multi-video merge complete![/bold green]")
        logger.info(f"  Total clips: {len(all_clips)}")
        logger.info(f"  Output: [cyan]{final_output}[/cyan]")
        logger.info(f"  Report: {report_path}")

        results.append({
            "path": "MERGED",
            "success": True,
            "final_video": final_output,
            "total_clips": len(all_clips),
            "source_videos": len(video_files),
            "report_path": report_path
        })

        return results
