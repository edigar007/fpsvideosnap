from dataclasses import dataclass, field
from typing import Callable, List, Sequence, Tuple


@dataclass(frozen=True)
class FFmpegCommand:
    args: List[str]
    filter_complex: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class JoinCommandBuilder:
    ffmpeg_path: str
    encoder: str
    fps: int
    bitrate: str
    hwaccel: str | None
    output_preset: str
    safe_preset: str
    safe_crf: str
    safe_audio_rate: str
    safe_channel_layout: str

    def build_normalize_command(
        self,
        input_path: str,
        output_path: str,
        has_audio: bool,
        duration: float | None,
    ) -> FFmpegCommand:
        audio_input_label = "[0:a]"
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-fflags",
            "+genpts",
            "-i",
            input_path,
        ]

        if not has_audio:
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
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                self.safe_preset,
                "-crf",
                self.safe_crf,
                "-g",
                str(self.fps * 2),
                "-keyint_min",
                "1",
                "-sc_threshold",
                "0",
                "-bf",
                "0",
                "-pix_fmt",
                "yuv420p",
                "-force_key_frames",
                "0",
                "-c:a",
                "aac",
                "-ar",
                self.safe_audio_rate,
                "-ac",
                "2",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-avoid_negative_ts",
                "make_zero",
                "-max_interleave_delta",
                "0",
                output_path,
            ]
        )
        return FFmpegCommand(args=cmd, filter_complex=filter_complex)

    def build_concat_command(
        self,
        clip_paths: Sequence[str],
        output_path: str,
        normalized_input_filters: Callable[[int], Tuple[List[str], List[str], List[str]]],
    ) -> FFmpegCommand:
        cmd = self._input_command(clip_paths)
        n = len(clip_paths)
        filter_parts, video_labels, audio_labels = normalized_input_filters(n)
        video_inputs = "".join([f"[{label}]" for label in video_labels])
        audio_inputs = "".join([f"[{label}]" for label in audio_labels])
        filter_parts.append(f"{video_inputs}concat=n={n}:v=1:a=0[vout]")
        filter_parts.append(f"{audio_inputs}concat=n={n}:v=0:a=1[aout]")
        filter_complex = ";".join(filter_parts)

        cmd.extend(["-filter_complex", filter_complex, "-map", "[vout]", "-map", "[aout]"])
        cmd.extend(self._output_args())
        cmd.append(output_path)
        return FFmpegCommand(args=cmd, filter_complex=filter_complex)

    def build_xfade_command(
        self,
        clip_paths: Sequence[str],
        output_path: str,
        durations: Sequence[float],
        transition_duration: float,
        transitions: Sequence[str],
        normalized_input_filters: Callable[[int], Tuple[List[str], List[str], List[str]]],
    ) -> FFmpegCommand:
        cmd = self._input_command(clip_paths)
        filter_parts, video_labels, audio_labels = normalized_input_filters(len(clip_paths))
        warnings = []

        last_v_label = video_labels[0]
        last_a_label = audio_labels[0]
        current_offset = durations[0]

        for i in range(1, len(clip_paths)):
            actual_transition_duration = transition_duration
            if durations[i - 1] < actual_transition_duration or durations[i] < actual_transition_duration:
                actual_transition_duration = min(durations[i - 1], durations[i]) / 2
                warnings.append(
                    f"Clip {i - 1} or {i} is too short. "
                    f"Reducing transition duration to {actual_transition_duration:.2f}s"
                )

            offset = current_offset - actual_transition_duration

            next_v_label = f"v{i}"
            filter_parts.append(
                f"[{last_v_label}][{video_labels[i]}]"
                f"xfade=transition={transitions[i - 1]}:duration={actual_transition_duration}:offset={offset}"
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
        cmd.extend(self._output_args())
        cmd.append(output_path)
        return FFmpegCommand(args=cmd, filter_complex=filter_complex, warnings=warnings)

    def _input_command(self, clip_paths: Sequence[str]) -> List[str]:
        cmd = [self.ffmpeg_path, "-y"]
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])
        for path in clip_paths:
            cmd.extend(["-i", path])
        return cmd

    def _output_args(self) -> List[str]:
        args = [
            "-c:v",
            self.encoder,
            "-preset",
            self.output_preset,
            "-b:v",
            self.bitrate,
            "-r",
            str(self.fps),
            "-g",
            str(self.fps * 2),
            "-bf",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-force_key_frames",
            "0",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-avoid_negative_ts",
            "make_zero",
            "-max_interleave_delta",
            "0",
        ]
        if self.encoder == "h264_nvenc":
            args.extend(["-forced-idr", "1", "-strict_gop", "1"])
        return args
