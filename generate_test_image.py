"""
生成带文字的测试图片用于 OCR 调试
"""
from PIL import Image, ImageDraw, ImageFont
import os

# 创建 temp/uploads 目录
os.makedirs("temp/uploads", exist_ok=True)

# 创建图片 (1920x1080, 模拟游戏截图尺寸)
width, height = 1920, 1080
image = Image.new('RGB', (width, height), color=(30, 30, 40))

draw = ImageDraw.Draw(image)

# 尝试使用系统字体
try:
    # Windows 中文字体
    font_large = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 60)
    font_medium = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 40)
except:
    try:
        # 备选字体
        font_large = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 60)
        font_medium = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40)
    except:
        # 使用默认字体
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()

# 在不同位置绘制文字（模拟游戏击杀提示）
texts = [
    ("击杀 +100", (800, 200), (255, 255, 0), font_large),  # 黄色，大字
    ("KILL", (900, 280), (255, 50, 50), font_large),  # 红色
    ("多重击杀", (850, 360), (255, 100, 0), font_medium),  # 橙色
    ("Double Kill", (820, 420), (255, 255, 255), font_medium),  # 白色
    ("连杀奖励 +50", (780, 500), (100, 255, 100), font_medium),  # 绿色
    ("ELIMINATED", (830, 580), (200, 200, 200), font_medium),  # 灰色
]

# 绘制背景框（让文字更清晰）
for text, pos, color, font in texts:
    # 获取文字边界框
    bbox = draw.textbbox(pos, text, font=font)
    padding = 10
    # 绘制半透明背景
    draw.rectangle(
        [bbox[0]-padding, bbox[1]-padding, bbox[2]+padding, bbox[3]+padding],
        fill=(0, 0, 0, 128)
    )
    # 绘制文字
    draw.text(pos, text, fill=color, font=font)

# 添加一些装饰线条（模拟游戏UI）
draw.rectangle([750, 150, 1150, 650], outline=(100, 100, 150), width=3)
draw.line([(750, 320), (1150, 320)], fill=(80, 80, 120), width=2)

# 保存图片
output_path = "temp/uploads/test_ocr_image.jpg"
image.save(output_path, quality=95)

print(f"✅ 测试图片已生成: {output_path}")
print(f"   尺寸: {width}x{height}")
print(f"   包含文字: {len(texts)} 条")
print("\n文字内容:")
for i, (text, _, _, _) in enumerate(texts, 1):
    print(f"  {i}. {text}")
