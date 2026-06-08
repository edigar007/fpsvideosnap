"""
击杀检测调试脚本 - 逐步分析每个检测环节
用于诊断为什么某个帧没有被识别为击杀
"""
import cv2
import yaml
import sys
from pathlib import Path

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.ai.kill_detector import KillDetector
from src.ai.yolo_detector import YoloDetector
from src.ai.opencv_matcher import OpenCVMatcher
from src.ai.ocr_detector import OCRDetector

def load_config(game_name: str) -> dict:
    """加载游戏配置"""
    config_path = Path(f"config/games/{game_name}.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def debug_kill_detection(image_path: str, game_name: str = "battlefield6"):
    """
    详细调试击杀检测过程
    """
    print_section("FPS Video Snap - 击杀检测调试工具")
    
    # 1. 加载配置
    print_section("步骤 1: 加载配置")
    config = load_config(game_name)
    detection_cfg = config.get('detection', {})
    
    print(f"✅ 配置文件: config/games/{game_name}.yaml")
    print(f"   信心阈值: {detection_cfg.get('confidence_threshold', 0.5)}")
    print(f"   ROI 区域: {detection_cfg.get('killfeed_roi', [0, 0, 1, 1])}")
    
    # 2. 加载图片
    print_section("步骤 2: 加载测试图片")
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"❌ 无法加载图片: {image_path}")
        return
    
    h, w = frame.shape[:2]
    print(f"✅ 图片已加载: {image_path}")
    print(f"   尺寸: {w}x{h} 像素")
    
    # 3. 初始化检测器
    print_section("步骤 3: 初始化检测器")
    
    # YOLO
    print("初始化 YOLO 检测器...")
    from ultralytics import YOLO
    model = YOLO("models/yolov8n.pt")
    yolo = YoloDetector(model=model, confidence_threshold=0.25)
    print("✅ YOLO 已就绪")
    
    # OpenCV Matcher
    print("初始化 OpenCV 模板匹配器...")
    opencv_matcher = OpenCVMatcher(config=config)
    
    # 加载模板
    template_dir = f"models/templates/{game_name}"
    if Path(template_dir).exists():
        opencv_matcher.load_templates(template_dir)
    
    templates_loaded = len(opencv_matcher.templates)
    print(f"✅ OpenCV 已就绪 (加载了 {templates_loaded} 个模板)")
    if templates_loaded > 0:
        print(f"   模板列表: {list(opencv_matcher.templates.keys())}")
    
    # OCR
    ocr_cfg = detection_cfg.get('ocr', {})
    ocr_enabled = ocr_cfg.get('enabled', False)
    
    if ocr_enabled:
        print("初始化 OCR 检测器...")
        ocr = OCRDetector(
            lang=ocr_cfg.get('lang', 'ch'),
            use_gpu=ocr_cfg.get('use_gpu', True)
        )
        print("✅ OCR 已就绪")
    else:
        ocr = None
        print("⚠️ OCR 未启用")
    
    # Kill Detector
    print("初始化击杀检测器...")
    kill_detector = KillDetector(
        yolo_detector=yolo,
        opencv_matcher=opencv_matcher,
        game_config=config,
        ocr_detector=ocr
    )
    print("✅ 击杀检测器已就绪")
    
    # 4. 预过滤测试
    print_section("步骤 4: 颜色预过滤 (快速筛选)")
    
    prefilter_cfg = detection_cfg.get('prefilter', {})
    color_threshold = prefilter_cfg.get('color_threshold', 0.01)
    colors = detection_cfg.get('colors', {})
    
    print(f"颜色阈值: {color_threshold}")
    print(f"定义的颜色: {len(colors)} 个")
    
    if not colors:
        print("⚠️ 没有定义颜色，跳过预过滤")
        prefilter_passed = True
    else:
        max_color_pct = 0.0
        roi = detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
        
        for color_name, color_cfg in colors.items():
            # 支持两种配置格式: hsv_lower/hsv_upper 或 lower/upper
            hsv_lower = color_cfg.get('hsv_lower', color_cfg.get('lower'))
            hsv_upper = color_cfg.get('hsv_upper', color_cfg.get('upper'))
            tolerance = color_cfg.get('tolerance', 0)
            
            if hsv_lower and hsv_upper:
                # 应用容差
                if tolerance > 0:
                    hsv_lower = [max(0, hsv_lower[0] - tolerance), max(0, hsv_lower[1] - tolerance), max(0, hsv_lower[2] - tolerance)]
                    hsv_upper = [min(179, hsv_upper[0] + tolerance), min(255, hsv_upper[1] + tolerance), min(255, hsv_upper[2] + tolerance)]
                
                pct = opencv_matcher.detect_color(
                    frame, 
                    hsv_lower,
                    hsv_upper,
                    roi=roi
                )
                max_color_pct = max(max_color_pct, pct)
                print(f"   {color_name}: {pct:.2%} 匹配")
        
        prefilter_passed = max_color_pct >= color_threshold
        
        if prefilter_passed:
            print(f"✅ 预过滤通过 (最大颜色匹配: {max_color_pct:.2%} >= {color_threshold:.2%})")
        else:
            print(f"❌ 预过滤失败 (最大颜色匹配: {max_color_pct:.2%} < {color_threshold:.2%})")
            print("   → 由于颜色预过滤失败，不会进行后续的 AI 检测")
            return
    
    # 5. OCR 检测
    print_section("步骤 5: OCR 文字识别")
    
    ocr_conf = 0.0
    if ocr_enabled and ocr:
        keywords = ocr_cfg.get('keywords', ["击杀", "KILL"])
        similarity_threshold = ocr_cfg.get('similarity_threshold', 80)
        ocr_required = ocr_cfg.get('required', False)
        
        print(f"关键词: {keywords}")
        print(f"相似度阈值: {similarity_threshold}")
        print(f"OCR 必须: {'是' if ocr_required else '否'}")
        
        # 先检测所有文字
        roi = detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
        x, y, w_roi, h_roi = roi
        x_px = int(x * w)
        y_px = int(y * h)
        w_px = int(w_roi * w)
        h_px = int(h_roi * h)
        
        roi_px = [x_px, y_px, w_px, h_px]
        
        all_texts = ocr.detect_text(frame, roi=roi_px)
        print(f"\n识别到 {len(all_texts)} 个文本:")
        for i, text_info in enumerate(all_texts, 1):
            print(f"   {i}. '{text_info['text']}' (置信度: {text_info['confidence']:.2f})")
        
        # 查找关键词
        res = ocr.find_keywords(
            frame, 
            keywords, 
            roi=roi_px,
            threshold=similarity_threshold / 100.0
        )
        
        if res['found']:
            ocr_conf = res['confidence'] / 100.0 if res['confidence'] > 1.0 else res['confidence']
            print("\n✅ OCR 匹配成功!")
            print(f"   匹配关键词: {res['matched_keyword']}")
            print(f"   识别文本: {res['text']}")
            print(f"   OCR置信度: {res.get('ocr_confidence', 'N/A')}")
            print(f"   相似度: {res['similarity']:.2%}")
            print(f"   最终得分: {ocr_conf:.3f}")
        else:
            print("\n❌ OCR 未找到关键词")
            if ocr_required:
                print("   → 由于 OCR 是必须的且未匹配，击杀检测失败")
                return
    else:
        print("⚠️ OCR 检测被禁用，跳过")
    
    # 6. 模板匹配
    print_section("步骤 6: 模板匹配")
    
    max_template_conf = 0.0
    if opencv_matcher.templates:
        template_list = detection_cfg.get('templates', {})
        roi = detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
        
        if not template_list:
            print("使用所有已加载的模板")
            template_list = list(opencv_matcher.templates.keys())
        else:
            print(f"配置指定的模板: {list(template_list.keys())}")
            template_list = list(template_list.keys())
        
        print(f"\n检测 {len(template_list)} 个模板:")
        for t_name in template_list:
            try:
                _, score = opencv_matcher.match_template(frame, t_name, roi=roi)
                threshold = template_list.get(t_name, {}).get('threshold', 0.7) if isinstance(template_list, dict) else 0.7
                max_template_conf = max(max_template_conf, score)
                
                status = "✅" if score >= threshold else "❌"
                print(f"   {status} {t_name}: {score:.3f} (阈值: {threshold})")
            except Exception as e:
                print(f"   ❌ {t_name}: 错误 - {e}")
        
        print(f"\n最高模板得分: {max_template_conf:.3f}")
    else:
        print("⚠️ 没有加载模板，跳过")
    
    # 7. YOLO 检测
    print_section("步骤 7: YOLO 目标检测")
    
    yolo_detections = yolo.detect_single(frame)
    print(f"YOLO 检测到 {len(yolo_detections)} 个目标:")
    
    max_yolo_conf = 0.0
    kill_detections = []
    
    for d in yolo_detections:
        print(f"   - {d['name']}: {d['conf']:.3f} at {d['box']}")
        if d['name'] == 'kill':
            max_yolo_conf = max(max_yolo_conf, d['conf'])
            kill_detections.append(d)
    
    if kill_detections:
        print(f"\n✅ YOLO 检测到 {len(kill_detections)} 个击杀目标")
        print(f"   最高置信度: {max_yolo_conf:.3f}")
    else:
        print("\n❌ YOLO 未检测到击杀目标")
    
    # 8. 颜色检测 (精确)
    print_section("步骤 8: 颜色精确检测")
    
    max_color_conf = 0.0
    roi = detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
    
    if colors:
        print("重新计算颜色匹配得分:")
        for color_name, color_cfg in colors.items():
            # 支持两种配置格式: hsv_lower/hsv_upper 或 lower/upper
            hsv_lower = color_cfg.get('hsv_lower', color_cfg.get('lower'))
            hsv_upper = color_cfg.get('hsv_upper', color_cfg.get('upper'))
            tolerance = color_cfg.get('tolerance', 0)
            
            if hsv_lower and hsv_upper:
                # 应用容差
                if tolerance > 0:
                    hsv_lower = [max(0, hsv_lower[0] - tolerance), max(0, hsv_lower[1] - tolerance), max(0, hsv_lower[2] - tolerance)]
                    hsv_upper = [min(179, hsv_upper[0] + tolerance), min(255, hsv_upper[1] + tolerance), min(255, hsv_upper[2] + tolerance)]
                
                match_percent = opencv_matcher.detect_color(
                    frame,
                    hsv_lower,
                    hsv_upper,
                    roi=roi
                )
                # 根据 kill_detector.py 的逻辑: min(match_percent * 50, 1.0)
                color_score = min(match_percent * 50, 1.0)
                max_color_conf = max(max_color_conf, color_score)
                print(f"   {color_name}: {match_percent:.2%} → 得分: {color_score:.3f}")
        
        print(f"\n最高颜色得分: {max_color_conf:.3f}")
    else:
        print("⚠️ 没有定义颜色")
    
    # 9. 综合评分
    print_section("步骤 9: 综合评分计算")
    
    signals = {
        'ocr': ocr_conf,
        'template': max_template_conf,
        'color': max_color_conf,
        'yolo': max_yolo_conf
    }
    
    print("各信号得分:")
    for name, score in signals.items():
        print(f"   {name.upper()}: {score:.3f}")
    
    # 计算权重
    weights = detection_cfg.get('weights', {
        'ocr': 0.4,
        'template': 0.3,
        'color': 0.2,
        'yolo': 0.1
    })
    
    print("\n配置的权重:")
    for name, weight in weights.items():
        print(f"   {name.upper()}: {weight}")
    
    # 根据实际激活的信号重新计算权重
    active_weights = {}
    
    if ocr_enabled and ocr:
        active_weights['ocr'] = weights.get('ocr', 0.4)
    
    if opencv_matcher.templates:
        active_weights['template'] = weights.get('template', 0.3)
    
    active_weights['color'] = weights.get('color', 0.2)
    active_weights['yolo'] = weights.get('yolo', 0.1)
    
    total_weight = sum(active_weights.values())
    
    print(f"\n激活的权重 (总和: {total_weight}):")
    for name, weight in active_weights.items():
        normalized = weight / total_weight if total_weight > 0 else 0
        print(f"   {name.upper()}: {weight} → 归一化: {normalized:.3f}")
    
    # 计算最终得分
    final_conf = 0.0
    if total_weight > 0:
        print("\n加权计算:")
        for name, weight in active_weights.items():
            contrib = signals[name] * (weight / total_weight)
            final_conf += contrib
            print(f"   {name.upper()}: {signals[name]:.3f} × {weight/total_weight:.3f} = {contrib:.3f}")
    
    # 10. 最终判定
    print_section("步骤 10: 最终判定")
    
    conf_threshold = detection_cfg.get('confidence_threshold', 0.5)
    is_kill = final_conf >= conf_threshold
    
    print(f"最终置信度: {final_conf:.3f}")
    print(f"检测阈值: {conf_threshold}")
    print()
    
    if is_kill:
        print(f"✅ 判定为击杀! (置信度 {final_conf:.3f} >= 阈值 {conf_threshold})")
    else:
        print(f"❌ 未判定为击杀 (置信度 {final_conf:.3f} < 阈值 {conf_threshold})")
        print("\n差距分析:")
        print(f"   需要提高: {(conf_threshold - final_conf):.3f} 分")
        print("\n可能的改进方向:")
        
        # 给出改进建议
        suggestions = []
        if ocr_enabled and ocr_conf == 0:
            suggestions.append("- OCR 未匹配，检查关键词或降低相似度阈值")
        if max_template_conf < 0.5:
            suggestions.append("- 模板匹配得分低，可能需要更新模板或降低模板阈值")
        if max_color_conf < 0.3:
            suggestions.append("- 颜色检测得分低，可能需要调整 HSV 颜色范围")
        if max_yolo_conf == 0:
            suggestions.append("- YOLO 未检测到目标，可能需要重新训练模型")
        if final_conf > 0 and (conf_threshold - final_conf) < 0.1:
            suggestions.append("- 得分接近阈值，可以考虑降低 confidence_threshold")
        
        for s in suggestions:
            print(s)
    
    print_section("调试完成")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="击杀检测调试工具")
    parser.add_argument("--image", "-i", default="temp/uploads/frame_285000.jpg",
                       help="测试图片路径 (默认: temp/uploads/frame_285000.jpg)")
    parser.add_argument("--game", "-g", default="battlefield6",
                       help="游戏名称 (默认: battlefield6)")
    
    args = parser.parse_args()
    
    try:
        debug_kill_detection(args.image, args.game)
    except Exception as e:
        print(f"\n❌ 调试过程出错: {e}")
        import traceback
        traceback.print_exc()
