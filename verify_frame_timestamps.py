#!/usr/bin/env python3
"""
验证提取的帧的时间戳是否准确
通过使用 ffprobe 检查每帧的实际时间戳
"""
import subprocess
import sys
import os
import glob

def get_frame_timestamp(video_path, frame_number):
    """使用 ffprobe 获取指定帧的实际时间戳"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_frames",
        "-show_entries", "frame=pts_time,pkt_pts_time",
        "-of", "csv=p=0",
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
        lines = result.stdout.strip().split('\n')
        
        if frame_number < len(lines):
            timestamp_str = lines[frame_number].split(',')[0]
            return float(timestamp_str) if timestamp_str else None
        return None
    except Exception as e:
        print(f"Error getting frame timestamp: {e}")
        return None

def verify_extracted_frames(frames_dir):
    """验证提取的帧文件名与实际内容的时间戳是否匹配"""
    frame_files = sorted(glob.glob(os.path.join(frames_dir, "frame_*.jpg")))
    
    print(f"Found {len(frame_files)} frames in {frames_dir}")
    print("\n检查前 10 帧的时间戳:")
    print("=" * 70)
    print(f"{'文件名':<30} {'期望时间戳':<15} {'实际时间戳':<15} {'差异':<10}")
    print("=" * 70)
    
    mismatches = []
    
    for i, frame_file in enumerate(frame_files[:10]):  # 只检查前 10 帧
        filename = os.path.basename(frame_file)
        
        # 从文件名提取时间戳
        try:
            expected_ts_ms = int(filename.split('_')[1].split('.')[0])
            expected_ts_sec = expected_ts_ms / 1000.0
        except (IndexError, ValueError):
            print(f"无法从文件名解析时间戳: {filename}")
            continue
        
        print(f"{filename:<30} {expected_ts_sec:<15.3f} {'N/A':<15} {'N/A':<10}")
    
    print("=" * 70)
    print("\n注意: 由于提取的是图片文件，无法直接从中读取原始视频时间戳。")
    print("时间戳的准确性取决于 FFmpeg 的 fps 过滤器是否精确提取。")
    print("\n建议: 对比视频中该时间点的画面与提取的帧是否一致。")

def main():
    if len(sys.argv) < 2:
        print("用法: python verify_frame_timestamps.py <frames_directory>")
        print("示例: python verify_frame_timestamps.py temp/pipeline_xxx/frames")
        sys.exit(1)
    
    frames_dir = sys.argv[1]
    
    if not os.path.exists(frames_dir):
        print(f"错误: 目录不存在: {frames_dir}")
        sys.exit(1)
    
    verify_extracted_frames(frames_dir)

if __name__ == "__main__":
    main()
