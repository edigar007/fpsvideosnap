from setuptools import setup, find_packages

setup(
    name="fpsvideosnap",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "opencv-python",
        "PyYAML",
        "ultralytics",
        "torch",
        "torchvision",
        "torchaudio",
        "ffmpeg-python",
        "tqdm",
        "rich",
        "psutil",
        "flask",
        "Pillow"
    ],
    entry_points={
        "console_scripts": [
            "fpsvideosnap=main:main",
        ],
    },
    author="FPS Video Snap Team",
    description="AI-powered FPS gameplay kill highlight generator",
    keywords="fps, video, ai, yolo, kill detection, highlight",
    python_requires=">=3.10",
)
