# -*- coding: utf-8 -*-
#import sys, os
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Dict, Any, Tuple
import numpy as np
import mediapipe as mp
import cv2
from ..utils.image_io import to_rgb

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

def _P(lm, idx, w, h):
    p = lm[idx]
    return np.array([p.x * w, p.y * h])

def draw_debug(bgr: np.ndarray, res) -> np.ndarray:
    out = bgr.copy()
    rgb = to_rgb(out)
    if res and res.pose_landmarks:
        mp_draw.draw_landmarks(
            rgb, res.pose_landmarks,
            mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style()
        )
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

def classify(bgr, return_debug: bool=False) -> Tuple[Dict[str, Any], bytes]:
    """체형 분류: inverted_triangle/triangle/hourglass/rectangle/balanced/unknown"""
    rgb = to_rgb(bgr)
    with mp_pose.Pose(static_image_mode=True, enable_segmentation=False) as pose:
        res = pose.process(rgb)

    if not res.pose_landmarks:
        out = {"body_shape": "unknown", "metrics": None, "debug": "no_pose"}
        return out, b""
    
    lm = res.pose_landmarks.landmark
    h, w = rgb.shape[:2]
    LSh, RSh = _P(lm, 11, w, h), _P(lm, 12, w, h)
    LHip, RHip = _P(lm, 23, w, h), _P(lm, 24, w, h)

    shoulder_width = np.linalg.norm(RSh - LSh)
    hip_width = np.linalg.norm(RHip - LHip)
    waist_width = 0.75 * (shoulder_width + hip_width) / 2.0  # 근사
    s_h = shoulder_width / (hip_width + 1e-6)
    w_s = waist_width / (shoulder_width + 1e-6)
    w_h = waist_width / (hip_width + 1e-6)

    body = "balanced"
    if s_h >= 1.1:
        body = "inverted_triangle"
    elif s_h <= 0.9:
        body = "triangle"
    elif w_s <= 0.75 and w_h <= 0.75:
        body = "hourglass"
    elif abs(s_h - 1.0) < 0.1 and (0.75 < w_s <= 0.9) and (0.75 < w_h <= 0.9):
        body = "rectangle"

    out = {
        "body_shape": body,
        "metrics": {
            "shoulder_width": float(shoulder_width),
            "hip_width": float(hip_width),
            "waist_width_est": float(waist_width),
            "s_h": float(s_h), "w_s": float(w_s), "w_h": float(w_h)
        },
        "debug":"ok"
    }
    
    debug_png = b""
    if return_debug:
        dbg = draw_debug(bgr, res)
        ok, buf = cv2.imencode(".png", dbg)
        debug_png = buf.tobytes() if ok else b""

    return out, debug_png