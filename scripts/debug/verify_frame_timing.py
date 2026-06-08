#!/usr/bin/env python3
"""
验证提取的帧与视频实际时间戳的对应关系
通过比较提取的帧和直接从视频指定时间点提取的帧
"""
import os
import sys
import subprocess
import cv2
import numpy as np

def extract_frame_at_timestamp(video_path, timestamp_ms, output_path):
    """从视频中精确提取指定时间戳的帧"""
    timestamp_sec = timestamp_ms / 1000.0
    
    cmd = [
        "ffmpeg",
        "-ss", str(timestamp_sec),  # 精确定位到指定时间
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        "-y",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg错误: {e.stderr}")
        return False

def compare_frames(frame1_path, frame2_path):
    """比较两个帧的相似度"""
    img1 = cv2.imread(frame1_path)
    img2 = cv2.imread(frame2_path)
    
    if img1 is None or img2 is None:
        return None, "无法读取图片"
    
    # 确保尺寸相同
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    
    # 计算均方误差(MSE)和结构相似度(SSIM)
    mse = np.mean((img1.astype(float) - img2.astype(float)) ** 2)
    
    # 转换为灰度图计算SSIM
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    
    # 简单的相似度计算（差异百分比）
    diff = cv2.absdiff(gray1, gray2)
    diff_percent = (np.sum(diff) / (diff.size * 255)) * 100
    similarity = 100 - diff_percent
    
    return similarity, f"MSE={mse:.2f}, 相似度={similarity:.2f}%"

def main():
    if len(sys.argv) < 4:
        print("用法: python verify_frame_timing.py <video_path> <frames_dir> <timestamp_ms1> [timestamp_ms2] ...")
        print("示例: python verify_frame_timing.py 'G:\\Video\\test.mp4' 'temp\\pipeline_xxx\\frames' 342000 343000")
        sys.exit(1)
    
    video_path = sys.argv[1]
    frames_dir = sys.argv[2]
    timestamps = [int(ts) for ts in sys.argv[3:]]
    
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        sys.exit(1)
    
    if not os.path.exists(frames_dir):
        print(f"错误: 帧目录不存在: {frames_dir}")
        sys.exit(1)
    
    print("="*80)
    print("帧时间戳验证工具")
    print("="*80)
    print(f"视频: {video_path}")
    print(f"帧目录: {frames_dir}")
    print(f"测试时间戳: {timestamps}")
    print()
    
    # 创建临时目录存放验证帧
    verify_dir = "temp/verify_frames"
    os.makedirs(verify_dir, exist_ok=True)
    
    results = []
    
    for ts in timestamps:
        print(f"\n检查时间戳 {ts}ms ({ts/1000:.1f}s):")
        print("-" * 80)
        
        # 1. 检查提取的帧
        extracted_frame = os.path.join(frames_dir, f"frame_{ts}.jpg")
        if not os.path.exists(extracted_frame):
            print(f"  ✗ 提取的帧不存在: {extracted_frame}")
            results.append((ts, False, "帧不存在"))
            continue
        
        print(f"  ✓ 找到提取的帧: {os.path.basename(extracted_frame)}")
        
        # 2. 从视频中精确提取该时间点的帧
        verify_frame = os.path.join(verify_dir, f"verify_{ts}.jpg")
        print("  正在从视频提取验证帧...")
        
        if not extract_frame_at_timestamp(video_path, ts, verify_frame):
            print("  ✗ 无法从视频提取验证帧")
            results.append((ts, False, "无法提取验证帧"))
            continue
        
        print("  ✓ 验证帧已提取")
        
        # 3. 比较两帧
        similarity, details = compare_frames(extracted_frame, verify_frame)
        
        if similarity is None:
            print(f"  ✗ 无法比较帧: {details}")
            results.append((ts, False, details))
            continue
        
        # 判断是否匹配（相似度 > 95% 认为是同一帧）
        if similarity > 95:
            print(f"  ✓ 帧匹配! {details}")
            results.append((ts, True, details))
        elif similarity > 85:
            print(f"  ⚠ 帧相似但可能有偏移: {details}")
            results.append((ts, "warning", details))
        else:
            print(f"  ✗ 帧不匹配! {details}")
            results.append((ts, False, details))
        
        # 如果不匹配，尝试前后几帧
        if similarity < 95:
            print("\n  尝试前后偏移...")
            best_offset = 0
            best_similarity = similarity
            
            for offset in [-2000, -1000, 1000, 2000]:  # ±1-2秒
                test_ts = ts + offset
                test_frame = os.path.join(frames_dir, f"frame_{test_ts}.jpg")
                
                if os.path.exists(test_frame):
                    test_verify = os.path.join(verify_dir, f"verify_{test_ts}.jpg")
                    if extract_frame_at_timestamp(video_path, test_ts, test_verify):
                        test_sim, _ = compare_frames(test_frame, test_verify)
                        if test_sim and test_sim > best_similarity:
                            best_similarity = test_sim
                            best_offset = offset
            
            if best_offset != 0:
                print(f"  ⚠ 发现偏移: 实际帧可能在 {ts + best_offset}ms (偏移 {best_offset}ms, 相似度 {best_similarity:.2f}%)")
    
    # 总结
    print("\n" + "="*80)
    print("验证结果总结:")
    print("="*80)
    
    matched = sum(1 for _, status, _ in results if status == True)
    warnings = sum(1 for _, status, _ in results if status == "warning")
    failed = sum(1 for _, status, _ in results if status == False)
    
    print(f"总计: {len(results)} 个时间戳")
    print(f"  ✓ 匹配: {matched}")
    print(f"  ⚠ 警告: {warnings}")
    print(f"  ✗ 不匹配: {failed}")
    
    if failed > 0:
        print("\n⚠️ 发现帧时间戳不准确！")
        print("原因可能是:")
        print("  1. FFmpeg的fps过滤器在长视频中产生累积误差")
        print("  2. 视频的GOP结构导致精确定位困难")
        print("\n建议:")
        print("  - 使用更精确的帧提取方法（select过滤器）")
        print("  - 或者使用直接时间戳定位(-ss)而不是按间隔提取")

if __name__ == "__main__":
    main()
