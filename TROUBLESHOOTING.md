# 故障排除指南 (TROUBLESHOOTING.md)

在使用 FPS Video Snap 过程中，如果你遇到了问题，请参考以下常见问题及解决方法。

---

## 1. 视频处理相关

### ❌ 错误: `ffmpeg` not found
**现象**: 程序运行报错或提示无法找到 FFmpeg。
**解决**:
- 确保已按照 [INSTALL.md](INSTALL.md) 安装 FFmpeg。
- 将 FFmpeg 的 `bin` 目录路径正确添加到 Windows 环境变量 `PATH` 中。
- 在命令提示符下运行 `ffmpeg -version` 以测试。

### ❌ 视频拼接失败或输出视频只有声音/黑屏
**解决**:
- 检查 `config/default_config.yaml` 中的 `encoder` 设置。如果是普通显卡或 CPU，尝试将 `h264_nvenc` 更改为 `libx264`。
- 确保输入视频路径不包含特殊字符或超长路径。

---

## 2. AI 识别与 GPU 相关

### ❌ 错误: Out of Memory (OOM)
**现象**: 推理过程中程序崩溃，提示显存不足。
**解决**:
- 在配置文件中减小 `detection -> batch_size` 的值（例如从 16 减小到 4 或 2）。
- 关闭后台占用大量显存的其他程序（如正在运行的游戏或浏览器）。

### ❌ 提示 CUDA 不可用，走 CPU 速度极慢
**现象**: `torch` 警告无法加载 CUDA 驱动。
**解决**:
- 运行 `python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`（具体版本取决于你的驱动）。
- 确保 NVIDIA 驱动已更新至最新版本。

---

## 3. 识别精度相关

### ❓ 问题: 漏掉了很多击杀画面
**解决**:
- 检查 `detection -> confidence_threshold`。如果模型认为击杀不够明显（如录像分辨率低），尝试降低此值。
- 检查 `config/games/xxx.yaml` 中的 `ui_roi`。如果 UI 位置偏移，AI 可能检测不到。

### ❓ 问题: 识别了很多不是击杀的画面
**解决**:
- 提高 `confidence_threshold`。
- 在 `ui_roi` 中更精确地框选击杀反馈区域，减少周围环境干扰。

---

## 4. PaddleOCR Initialization Errors (Config Assistant)

### Symptom
When running `python main.py config-assistant`, you see errors like:
- `Failed to initialize PaddleOCR`
- `OSError: [WinError 127] ... cudnn_cnn64_9.dll`
- Traceback showing `C:\Users\...\Miniconda3\Lib\site-packages\...`

### Cause
This usually means you're running with the wrong Python interpreter (system/conda Python instead of the project's virtual environment).

### Solution

#### 1. Verify your Python interpreter
```cmd
where python
python -c "import sys; print(sys.executable)"
```

If the output shows `Miniconda3`, `Anaconda`, or a system path instead of `.venv`, you're using the wrong interpreter.

#### 2. Use the correct interpreter
Always run with the project's virtual environment:
```cmd
.venv\Scripts\python.exe main.py config-assistant --port 8080
```

#### 3. If OCR still fails: Install .venv_paddle

For Config Assistant's OCR preview feature, you may need a separate PaddleOCR environment:

**For GPU machines (NVIDIA with CUDA):**
```cmd
uv venv --python 3.12.11 .venv_paddle
uv pip install --python .venv_paddle -r requirements-win-paddleocr-gpu-standalone.txt
```

**For CPU-only machines:**
```cmd
uv venv --python 3.12.11 .venv_paddle
uv pip install --python .venv_paddle paddlepaddle paddleocr numpy opencv-python
```

#### 4. If you don't need OCR
Config Assistant will work without OCR - you just won't be able to preview OCR detection. All other features (ROI configuration, color picking, template management) work normally.

---

## 5. 获取更多帮助


如果以上方法无法解决问题：
1. 开启调试模式运行：`--debug`，查看 `temp/` 目录下的中间帧。
2. 检查 `output/process_report.json` 获取详细处理流水。
3. 在 GitHub 提交 Issue，附带你的系统配置、报错信息和 `default_config.yaml` 内容。
