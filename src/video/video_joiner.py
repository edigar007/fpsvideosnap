import json
import os
import shutil
import subprocess
import tempfile
from enum import Enum
from typing import List, Dict, Any, Tuple
from src.utils.logger import logger
from src.video.ffmpeg_command import JoinCommandBuilder
from src.video.video_info import VideoInfo
from src.video.transitions import TransitionManager


class AudioProbeResult(Enum):
    HAS_AUDIO = "has_audio"
    NO_AUDIO = "no_audio"
    PROBE_FAILED = "probe_failed"


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
        self.xfade_segment_size = self._parse_xfade_segment_size(
            self.join_fix_cfg.get("xfade_segment_size", 4)
        )
        self.output_preset = "p4" if self.encoder == "h264_nvenc" else "medium"
        self.safe_crf = str(self.join_fix_cfg.get("safe_crf", 18))
        self.safe_audio_rate = str(self.join_fix_cfg.get("safe_audio_rate", 48000))
        self.safe_channel_layout = self.join_fix_cfg.get("safe_channel_layout", "stereo")
        self.command_builder = JoinCommandBuilder(
            ffmpeg_path=self.ffmpeg_path,
            encoder=self.encoder,
            fps=self.fps,
            bitrate=self.bitrate,
            hwaccel=self.hwaccel,
            output_preset=self.output_preset,
            safe_preset=self.safe_preset,
            safe_crf=self.safe_crf,
            safe_audio_rate=self.safe_audio_rate,
            safe_channel_layout=self.safe_channel_layout,
        )

        # Cache audio probe results per path so each clip is ffprobed at most
        # once per VideoJoiner instance. Without this, join_clips probes every
        # clip once in _any_clip_missing_audio and then again in
        # _normalize_clip_for_join via _has_audio_stream (2 probes per clip).
        self._audio_probe_cache: Dict[str, AudioProbeResult] = {}

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
        for path in clip_paths:
            probe_result = self._probe_audio_stream(path)
            if probe_result == AudioProbeResult.PROBE_FAILED:
                raise RuntimeError(f"Could not probe audio stream for {path}")
            if probe_result == AudioProbeResult.NO_AUDIO:
                return True
        return False

    def _has_audio_stream(self, input_path: str) -> bool:
        probe_result = self._probe_audio_stream(input_path)
        if probe_result == AudioProbeResult.PROBE_FAILED:
            raise RuntimeError(f"Could not probe audio stream for {input_path}")
        return probe_result == AudioProbeResult.HAS_AUDIO

    def _probe_audio_stream(self, input_path: str) -> AudioProbeResult:
        # Reuse the cached result so repeated audio checks within the same join
        # (e.g. _any_clip_missing_audio followed by _has_audio_stream inside
        # _normalize_clip_for_join) do not spawn ffprobe twice per clip.
        if input_path in self._audio_probe_cache:
            return self._audio_probe_cache[input_path]

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
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, TypeError) as exc:
            logger.error(f"Could not probe audio stream for {input_path}: {exc}")
            probe_result = AudioProbeResult.PROBE_FAILED
            self._audio_probe_cache[input_path] = probe_result
            return probe_result

        probe_result = (
            AudioProbeResult.HAS_AUDIO if data.get("streams") else AudioProbeResult.NO_AUDIO
        )
        self._audio_probe_cache[input_path] = probe_result
        return probe_result

    def _normalize_clip_for_join(self, input_path: str, temp_dir: str, index: int) -> str:
        output_path = os.path.join(temp_dir, f"join_norm_{index + 1:03d}.mp4")
        has_audio = self._has_audio_stream(input_path)
        duration = VideoInfo(input_path, ffprobe_path=self.ffprobe_path).duration if not has_audio else None
        command = self.command_builder.build_normalize_command(
            input_path=input_path,
            output_path=output_path,
            has_audio=has_audio,
            duration=duration,
        )

        logger.info(f"Normalizing clip for join: {input_path} -> {output_path}")
        subprocess.run(command.args, check=True, capture_output=True, text=True)
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

    def _parse_xfade_segment_size(self, value: Any) -> int:
        try:
            segment_size = int(value)
        except (TypeError, ValueError):
            logger.warning(f"Invalid xfade_segment_size {value!r}; using 4.")
            return 4

        if segment_size <= 0:
            return 0
        if segment_size < 2:
            logger.warning("xfade_segment_size must be at least 2; using 2.")
            return 2
        return segment_size

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
            n = len(clip_paths)
            command = self.command_builder.build_concat_command(
                clip_paths,
                output_path,
                self._build_normalized_input_filters,
            )

            logger.info(f"Joining {n} clips with concat filter (no transitions)...")
            logger.debug(f"Running FFmpeg: {' '.join(command.args)}")

            subprocess.run(command.args, check=True, capture_output=True)
            logger.info("Successfully joined clips with concat.")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Concat join failed: {e.stderr.decode() if e.stderr else str(e)}")
            return False

    def _join_with_xfade(self, clip_paths: List[str], output_path: str) -> bool:
        """Uses FFmpeg xfade filter to join clips with transitions."""
        if self.xfade_segment_size and len(clip_paths) > self.xfade_segment_size:
            return self._join_with_segmented_xfade(clip_paths, output_path)

        return self._join_with_xfade_command(clip_paths, output_path)

    def _join_with_segmented_xfade(self, clip_paths: List[str], output_path: str) -> bool:
        """Join large xfade chains in smaller passes to cap FFmpeg filter memory."""
        temp_root = self.config.get("global", {}).get("temp_dir", "temp")
        os.makedirs(temp_root, exist_ok=True)
        segment_dir = tempfile.mkdtemp(prefix="xfade_segments_", dir=temp_root)
        segment_paths = []

        try:
            chunks = [
                clip_paths[index:index + self.xfade_segment_size]
                for index in range(0, len(clip_paths), self.xfade_segment_size)
            ]
            logger.info(
                "Joining %s clips in %s xfade segments of up to %s inputs.",
                len(clip_paths),
                len(chunks),
                self.xfade_segment_size,
            )

            for index, chunk in enumerate(chunks, start=1):
                segment_path = os.path.join(segment_dir, f"xfade_segment_{index:03d}.mp4")
                logger.info(
                    "Joining xfade segment %s/%s with %s clips...",
                    index,
                    len(chunks),
                    len(chunk),
                )

                if len(chunk) == 1:
                    success = self._copy_single_clip(chunk[0], segment_path)
                else:
                    success = self._join_with_xfade_command(chunk, segment_path)

                if not success:
                    logger.error(f"Failed to join xfade segment {index}/{len(chunks)}.")
                    return False
                segment_paths.append(segment_path)

            return self._join_with_xfade(segment_paths, output_path)
        finally:
            if not self.keep_intermediates:
                shutil.rmtree(segment_dir, ignore_errors=True)

    def _join_with_xfade_command(self, clip_paths: List[str], output_path: str) -> bool:
        """Run one FFmpeg xfade command for a bounded number of inputs."""
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
        transitions = [self.transition_mgr.get_transition() for _ in range(1, len(clip_paths))]
        command = self.command_builder.build_xfade_command(
            clip_paths,
            output_path,
            durations,
            transition_duration,
            transitions,
            self._build_normalized_input_filters,
        )
        for warning in command.warnings:
            logger.warning(warning)

        try:
            logger.info(f"Running FFmpeg: {' '.join(command.args)}")
            process = subprocess.Popen(command.args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                logger.error(f"FFmpeg xfade failed with return code {process.returncode}")
                logger.debug(f"FFmpeg stderr: {stderr.decode()}")
                logger.warning("Falling back to concat join without transitions")
                return self._join_with_concat(clip_paths, output_path)

            logger.info("Successfully joined clips with xfade.")
            return True
        except Exception as e:
            logger.error(f"Error joining clips with xfade: {e}")
            logger.warning("Falling back to concat join without transitions")
            return self._join_with_concat(clip_paths, output_path)
