"""
手动 OCR 测试脚本
用于独立测试 OCR 功能，不依赖 Web 服务器
"""
import os
import sys
import cv2

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools.config_assistant.ocr_service import ocr_service
from src.utils.logger import get_logger

logger = get_logger("test_ocr")

def test_ocr_basic():
    """测试基本 OCR 功能"""
    print("\n" + "="*60)
    print("测试 1: 检查 OCR 服务初始化")
    print("="*60)
    
    if ocr_service._detector is None:
        print("❌ OCR Detector 未初始化!")
        print("   可能原因：")
        print("   1. PaddleOCR 或 EasyOCR 未安装")
        print("   2. 依赖库缺失")
        return False
    else:
        print("✅ OCR Detector 已成功初始化")
        print(f"   Detector 类型: {type(ocr_service._detector).__name__}")
    
    return True

def test_ocr_with_image(image_path, roi=None):
    """测试指定图片的 OCR"""
    print("\n" + "="*60)
    print(f"测试 2: OCR 识别测试")
    print("="*60)
    print(f"图片路径: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"❌ 图片文件不存在: {image_path}")
        return
    
    # 检查图片是否可读
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ 无法加载图片: {image_path}")
        return
    
    h, w = image.shape[:2]
    print(f"✅ 图片已加载: {w}x{h} 像素")
    
    if roi:
        print(f"   ROI (相对): {roi}")
        rx, ry, rw, rh = roi
        px, py, pw, ph = int(rx*w), int(ry*h), int(rw*w), int(rh*h)
        print(f"   ROI (像素): [{px}, {py}, {pw}, {ph}]")
        
        # 裁剪并保存 ROI 区域用于检查
        roi_img = image[py:py+ph, px:px+pw]
        roi_save_path = "temp/ocr_test_roi.png"
        os.makedirs("temp", exist_ok=True)
        cv2.imwrite(roi_save_path, roi_img)
        print(f"   ROI 区域已保存到: {roi_save_path}")
    
    print("\n正在运行 OCR 检测...")
    try:
        results = ocr_service.detect(image_path, roi)
        print(f"\n✅ OCR 完成! 识别到 {len(results)} 个文本")
        
        if len(results) > 0:
            print("\n识别结果:")
            print("-" * 60)
            for i, result in enumerate(results, 1):
                text = result.get('text', '')
                confidence = result.get('confidence', 0)
                bbox = result.get('bbox', [])
                print(f"{i}. 文本: '{text}'")
                print(f"   置信度: {confidence:.2f}")
                if bbox:
                    print(f"   位置: {bbox}")
            print("-" * 60)
        else:
            print("\n⚠️ 未识别到任何文本")
            print("   可能原因：")
            print("   1. 图片中没有清晰的文字")
            print("   2. ROI 区域选择不正确")
            print("   3. 文字颜色与背景对比度不够")
            print("   4. OCR 引擎不支持该语言")
            
    except Exception as e:
        print(f"\n❌ OCR 检测失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("FPS Video Snap - OCR 功能测试")
    print("="*60)
    
    # 测试 1: 检查初始化
    if not test_ocr_basic():
        print("\n❌ OCR 服务未正确初始化，无法继续测试")
        return
    
    # 测试 2: 让用户指定测试图片
    print("\n" + "="*60)
    print("请提供测试图片路径")
    print("="*60)
    
    # 检查 temp/uploads 目录中的图片
    upload_dir = "temp/uploads"
    if os.path.exists(upload_dir):
        files = [f for f in os.listdir(upload_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if files:
            print(f"\n找到 {len(files)} 个上传的图片:")
            for i, f in enumerate(files, 1):
                print(f"  {i}. {f}")
            
            # 使用最新的图片
            latest_file = max([os.path.join(upload_dir, f) for f in files], key=os.path.getmtime)
            print(f"\n使用最新上传的图片: {latest_file}")
            
            # 测试完整图片
            print("\n[测试场景 A] 完整图片识别")
            test_ocr_with_image(latest_file, roi=None)
            
            # 测试带 ROI
            print("\n[测试场景 B] ROI 区域识别")
            print("使用示例 ROI: [0.2, 0.5, 0.3, 0.2]")
            test_ocr_with_image(latest_file, roi=[0.2, 0.5, 0.3, 0.2])
            
        else:
            print("\n⚠️ temp/uploads 目录中没有图片")
    else:
        print("\n⚠️ temp/uploads 目录不存在")
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)

if __name__ == "__main__":
    main()
