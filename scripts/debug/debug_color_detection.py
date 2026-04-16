"""
颜色检测可视化工具 - 帮助调整 HSV 颜色范围
"""
import cv2
import yaml
import numpy as np
import sys
from pathlib import Path

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def load_config(game_name: str) -> dict:
    """加载游戏配置"""
    config_path = Path(f"config/games/{game_name}.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def visualize_color_detection(image_path: str, game_name: str = "battlefield6"):
    """可视化颜色检测"""
    
    print("="*60)
    print(" 颜色检测可视化工具")
    print("="*60)
    
    # 加载配置
    config = load_config(game_name)
    detection_cfg = config.get('detection', {})
    roi = detection_cfg.get('killfeed_roi', [0, 0, 1, 1])
    colors = detection_cfg.get('colors', {})
    
    print(f"\n配置信息:")
    print(f"  ROI: {roi}")
    print(f"  定义的颜色数: {len(colors)}")
    
    # 加载图片
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"错误: 无法加载图片 {image_path}")
        return
    
    h, w = frame.shape[:2]
    print(f"  图片尺寸: {w}x{h}")
    
    # 计算 ROI 像素坐标
    x, y, w_roi, h_roi = roi
    x1 = int(x * w)
    y1 = int(y * h)
    x2 = int((x + w_roi) * w)
    y2 = int((y + h_roi) * h)
    
    print(f"\nROI 像素坐标: ({x1}, {y1}) 到 ({x2}, {y2})")
    print(f"ROI 尺寸: {x2-x1}x{y2-y1}")
    
    # 裁剪 ROI
    roi_img = frame[y1:y2, x1:x2]
    
    # 创建可视化图像
    vis_img = frame.copy()
    
    # 绘制 ROI 矩形
    cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.putText(vis_img, "ROI", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # 转换 ROI 到 HSV
    roi_hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
    
    print("\n"+"="*60)
    print(" 颜色检测结果")
    print("="*60)
    
    # 为每个颜色创建掩码
    all_masks = []
    
    for color_name, color_cfg in colors.items():
        print(f"\n[{color_name}]")
        
        # 获取 HSV 范围
        hsv_lower = color_cfg.get('hsv_lower', color_cfg.get('lower', [0, 0, 0]))
        hsv_upper = color_cfg.get('hsv_upper', color_cfg.get('upper', [179, 255, 255]))
        tolerance = color_cfg.get('tolerance', 0)
        
        print(f"  HSV下限: {hsv_lower}")
        print(f"  HSV上限: {hsv_upper}")
        print(f"  容差: {tolerance}")
        
        # 应用容差
        if tolerance > 0:
            hsv_lower = [max(0, hsv_lower[0] - tolerance), max(0, hsv_lower[1] - tolerance), max(0, hsv_lower[2] - tolerance)]
            hsv_upper = [min(179, hsv_upper[0] + tolerance), min(255, hsv_upper[1] + tolerance), min(255, hsv_upper[2] + tolerance)]
            print(f"  应用容差后:")
            print(f"    下限: {hsv_lower}")
            print(f"    上限: {hsv_upper}")
        
        # 创建掩码
        lower = np.array(hsv_lower, dtype=np.uint8)
        upper = np.array(hsv_upper, dtype=np.uint8)
        mask = cv2.inRange(roi_hsv, lower, upper)
        
        # 计算匹配百分比
        match_pixels = np.count_nonzero(mask)
        total_pixels = mask.size
        match_percent = match_pixels / total_pixels if total_pixels > 0 else 0
        
        print(f"  匹配像素: {match_pixels}/{total_pixels} = {match_percent:.4%}")
        
        all_masks.append((color_name, mask, match_percent))
    
    # 保存可视化结果
    output_dir = Path("temp/color_debug")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # 1. 原图 + ROI 框
    cv2.imwrite(str(output_dir / "01_original_with_roi.jpg"), vis_img)
    print(f"\n已保存: {output_dir}/01_original_with_roi.jpg")
    
    # 2. ROI 裁剪
    cv2.imwrite(str(output_dir / "02_roi_cropped.jpg"), roi_img)
    print(f"已保存: {output_dir}/02_roi_cropped.jpg")
    
    # 3. ROI HSV
    roi_hsv_vis = cv2.cvtColor(roi_hsv, cv2.COLOR_HSV2BGR)
    cv2.imwrite(str(output_dir / "03_roi_hsv.jpg"), roi_hsv_vis)
    print(f"已保存: {output_dir}/03_roi_hsv.jpg")
    
    # 4. 各颜色掩码
    for i, (color_name, mask, percent) in enumerate(all_masks, 1):
        # 保存掩码
        cv2.imwrite(str(output_dir / f"04_mask_{color_name}.jpg"), mask)
        
        # 创建彩色覆盖
        colored_mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        colored_mask[:, :, 0] = 0  # 去除蓝色通道
        overlay = cv2.addWeighted(roi_img, 0.7, colored_mask, 0.3, 0)
        cv2.imwrite(str(output_dir / f"05_overlay_{color_name}.jpg"), overlay)
        
        print(f"已保存: {output_dir}/04_mask_{color_name}.jpg")
        print(f"已保存: {output_dir}/05_overlay_{color_name}.jpg")
    
    # 5. ROI 的 HSV 通道分解
    h_channel, s_channel, v_channel = cv2.split(roi_hsv)
    cv2.imwrite(str(output_dir / "06_h_channel.jpg"), h_channel)
    cv2.imwrite(str(output_dir / "07_s_channel.jpg"), s_channel)
    cv2.imwrite(str(output_dir / "08_v_channel.jpg"), v_channel)
    print(f"已保存: HSV 通道图 (H, S, V)")
    
    # 6. 采样 ROI 中心点的 HSV 值
    roi_h, roi_w = roi_img.shape[:2]
    center_y, center_x = roi_h // 2, roi_w // 2
    
    # 采样多个点
    sample_points = [
        ("中心", center_y, center_x),
        ("左上", roi_h // 4, roi_w // 4),
        ("右上", roi_h // 4, roi_w * 3 // 4),
        ("左下", roi_h * 3 // 4, roi_w // 4),
        ("右下", roi_h * 3 // 4, roi_w * 3 // 4),
    ]
    
    print(f"\n" + "="*60)
    print(" ROI 采样点 HSV 值")
    print("="*60)
    
    for name, py, px in sample_points:
        if 0 <= py < roi_h and 0 <= px < roi_w:
            hsv_val = roi_hsv[py, px]
            bgr_val = roi_img[py, px]
            print(f"{name} ({px}, {py}):")
            print(f"  BGR: {bgr_val}")
            print(f"  HSV: H={hsv_val[0]}, S={hsv_val[1]}, V={hsv_val[2]}")
    
    print(f"\n" + "="*60)
    print(" 建议")
    print("="*60)
    
    # 找出匹配率最低的颜色
    if all_masks:
        worst_color = min(all_masks, key=lambda x: x[2])
        if worst_color[2] < 0.01:  # 小于 1%
            print(f"\n颜色 '{worst_color[0]}' 匹配率极低 ({worst_color[2]:.4%})")
            print(f"建议:")
            print(f"  1. 查看生成的图片，特别是 04_mask_{worst_color[0]}.jpg")
            print(f"  2. 使用上面的采样点 HSV 值来调整配置")
            print(f"  3. 扩大 HSV 范围或增加 tolerance 值")
            print(f"  4. 如果 ROI 中根本没有这个颜色，可以考虑禁用颜色预过滤")
    
    print(f"\n所有可视化文件已保存到: {output_dir}/")
    print(f"请检查这些图片来诊断颜色检测问题。")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="颜色检测可视化工具")
    parser.add_argument("--image", "-i", default="temp/frame_285000.jpg",
                       help="测试图片路径")
    parser.add_argument("--game", "-g", default="battlefield6",
                       help="游戏名称")
    
    args = parser.parse_args()
    
    try:
        visualize_color_detection(args.image, args.game)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
