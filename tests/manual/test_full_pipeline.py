"""
模拟主程序完整流程的测试脚本
测试从视频提取帧到击杀检测的完整流程
"""
import cv2
import yaml
import sys
from pathlib import Path
from ultralytics import YOLO

# 设置控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.ai.kill_detector import KillDetector
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.ocr_detector import OCRDetector

print("="*60)
print(" 完整流程测试")
print("="*60)

# 1. 加载配置
print("\n[1] 加载配置...")
with open('config/games/battlefield6.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

detection_cfg = config.get('detection', {})
print(f"  ✓ 置信度阈值: {detection_cfg.get('confidence_threshold', 0.5)}")
print(f"  ✓ ROI: {detection_cfg.get('killfeed_roi')}")
print(f"  ✓ 颜色预过滤阈值: {detection_cfg.get('prefilter', {}).get('color_threshold', 0.01)}")

# 2. 初始化检测器
print("\n[2] 初始化检测器...")

# YOLO
model = YOLO("models/yolov8n.pt")
yolo = YoloDetector(model=model, confidence_threshold=0.25)
print("  ✓ YOLO 就绪")

# OpenCV
opencv_matcher = OpenCVMatcher(config=config)
template_dir = "models/templates/battlefield6"
if Path(template_dir).exists():
    opencv_matcher.load_templates(template_dir)
print(f"  ✓ OpenCV 就绪 ({len(opencv_matcher.templates)} 个模板)")

# OCR
ocr_cfg = detection_cfg.get('ocr', {})
if ocr_cfg.get('enabled', False):
    ocr = OCRDetector(lang='ch', use_gpu=True)
    print("  ✓ OCR 就绪")
else:
    ocr = None
    print("  ! OCR 未启用")

# Kill Detector
kill_detector = KillDetector(
    yolo_detector=yolo,
    opencv_matcher=opencv_matcher,
    game_config=config,
    ocr_detector=ocr
)
print("  ✓ 击杀检测器就绪")

# 3. 加载测试帧
print("\n[3] 加载测试帧...")
test_frame = cv2.imread('temp/frame_285000.jpg')
if test_frame is None:
    print("  ✗ 无法加载测试帧")
    sys.exit(1)

print(f"  ✓ 已加载: temp/frame_285000.jpg")
print(f"  ✓ 尺寸: {test_frame.shape}")

# 4. 单帧测试
print("\n[4] 单帧检测测试...")
result = kill_detector.process_frame(test_frame)

print(f"\n  结果:")
print(f"    是否击杀: {result['is_kill']}")
print(f"    置信度: {result['confidence']:.3f}")
print(f"    信号得分:")
for name, score in result['signals'].items():
    print(f"      {name}: {score:.3f}")

if not result['is_kill']:
    print("\n  ✗ 单帧测试失败!")
    print("  → 主程序也不会检测到这一帧")
    sys.exit(1)

print("\n  ✓ 单帧测试成功!")

# 5. 批处理测试
print("\n[5] 批处理检测测试...")
print("  模拟主程序的批处理流程...")

# 创建一个包含测试帧的批次（重复几次来测试）
test_frames = [test_frame] * 3
timestamps = [285000, 285033, 285066]  # 假设 30fps

print(f"  ✓ 测试批次: {len(test_frames)} 帧")

events = kill_detector.process_video_batch(test_frames, timestamps)

print(f"\n  批处理结果: 检测到 {len(events)} 个击杀事件")

if len(events) == 0:
    print("\n  ✗ 批处理测试失败!")
    print("  → 这就是为什么主程序显示 'No kills detected'")
    print("\n  调试信息:")
    
    # 详细测试预过滤
    print("\n  [预过滤测试]")
    prefilter_passed = kill_detector._prefilter(test_frame)
    print(f"    预过滤结果: {prefilter_passed}")
    
    if not prefilter_passed:
        print("    → 预过滤失败，帧被跳过!")
        
        # 检查颜色检测
        colors = detection_cfg.get('colors', {})
        print(f"\n    颜色配置: {list(colors.keys())}")
        
        for color_name, color_cfg in colors.items():
            print(f"\n    [{color_name}]")
            print(f"      配置: {color_cfg}")
            
            hsv_lower = color_cfg.get('hsv_lower', color_cfg.get('lower'))
            hsv_upper = color_cfg.get('hsv_upper', color_cfg.get('upper'))
            tolerance = color_cfg.get('tolerance', 0)
            
            if hsv_lower and hsv_upper:
                if tolerance > 0:
                    hsv_lower_adj = [max(0, hsv_lower[0] - tolerance), max(0, hsv_lower[1] - tolerance), max(0, hsv_lower[2] - tolerance)]
                    hsv_upper_adj = [min(179, hsv_upper[0] + tolerance), min(255, hsv_upper[1] + tolerance), min(255, hsv_upper[2] + tolerance)]
                else:
                    hsv_lower_adj = hsv_lower
                    hsv_upper_adj = hsv_upper
                
                roi = detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
                pct = opencv_matcher.detect_color(test_frame, hsv_lower_adj, hsv_upper_adj, roi=roi)
                print(f"      颜色匹配: {pct:.4%}")
                print(f"      阈值: {detection_cfg.get('prefilter', {}).get('color_threshold', 0.01):.4%}")
                print(f"      通过: {'是' if pct >= detection_cfg.get('prefilter', {}).get('color_threshold', 0.01) else '否'}")
    else:
        print("    → 预过滤通过，但后续检测失败")
        
        # 测试精确检测
        print("\n  [精确检测测试]")
        signals = kill_detector._precise_detect(test_frame)
        print(f"    信号得分:")
        for name, score in signals.items():
            print(f"      {name}: {score:.3f}")
        
        final_conf = kill_detector._calculate_confidence(signals)
        threshold = detection_cfg.get('confidence_threshold', 0.5)
        print(f"\n    最终置信度: {final_conf:.3f}")
        print(f"    检测阈值: {threshold}")
        print(f"    通过: {'是' if final_conf >= threshold else '否'}")
    
    sys.exit(1)

print("\n  ✓ 批处理测试成功!")

for i, event in enumerate(events, 1):
    print(f"\n  事件 {i}:")
    print(f"    时间戳: {event['timestamp_ms']}ms")
    print(f"    置信度: {event['confidence']:.3f}")
    print(f"    信号: {event['signals']}")

# 6. 总结
print("\n" + "="*60)
print(" 测试总结")
print("="*60)
print("\n✓ 所有测试通过!")
print("  单帧检测: 成功")
print("  批处理检测: 成功")
print(f"  检测到事件数: {len(events)}")
print("\n如果主程序还是显示 'No kills detected'，")
print("可能的原因:")
print("  1. 视频中的帧和测试帧不同")
print("  2. 主程序使用了不同的配置文件")
print("  3. 主程序在初始化时出现了问题")
print("  4. 需要检查 pipeline.py 中的具体实现")
