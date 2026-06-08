#!/usr/bin/env python3
"""快速测试：使用修复后的 KillDetector 处理单帧"""
import cv2
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai.kill_detector import KillDetector
from ai.yolo_detector import YoloDetector
from ai.opencv_matcher import OpenCVMatcher
from config.config_loader import ConfigLoader
from ultralytics import YOLO

# 加载配置
config_loader = ConfigLoader()
config = config_loader.load_config("battlefield6")

# 初始化检测器
model = YOLO("models/yolov8n.pt")
yolo_detector = YoloDetector(model, batch_size=1)
opencv_matcher = OpenCVMatcher(config)
kill_detector = KillDetector(yolo_detector, opencv_matcher, config, ocr_detector=None)

# 测试帧
test_frame_path = r"C:\Users\ediga\code\fpsvideosnap\temp\pipeline_7a917b9e\frames\frame_285000.jpg"
frame = cv2.imread(test_frame_path)
timestamp_ms = 285000

print("测试帧:", test_frame_path)
print("尺寸:", frame.shape if frame is not None else "None")

# 执行检测
if frame is not None:
    result = kill_detector.process_frame(frame)
    result['timestamp_ms'] = timestamp_ms
    print("\n" + "="*60)
    print(f"检测结果: {'击杀 ✓' if result['is_kill'] else '非击杀 ✗'}")
    print(f"置信度: {result['confidence']:.3f}")
    print("信号得分:")
    for key, value in result.get('signals', {}).items():
        print(f"  {key}: {value:.3f}")
    print("="*60)
else:
    print("❌ 无法读取帧")
