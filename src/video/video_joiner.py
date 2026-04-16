import subprocess
import os
from typing import List, Dict, Any, Tuple
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
        """Uses FFmpeg to join clips. Supports both concat (no transitions) and xfade (with transitions)."""
        transition_type = self.highlight_cfg.get("transition_type", "fade")

        # 如果禁用转场或转场类型为none，使用简单concat
        if transition_type == "none":
            return self._join_with_concat(clip_paths, output_path)
        else:
            # 使用xfade转场（可能有花屏问题）
            return self._join_with_xfade(clip_paths, output_path)

    def _build_normalized_input_filters(self, clip_count: int) -> Tuple[List[str], List[str], List[str]]:
        """Normalize each input stream to start at timestamp zero before joining."""
        filter_parts = []
        video_labels = []
        audio_labels = []

        for i in range(clip_count):
            video_label = f"vnorm{i}"
            audio_label = f"anorm{i}"
            filter_parts.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[{video_label}]")
            filter_parts.append(
                f"[{i}:a]aresample=async=1:first_pts=0,asetpts=PTS-STARTPTS[{audio_label}]"
            )
            video_labels.append(video_label)
            audio_labels.append(audio_label)

        return filter_parts, video_labels, audio_labels

    def _join_with_concat(self, clip_paths: List[str], output_path: str) -> bool:
        """使用concat filter快速拼接，无转场效果"""
        try:
            # 使用concat filter
            cmd = [self.video_cfg.get("ffmpeg_path", "ffmpeg"), "-y"]

            if self.hwaccel == "cuda":
                cmd.extend(["-hwaccel", "cuda"])

            # 添加所有输入
            for path in clip_paths:
                cmd.extend(["-i", path])

            # 构建concat filter
            n = len(clip_paths)
            filter_parts, video_labels, audio_labels = self._build_normalized_input_filters(n)
            video_inputs = "".join([f"[{label}]" for label in video_labels])
            audio_inputs = "".join([f"[{label}]" for label in audio_labels])
            filter_parts.append(f"{video_inputs}concat=n={n}:v=1:a=0[vout]")
            filter_parts.append(f"{audio_inputs}concat=n={n}:v=0:a=1[aout]")
            filter_complex = ";".join(filter_parts)

            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "[aout]",
                "-c:v", self.encoder,
                "-preset", "p4",
                "-b:v", self.bitrate,
                "-g", str(self.fps * 2),
                "-bf", "0",
                "-force_key_frames", "0",
                "-c:a", "aac",
                "-b:a", "192k",
            ])

            # NVENC: force keyframes to be IDR for better random access / VLC compatibility
            if self.encoder == "h264_nvenc":
                cmd.extend(["-forced-idr", "1", "-strict_gop", "1"])

            cmd.append(output_path)
            
            logger.info(f"Joining {n} clips with concat filter (no transitions)...")
            logger.debug(f"Running FFmpeg: {' '.join(cmd)}")
            
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Successfully joined clips with concat.")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Concat join failed: {e.stderr.decode() if e.stderr else str(e)}")
            return False
    
    def _join_with_xfade(self, clip_paths: List[str], output_path: str) -> bool:
        """Uses FFmpeg xfade filter to join clips with transitions."""
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
        filter_parts, video_labels, audio_labels = self._build_normalized_input_filters(len(clip_paths))

        # Initial labels - 使用归一化后的输入，避免首个clip把原始时间戳直接带入输出
        last_v_label = video_labels[0]
        last_a_label = audio_labels[0]

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
                f"[{last_v_label}][{video_labels[i]}]xfade=transition={trans}:duration={actual_transition_duration}:offset={offset}[{next_v_label}]"
            )
            last_v_label = next_v_label

            # Audio acrossfade
            next_a_label = f"a{i}"
            filter_parts.append(
                f"[{last_a_label}][{audio_labels[i]}]acrossfade=d={actual_transition_duration}[{next_a_label}]"
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
            "-g", str(self.fps * 2),  # GOP size: 每2秒一个关键帧
            "-bf", "0",  # 禁用B帧，xfade需要简单的帧结构
            "-pix_fmt", "yuv420p",  # 确保像素格式一致
            "-force_key_frames", "0",
            "-c:a", "aac",
            "-b:a", "192k",
        ])

        if self.encoder == "h264_nvenc":
            # Force IDR at keyframes (esp. the first one) to prevent initial corruption in VLC.
            cmd.extend(["-forced-idr", "1", "-strict_gop", "1"])

        cmd.append(output_path)

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
