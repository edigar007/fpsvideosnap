#!/usr/bin/env python3
"""
测试帧提取的准确性
提取视频的前 10 秒帧，并手动验证时间戳
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from video.frame_extractor import FrameExtractor
from utils.logger import logger
import subprocess

def verify_frame_content(video_path, frame_path, expected_timestamp_ms):
    """
    通过提取视频中指定时间点的单帧来验证
    比较是否与已提取的帧一致
    """
    timestamp_sec = expected_timestamp_ms / 1000.0
    
    # 临时验证帧路径
    verify_path = frame_path.replace(".jpg", "_verify.jpg")
    
    cmd = [
        "ffmpeg",
        "-ss", str(timestamp_sec),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        "-y",  # 覆盖
        verify_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # 比较文件大小（简单验证）
        original_size = os.path.getsize(frame_path)
        verify_size = os.path.getsize(verify_path)
        size_diff_percent = abs(original_size - verify_size) / original_size * 100
        
        # 清理
        os.remove(verify_path)
        
        return size_diff_percent < 5  # 允许 5% 的差异
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("用法: python test_frame_extraction.py <video_path>")
        print("示例: python test_frame_extraction.py 'G:\\Video\\test.mp4'")
        sys.exit(1)
    
    video_path = sys.argv[1]
    
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        sys.exit(1)
    
    # 创建临时目录
    test_dir = "temp/test_frame_extraction"
    os.makedirs(test_dir, exist_ok=True)
    
    # 提取前 10 秒的帧（interval=1000ms）
    print("=" * 70)
    print("测试帧提取准确性")
    print("=" * 70)
    print(f"视频: {video_path}")
    print(f"输出目录: {test_dir}")
    print(f"间隔: 1000ms (1秒)")
    print()
    
    extractor = FrameExtractor(hwaccel="cuda")
    
    try:
        frames = extractor.extract_frames(video_path, test_dir, interval_ms=1000)
        
        print(f"✓ 提取了 {len(frames)} 帧")
        print()
        
        # 检查前 10 帧
        print("验证前 10 帧的文件名和时间戳:")
        print("-" * 70)
        
        for i, frame_path in enumerate(frames[:10]):
            filename = os.path.basename(frame_path)
            
            # 从文件名提取时间戳
            try:
                timestamp_ms = int(filename.split('_')[1].split('.')[0])
                expected_ms = i * 1000
                
                match = "✓" if timestamp_ms == expected_ms else "✗"
                print(f"{match} {filename:<25} 期望: {expected_ms}ms, 实际: {timestamp_ms}ms")
                
                if timestamp_ms != expected_ms:
                    print(f"   警告: 时间戳不匹配! 差异 {timestamp_ms - expected_ms}ms")
                
            except (IndexError, ValueError) as e:
                print(f"✗ {filename:<25} 无法解析时间戳: {e}")
        
        print("-" * 70)
        print()
        print("测试完成!")
        print(f"提取的帧保存在: {test_dir}")
        
    except Exception as e:
        print(f"✗ 提取失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
