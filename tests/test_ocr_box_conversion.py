import pytest
import os
import cv2
import numpy as np
from src.tools.config_assistant.api import api_bp
from flask import Flask, jsonify

def test_bbox_to_box_logic():
    # Mock data
    img_w, img_h = 1920, 1080
    roi = [0.1, 0.2, 0.3, 0.4] # [x, y, w, h] relative
    
    # ROI in pixels: 
    # rx = 192, ry = 216, rw = 576, rh = 432
    roi_px = [roi[0] * img_w, roi[1] * img_h, roi[2] * img_w, roi[3] * img_h]
    
    # Bbox in absolute pixels (within ROI)
    # Let's say a box at relative (to ROI) [0.1, 0.1, 0.5, 0.5]
    # In pixels relative to image:
    # x = 192 + 0.1 * 576 = 192 + 57.6 = 249.6
    # y = 216 + 0.1 * 432 = 216 + 43.2 = 259.2
    # w = 0.5 * 576 = 288
    # h = 0.5 * 432 = 216
    
    bbox = [
        [249.6, 259.2],
        [249.6 + 288, 259.2],
        [249.6 + 288, 259.2 + 216],
        [249.6, 259.2 + 216]
    ]
    
    # Logic to be implemented:
    min_x = min(p[0] for p in bbox)
    max_x = max(p[0] for p in bbox)
    min_y = min(p[1] for p in bbox)
    max_y = max(p[1] for p in bbox)
    
    box_x = (min_x - roi_px[0]) / roi_px[2]
    box_y = (min_y - roi_px[1]) / roi_px[3]
    box_w = (max_x - min_x) / roi_px[2]
    box_h = (max_y - min_y) / roi_px[3]
    
    assert pytest.approx(box_x) == 0.1
    assert pytest.approx(box_y) == 0.1
    assert pytest.approx(box_w) == 0.5
    assert pytest.approx(box_h) == 0.5

def test_clamping_logic():
    # Bbox slightly outside ROI
    img_w, img_h = 1000, 1000
    roi = [0.1, 0.1, 0.1, 0.1] # ROI is [100, 100, 100, 100]
    roi_px = [100, 100, 100, 100]
    
    # Bbox is [50, 50, 100, 100] -> partially outside
    bbox = [[50, 50], [150, 50], [150, 150], [50, 150]]
    
    min_x = min(p[0] for p in bbox)
    max_x = max(p[0] for p in bbox)
    min_y = min(p[1] for p in bbox)
    max_y = max(p[1] for p in bbox)
    
    box_x = max(0, min(1, (min_x - roi_px[0]) / roi_px[2]))
    box_y = max(0, min(1, (min_y - roi_px[1]) / roi_px[3]))
    box_w = max(0, min(1 - box_x, (max_x - min_x) / roi_px[2])) # This clamping is slightly tricky
    # If we want the resulting box to be within [0,1], we should clamp min and max first, or clamp x,y then w,h
    
    # Better clamping:
    c_min_x = max(roi_px[0], min(roi_px[0] + roi_px[2], min_x))
    c_max_x = max(roi_px[0], min(roi_px[0] + roi_px[2], max_x))
    c_min_y = max(roi_px[1], min(roi_px[1] + roi_px[3], min_y))
    c_max_y = max(roi_px[1], min(roi_px[1] + roi_px[3], max_y))
    
    box_x = (c_min_x - roi_px[0]) / roi_px[2]
    box_y = (c_min_y - roi_px[1]) / roi_px[3]
    box_w = (c_max_x - c_min_x) / roi_px[2]
    box_h = (c_max_y - c_min_y) / roi_px[3]
    
    assert box_x == 0.0
    assert box_y == 0.0
    assert box_w == 0.5
    assert box_h == 0.5
