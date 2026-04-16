"""
测试新的精确时间戳提取方法
提取几个关键帧并验证与视频实际画面的匹配度
"""

import cv2
import numpy as np
import subprocess
import os
import sys

def get_frame_from_video(video_path: str, timestamp_sec: float) -> np.ndarray:
    """直接从视频中读取指定时间戳的帧（用于对比）"""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError(f"Failed to read frame at {timestamp_sec}s")
    return frame

def compare_frames(img1: np.ndarray, img2: np.ndarray) -> tuple[float, float]:
    """比较两帧的相似度，返回 (SSIM百分比, MSE)"""
    # 计算均方误差 (MSE)
    mse = np.mean((img1.astype(float) - img2.astype(float)) ** 2)
    
    # 简单的相似度：基于像素差异
    max_val = 255.0 ** 2
    similarity = (1 - (mse / max_val)) * 100
    
    return similarity, mse

def test_extraction():
    # 配置
    video_path = "G:/Video/Battlefield 6/Battlefield 6 2026.01.12 - 22.49.03.14.mp4"
    output_dir = "temp/test_precise_frames"
    
    # 测试时间点（选择之前有问题的区域）
    test_timestamps = [
        100,   # 100秒
        200,   # 200秒
        300,   # 300秒
        342,   # 之前发现问题的时间点
        343,   # 之前发现问题的时间点
        500,   # 500秒
    ]
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    print(f"测试视频: {os.path.basename(video_path)}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)
    
    # 导入新的 FrameExtractor
    sys.path.insert(0, os.path.dirname(__file__))
    from src.video.frame_extractor import FrameExtractor
    
    extractor = FrameExtractor(hwaccel="cuda")
    
    results = []
    
    for ts_sec in test_timestamps:
        ts_ms = ts_sec * 1000
        output_path = os.path.join(output_dir, f"frame_{ts_ms}.jpg")
        
        print(f"\n测试时间戳: {ts_sec}s ({ts_ms}ms)")
        
        # 使用新方法提取
        try:
            extractor.extract_single_frame(video_path, ts_ms, output_path)
            extracted_frame = cv2.imread(output_path)
            
            # 直接从视频读取对比
            video_frame = get_frame_from_video(video_path, ts_sec)
            
            # 比较相似度
            similarity, mse = compare_frames(extracted_frame, video_frame)
            
            result = {
                'timestamp_sec': ts_sec,
                'similarity': similarity,
                'mse': mse,
                'passed': similarity > 95.0  # 期望 >95% 相似度
            }
            results.append(result)
            
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"  相似度: {similarity:.2f}%  MSE: {mse:.2f}  {status}")
            
        except Exception as e:
            print(f"  ❌ 提取失败: {e}")
            results.append({
                'timestamp_sec': ts_sec,
                'error': str(e),
                'passed': False
            })
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结:")
    passed = sum(1 for r in results if r.get('passed', False))
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("✅ 所有测试通过！新的精确提取方法工作正常。")
        return 0
    else:
        print("❌ 部分测试失败，需要进一步调试。")
        return 1

if __name__ == "__main__":
    exit(test_extraction())
