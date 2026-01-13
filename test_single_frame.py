"""
简单的单帧击杀检测测试
"""
import cv2
import yaml
from pathlib import Path
from ultralytics import YOLO

from src.ai.kill_detector import KillDetector
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.ocr_detector import OCRDetector

# 加载配置
with open('config/games/battlefield6.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 加载图片
frame = cv2.imread('temp/frame_285000.jpg')
print(f"图片尺寸: {frame.shape}")

# 初始化检测器
print("\n初始化检测器...")
model = YOLO("models/yolov8n.pt")
yolo = YoloDetector(model=model, confidence_threshold=0.25)

opencv_matcher = OpenCVMatcher(config=config)
template_dir = "models/templates/battlefield6"
if Path(template_dir).exists():
    opencv_matcher.load_templates(template_dir)
print(f"加载了 {len(opencv_matcher.templates)} 个模板")

ocr = OCRDetector(lang='ch', use_gpu=True)

kill_detector = KillDetector(
    yolo_detector=yolo,
    opencv_matcher=opencv_matcher,
    game_config=config,
    ocr_detector=ocr
)

# 处理帧
print("\n处理帧...")
result = kill_detector.process_frame(frame)

print(f"\n结果:")
print(f"  是否击杀: {result['is_kill']}")
print(f"  置信度: {result['confidence']:.3f}")
print(f"  信号得分:")
for name, score in result['signals'].items():
    print(f"    {name}: {score:.3f}")
