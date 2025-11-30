# -*- coding: utf-8 -*-
# app/classifiers/skin.py
from typing import Dict, Any, Tuple
import cv2, numpy as np, mediapipe as mp
from ..utils.image_io import to_rgb

mp_face_mesh = mp.solutions.face_mesh

def draw_debug(bgr: np.ndarray, bbox) -> np.ndarray:
    """ROI 박스(중앙부) 시각화"""
    out = bgr.copy()
    x1, y1, x2, y2 = bbox
    cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 2)  # 빨간 박스
    # 가운데 점 찍기
    cx, cy = (x1+x2)//2, (y1+y2)//2
    cv2.circle(out, (cx, cy), 4, (0, 0, 255), -1)
    return out

def classify(bgr, return_debug: bool=False) -> Tuple[Dict[str, Any], bytes]:
    """
    피부톤 분류: depth(light/medium/deep) + undertone(warm/cool/neutral)
    """
    
    rgb = to_rgb(bgr)
    h, w = rgb.shape[:2]
    with mp_face_mesh.FaceMesh(static_image_mode=True, refine_landmarks=True,
                               max_num_faces=1, min_detection_confidence=0.5) as mesh:
        res = mesh.process(rgb)
        
    if not res.multi_face_landmarks:
        return {"skin_tone":"unknown", "metrics":None, "debug":"no_face"}, b""


    lm = res.multi_face_landmarks[0].landmark
    xs = [int(pt.x * w) for pt in lm]
    ys = [int(pt.y * h) for pt in lm]
    x1, y1, x2, y2 = max(0,min(xs)), max(0,min(ys)), min(w,max(xs)), min(h,max(ys))

    # 얼굴 중앙부 ROI
    cx1 = x1 + int((x2 - x1) * 0.25)
    cx2 = x2 - int((x2 - x1) * 0.25)
    cy1 = y1 + int((y2 - y1) * 0.25)
    cy2 = y2 - int((y2 - y1) * 0.35)
    roi = bgr[cy1:cy2, cx1:cx2].copy()
    if roi.size == 0:
        return {"skin_tone":"unknown", "metrics":None, "debug":"roi_empty"}, b""

    # 평균 색상(Lab/HSV)
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    L, a, b = lab[:,:,0].mean(), lab[:,:,1].mean(), lab[:,:,2].mean()
    H, S, V = hsv[:,:,0].mean(), hsv[:,:,1].mean(), hsv[:,:,2].mean()

    # ----- depth(밝기) -----
    depth = "light" if L >= 180 else ("medium" if L >= 130 else "deep")

    # ----- undertone (3-1 전역 threshold 버전) -----
    da = a - 128
    db = b - 128

    # 노랑/빨강 쪽으로 치우친 정도 (웜톤 점수)
    score = da + 0.8 * db

    T = 6.0  # 임계값: 나중에 데이터 보면서 5~8 사이에서 조정

    if score > T:
        undertone = "warm"
    elif score < -T:
        undertone = "cool"
    else:
        undertone = "neutral"

    out = {
        "skin_tone": f"{depth}_{undertone}",
        "metrics": {
            "L_mean": float(L), "a_mean": float(a), "b_mean": float(b),
            "H_mean": float(H), "S_mean": float(S), "V_mean": float(V),
            "roi_bbox": [int(cx1), int(cy1), int(cx2), int(cy2)]
        },
        "debug":"ok"
    }
    debug_png = b""
    
    if return_debug:
        dbg = draw_debug(bgr, (cx1, cy1, cx2, cy2))
        ok, buf = cv2.imencode(".png", dbg)
        debug_png = buf.tobytes() if ok else b""

    return out, debug_png