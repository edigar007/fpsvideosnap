import subprocess
import os
from typing import List, Dict, Any
from src.utils.logger import logger
from src.video.video_info import VideoInfo
from src.video.transitions import TransitionManager

class VideoJoiner:
    """Joins multiple video clips into a single video with transitions."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.video_cfg = config.get("video", {})
        self.highlight_cfg = config.get("highlights", {})
        
        self.transition_mgr = TransitionManager(
            transition_type=self.highlight_cfg.get("transition_type", "fade"),
            duration=self.highlight_cfg.get("transition_duration", 0.5)
        )
        
        self.encoder = self.video_cfg.get("encoder", "h264_nvenc")
        self.fps = self.video_cfg.get("fps", 60)
        self.bitrate = self.video_cfg.get("bitrate", "20M")
        self.hwaccel = self.video_cfg.get("hwaccel", "cuda")

    def join_clips(self, clip_paths: List[str], output_path: str) -> bool:
        """Merges clips into one video at output_path."""
        if not clip_paths:
            logger.error("No clips provided to join.")
            return False

        if len(clip_paths) == 1:
            logger.info("Only one clip provided. Copying to output.")
            return self._copy_single_clip(clip_paths[0], output_path)

        logger.info(f"Joining {len(clip_paths)} clips with transitions...")
        return self._join_with_ffmpeg(clip_paths, output_path)

    def _copy_single_clip(self, input_path: str, output_path: str) -> bool:
        """Copies a single clip to the output path using stream copy if possible."""
        cmd = [
            self.video_cfg.get("ffmpeg_path", "ffmpeg"),
            "-y",
            "-i", input_path,
            "-c", "copy",
            output_path
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to copy single clip: {e.stderr.decode()}")
            return False

    def _join_with_ffmpeg(self, clip_paths: List[str], output_path: str) -> bool:
        """Uses FFmpeg complex filter to join clips with xfade and acrossfade."""
        durations = []
        for path in clip_paths:
            try:
                info = VideoInfo(path)
                # TASK-007: Use VideoInfo.duration property (float seconds)
                duration = info.duration
                if duration <= 0:
                    logger.error(f"Invalid duration {duration} for {path}")
                    return False
                durations.append(duration)
            except Exception as e:
                logger.error(f"Failed to get duration for {path}: {e}")
                return False

        transition_duration = self.transition_mgr.get_duration()
        
        # Build command
        cmd = [self.video_cfg.get("ffmpeg_path", "ffmpeg"), "-y"]
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])

        # Inputs
        for path in clip_paths:
            cmd.extend(["-i", path])

        # Filter complex
        filter_parts = []
        
        # Initial labels
        last_v_label = "0:v"
        last_a_label = "0:a"
        
        current_offset = durations[0]
        
        for i in range(1, len(clip_paths)):
            trans = self.transition_mgr.get_transition()
            
            # Ensure transition duration is not longer than both clips
            # Simple check: transition duration should be significantly less than clip duration
            actual_transition_duration = transition_duration
            if durations[i-1] < actual_transition_duration or durations[i] < actual_transition_duration:
                actual_transition_duration = min(durations[i-1], durations[i]) / 2
                logger.warning(f"Clip {i-1} or {i} is too short. Reducing transition duration to {actual_transition_duration:.2f}s")

            offset = current_offset - actual_transition_duration
            
            # Video xfade
            next_v_label = f"v{i}"
            filter_parts.append(
                f"[{last_v_label}][{i}:v]xfade=transition={trans}:duration={actual_transition_duration}:offset={offset}[{next_v_label}]"
            )
            last_v_label = next_v_label
            
            # Audio acrossfade
            next_a_label = f"a{i}"
            filter_parts.append(
                f"[{last_a_label}][{i}:a]acrossfade=d={actual_transition_duration}[{next_a_label}]"
            )
            last_a_label = next_a_label
            
            # Update offset for next clip
            current_offset = offset + durations[i]

        filter_complex = ";".join(filter_parts)
        cmd.extend(["-filter_complex", filter_complex])
        
        # Map output
        cmd.extend(["-map", f"[{last_v_label}]", "-map", f"[{last_a_label}]"])
        
        # Output settings
        cmd.extend([
            "-c:v", self.encoder,
            "-preset", "p4",
            "-b:v", self.bitrate,
            "-r", str(self.fps),
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ])

        try:
            logger.info(f"Running FFmpeg: {' '.join(cmd)}")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg failed with return code {process.returncode}")
                logger.debug(f"FFmpeg stderr: {stderr.decode()}")
                return False
                
            logger.info("Successfully joined clips.")
            return True
        except Exception as e:
            logger.error(f"Error joining clips: {e}")
            return False
