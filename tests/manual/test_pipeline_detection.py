#!/usr/bin/env python3
"""
测试 Pipeline 的检测阶段，使用已经提取的帧
"""
import os
import sys
import glob
import cv2
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.config_loader import ConfigLoader
from ai.model_manager import ModelManager
from ai.yolo_detector import YoloDetector
from ai.opencv_matcher import OpenCVMatcher
from ai.kill_detector import KillDetector
from utils.logger import logger

def main():
    # set_log_level("DEBUG")  # 注释掉，直接使用默认配置
    
    # 加载配置
    logger.info("加载配置...")
    config_loader = ConfigLoader()
    config = config_loader.load_config("battlefield6")
    
    # 找到已提取的帧
    frames_dir = r"C:\Users\ediga\code\fpsvideosnap\temp\pipeline_7a917b9e\frames"
    logger.info(f"读取帧目录: {frames_dir}")
    
    frame_files = sorted(glob.glob(os.path.join(frames_dir, "frame_*.jpg")))
    logger.info(f"找到 {len(frame_files)} 个帧")
    
    # 只测试包含 frame_285000 附近的几帧
    test_frames = [f for f in frame_files if "frame_280000.jpg" <= os.path.basename(f) <= "frame_290000.jpg"]
    logger.info(f"测试范围: {len(test_frames)} 个帧 (280000-290000ms)")
    
    if not test_frames:
        logger.error("未找到测试帧!")
        return
    
    # 初始化检测器
    logger.info("初始化检测器...")
    model_path = config.get("detection", {}).get("model_path", "models/yolov8n.pt")
    model_manager = ModelManager(config)
    model_manager.model_path = model_path
    yolo_model = model_manager.load_model()
    yolo_detector = YoloDetector(yolo_model, batch_size=16)
    opencv_matcher = OpenCVMatcher(config)
    kill_detector = KillDetector(yolo_detector, opencv_matcher, config)
    
    # Debug: 输出配置信息
    detection_cfg = config.get('detection', {})
    logger.debug(f"KillDetector 配置:")
    logger.debug(f"  Confidence threshold: {detection_cfg.get('confidence_threshold', 0.5)}")
    logger.debug(f"  ROI: {detection_cfg.get('killfeed_roi', [0, 0, 1, 1])}")
    logger.debug(f"  Colors: {list(detection_cfg.get('colors', {}).keys())}")
    logger.debug(f"  OCR enabled: {detection_cfg.get('ocr', {}).get('enabled', False)}")
    logger.debug(f"  Prefilter threshold: {detection_cfg.get('prefilter', {}).get('color_threshold', 0.01)}")
    
    # 批量处理
    logger.info("开始批量检测...")
    chunk_size = 128
    detected_events = []
    
    for i in range(0, len(test_frames), chunk_size):
        chunk_paths = test_frames[i:i + chunk_size]
        chunk_frames = []
        chunk_timestamps = []
        
        for frame_path in chunk_paths:
            frame = cv2.imread(frame_path)
            if frame is not None:
                chunk_frames.append(frame)
                try:
                    ts_str = os.path.basename(frame_path).split('_')[1].split('.')[0]
                    chunk_timestamps.append(int(ts_str))
                except:
                    chunk_timestamps.append(0)
        
        if chunk_frames:
            logger.info(f"处理批次 {i//chunk_size + 1}: {len(chunk_frames)} 帧")
            batch_events = kill_detector.process_video_batch(chunk_frames, chunk_timestamps)
            detected_events.extend(batch_events)
            
            logger.debug(f"批次 {i//chunk_size + 1}: 检测到 {len(batch_events)} 个事件")
            if len(batch_events) > 0:
                for event in batch_events:
                    logger.info(f"  ✅ 事件: ts={event.get('timestamp_ms')}ms, conf={event.get('confidence', 0):.3f}")
    
    # 最终统计
    logger.info("")
    logger.info("="*60)
    logger.info(f"检测完成!")
    logger.info(f"  总帧数: {len(test_frames)}")
    logger.info(f"  检测到的事件: {len(detected_events)}")
    if len(detected_events) > 0:
        avg_conf = sum(e.get('confidence', 0) for e in detected_events) / len(detected_events)
        logger.info(f"  平均置信度: {avg_conf:.3f}")
        logger.info("")
        logger.info("所有事件:")
        for i, event in enumerate(detected_events, 1):
            logger.info(f"  {i}. ts={event.get('timestamp_ms')}ms, conf={event.get('confidence', 0):.3f}")
    logger.info("="*60)

if __name__ == "__main__":
    main()
