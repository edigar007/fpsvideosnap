import os
from datetime import datetime
from typing import List, Dict, Any

class ReportGenerator:
    """
    Generates a Markdown report for each FPS Video Snap run.
    """
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate(self, 
                 video_info: Dict[str, Any], 
                 clips: List[Dict[str, Any]], 
                 config: Dict[str, Any], 
                 logs: List[str] = None) -> str:
        """
        Generates the Markdown content and saves it to a file.
        Returns the path to the generated report.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_{timestamp}.md"
        report_path = os.path.join(self.output_dir, report_filename)
        
        # Calculate stats
        total_kills = sum(clip.get("kill_count", 0) for clip in clips)
        kill_types = {}
        for clip in clips:
            kt = clip.get("kill_type", "unknown")
            kill_types[kt] = kill_types.get(kt, 0) + 1
            
        md_content = self._build_markdown(video_info, clips, config, total_kills, kill_types, logs)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        return report_path

    def _build_markdown(self, 
                        video_info: Dict[str, Any], 
                        clips: List[Dict[str, Any]], 
                        config: Dict[str, Any],
                        total_kills: int,
                        kill_types: Dict[str, int],
                        logs: List[str]) -> str:
        
        # Header
        lines = [
            "# FPS Video Snap Processing Report",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 1. Video Statistics",
            f"- **Source File**: {video_info.get('video_path', 'Unknown')}",
            f"- **Resolution**: {video_info.get('width', 0)}x{video_info.get('height', 0)}",
            f"- **FPS**: {video_info.get('fps', 0)}",
            f"- **Duration**: {video_info.get('duration_str', '00:00:00')}",
            "",
            "## 2. Detection Summary",
            f"- **Total Kills Detected**: {total_kills}",
            f"- **Total Clips Extracted**: {len(clips)}",
            ""
        ]
        
        # Multi-kill stats
        if kill_types:
            lines.append("### Breakdown by Kill Type")
            for kt, count in sorted(kill_types.items()):
                lines.append(f"- {kt.replace('_', ' ').title()}: {count}")
            lines.append("")
            
        # Clips Table
        lines.append("## 3. Detailed Clips List")
        if not clips:
            lines.append("No kills detected in this run.")
        else:
            lines.append("| Clip # | Start Time | End Time | Kill Count | Type |")
            lines.append("|---|---|---|---|---|")
            for i, clip in enumerate(clips, 1):
                # TASK-008: Consume 'start_ms'/'end_ms' from clip metadata (not 'start'/'end' in seconds)
                start_ms = clip.get("start_ms", 0)
                end_ms = clip.get("end_ms", 0)
                start = self._format_ms(start_ms)
                end = self._format_ms(end_ms)
                k_count = clip.get("kill_count", 0)
                k_type = clip.get("kill_type", "single_kill").replace('_', ' ').title()
                lines.append(f"| {i} | {start} | {end} | {k_count} | {k_type} |")
        
        lines.append("")
        
        # Configuration Summary
        lines.append("## 4. Configuration Summary")
        lines.append("```yaml")
        # For simplicity, we just print the key parts of the config
        # Alternatively, we could dump the whole thing, but it might be too long
        filtered_config = {
            "global": config.get("global", {}),
            "detection": config.get("detection", {}),
            "highlights": config.get("highlights", {})
        }
        import yaml
        lines.append(yaml.dump(filtered_config, default_flow_style=False))
        lines.append("```")
        lines.append("")
        
        # Logs/Errors
        if logs:
            lines.append("## 5. Processing Logs")
            lines.append("```")
            lines.extend(logs)
            lines.append("```")
            
        return "\n".join(lines)

    def _format_ms(self, ms: float) -> str:
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        hours = int((ms / (1000 * 60 * 60)) % 24)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{int(ms % 1000):03d}"
