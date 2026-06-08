import os
import shutil
import subprocess
import tempfile
import json
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

        self.ffmpeg_path = self.video_cfg.get("ffmpeg_path", "ffmpeg")
        self.ffprobe_path = self.video_cfg.get("ffprobe_path", "ffprobe")
        self.encoder = self.video_cfg.get("encoder", "h264_nvenc")
        self.fps = self.video_cfg.get("fps", 60)
        self.bitrate = self.video_cfg.get("bitrate", "20M")
        self.hwaccel = self.video_cfg.get("hwaccel", "cuda")

        self.join_fix_cfg = self.video_cfg.get("join_fix", {})
        self.pre_normalize_clips = bool(self.join_fix_cfg.get("pre_normalize_clips", True))
        self.keep_intermediates = bool(self.join_fix_cfg.get("keep_intermediates", False))
        self.safe_preset = self.join_fix_cfg.get("safe_preset", "medium")
        self.output_preset = "p4" if self.encoder == "h264_nvenc" else "medium"
        self.safe_crf = str(self.join_fix_cfg.get("safe_crf", 18))
        self.safe_audio_rate = str(self.join_fix_cfg.get("safe_audio_rate", 48000))
        self.safe_channel_layout = self.join_fix_cfg.get("safe_channel_layout", "stereo")

    def join_clips(self, clip_paths: List[str], output_path: str) -> bool:
        """Merges clips into one video at output_path."""
        if not clip_paths:
            logger.error("No clips provided to join.")
            return False

        if len(clip_paths) == 1:
            logger.info("Only one clip provided. Copying to output.")
            return self._copy_single_clip(clip_paths[0], output_path)

        normalized_dir = None
        join_inputs = clip_paths

        try:
            if self.pre_normalize_clips or self._any_clip_missing_audio(clip_paths):
                join_inputs, normalized_dir = self._prepare_join_inputs(clip_paths)

            logger.info(f"Joining {len(join_inputs)} clips with transitions...")
            return self._join_with_ffmpeg(join_inputs, output_path)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
            logger.error(f"Failed to prepare clips for join: {stderr or e}")
            return False
        except Exception as e:
            logger.error(f"Error preparing clips for join: {e}")
            return False
        finally:
            if normalized_dir and not self.keep_intermediates:
                shutil.rmtree(normalized_dir, ignore_errors=True)

    def _copy_single_clip(self, input_path: str, output_path: str) -> bool:
        """Copies a single clip to the output path using stream copy if possible."""
        cmd = [
            self.ffmpeg_path,
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

    def _prepare_join_inputs(self, clip_paths: List[str]) -> Tuple[List[str], str]:
        temp_root = self.config.get("global", {}).get("temp_dir", "temp")
        os.makedirs(temp_root, exist_ok=True)

        normalized_dir = tempfile.mkdtemp(prefix="join_norm_", dir=temp_root)
        normalized_paths = [
            self._normalize_clip_for_join(path, normalized_dir, index)
            for index, path in enumerate(clip_paths)
        ]
        return normalized_paths, normalized_dir

    def _any_clip_missing_audio(self, clip_paths: List[str]) -> bool:
        return any(not self._has_audio_stream(path) for path in clip_paths)

    def _has_audio_stream(self, input_path: str) -> bool:
        cmd = [
            self.ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            input_path,
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            data = json.loads(result.stdout or "{}")
            return bool(data.get("streams"))
        except Exception as exc:
            logger.debug(f"Could not probe audio stream for {input_path}, assuming audio exists: {exc}")
            return True

    def _normalize_clip_for_join(self, input_path: str, temp_dir: str, index: int) -> str:
        output_path = os.path.join(temp_dir, f"join_norm_{index + 1:03d}.mp4")
        has_audio = self._has_audio_stream(input_path)
        audio_input_label = "[0:a]"

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-fflags", "+genpts",
            "-i", input_path,
        ]

        if not has_audio:
            duration = VideoInfo(input_path, ffprobe_path=self.ffprobe_path).duration
            cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    f"anullsrc=channel_layout={self.safe_channel_layout}:sample_rate={self.safe_audio_rate}",
                ]
            )
            audio_input_label = "[1:a]"

        filter_complex = (
            f"[0:v]"
            f"fps={self.fps},"
            f"scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos,"
            f"setsar=1,"
            f"format=yuv420p,"
            f"settb=AVTB,"
            f"setpts=PTS-STARTPTS[vout];"
            f"{audio_input_label}"
            f"aformat=sample_rates={self.safe_audio_rate}:channel_layouts={self.safe_channel_layout},"
            f"aresample=async=1:first_pts=0,"
            f"asetpts=PTS-STARTPTS[aout]"
        )

        cmd.extend(
            [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", self.safe_preset,
            "-crf", self.safe_crf,
            "-g", str(self.fps * 2),
            "-keyint_min", "1",
            "-sc_threshold", "0",
            "-bf", "0",
            "-pix_fmt", "yuv420p",
            "-force_key_frames", "0",
            "-c:a", "aac",
            "-ar", self.safe_audio_rate,
            "-ac", "2",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-avoid_negative_ts", "make_zero",
            "-max_interleave_delta", "0",
            output_path,
            ]
        )

        logger.info(f"Normalizing clip for join: {input_path} -> {output_path}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return output_path

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
        """Normalize each input stream to a safe, uniform format before joining."""
        filter_parts = []
        video_labels = []
        audio_labels = []

        for i in range(clip_count):
            video_label = f"vnorm{i}"
            audio_label = f"anorm{i}"
            filter_parts.append(
                f"[{i}:v]"
                f"fps={self.fps},"
                f"scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos,"
                f"setsar=1,"
                f"format=yuv420p,"
                f"settb=AVTB,"
                f"setpts=PTS-STARTPTS"
                f"[{video_label}]"
            )
            filter_parts.append(
                f"[{i}:a]"
                f"aformat=sample_rates={self.safe_audio_rate}:channel_layouts={self.safe_channel_layout},"
                f"aresample=async=1:first_pts=0,"
                f"asetpts=PTS-STARTPTS"
                f"[{audio_label}]"
            )
            video_labels.append(video_label)
            audio_labels.append(audio_label)

        return filter_parts, video_labels, audio_labels

    def _join_with_concat(self, clip_paths: List[str], output_path: str) -> bool:
        """使用concat filter快速拼接，无转场效果"""
        try:
            cmd = [self.ffmpeg_path, "-y"]

            if self.hwaccel == "cuda":
                cmd.extend(["-hwaccel", "cuda"])

            for path in clip_paths:
                cmd.extend(["-i", path])

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
                "-preset", self.output_preset,
                "-b:v", self.bitrate,
                "-r", str(self.fps),
                "-g", str(self.fps * 2),
                "-bf", "0",
                "-pix_fmt", "yuv420p",
                "-force_key_frames", "0",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-avoid_negative_ts", "make_zero",
                "-max_interleave_delta", "0",
            ])

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
                info = VideoInfo(path, ffprobe_path=self.ffprobe_path)
                duration = info.duration
                if duration <= 0:
                    logger.error(f"Invalid duration {duration} for {path}")
                    return False
                durations.append(duration)
            except Exception as e:
                logger.error(f"Failed to get duration for {path}: {e}")
                return False

        transition_duration = self.transition_mgr.get_duration()

        cmd = [self.ffmpeg_path, "-y"]
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])

        for path in clip_paths:
            cmd.extend(["-i", path])

        filter_parts, video_labels, audio_labels = self._build_normalized_input_filters(len(clip_paths))

        last_v_label = video_labels[0]
        last_a_label = audio_labels[0]
        current_offset = durations[0]

        for i in range(1, len(clip_paths)):
            trans = self.transition_mgr.get_transition()

            actual_transition_duration = transition_duration
            if durations[i - 1] < actual_transition_duration or durations[i] < actual_transition_duration:
                actual_transition_duration = min(durations[i - 1], durations[i]) / 2
                logger.warning(
                    f"Clip {i - 1} or {i} is too short. "
                    f"Reducing transition duration to {actual_transition_duration:.2f}s"
                )

            offset = current_offset - actual_transition_duration

            next_v_label = f"v{i}"
            filter_parts.append(
                f"[{last_v_label}][{video_labels[i]}]"
                f"xfade=transition={trans}:duration={actual_transition_duration}:offset={offset}"
                f"[{next_v_label}]"
            )
            last_v_label = next_v_label

            next_a_label = f"a{i}"
            filter_parts.append(
                f"[{last_a_label}][{audio_labels[i]}]acrossfade=d={actual_transition_duration}[{next_a_label}]"
            )
            last_a_label = next_a_label

            current_offset = offset + durations[i]

        filter_complex = ";".join(filter_parts)
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", f"[{last_v_label}]", "-map", f"[{last_a_label}]"])

        cmd.extend([
            "-c:v", self.encoder,
            "-preset", self.output_preset,
            "-b:v", self.bitrate,
            "-r", str(self.fps),
            "-g", str(self.fps * 2),
            "-bf", "0",
            "-pix_fmt", "yuv420p",
            "-force_key_frames", "0",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-avoid_negative_ts", "make_zero",
            "-max_interleave_delta", "0",
        ])

        if self.encoder == "h264_nvenc":
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
