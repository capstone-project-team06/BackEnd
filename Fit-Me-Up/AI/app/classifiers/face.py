# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional, Tuple
import numpy as np
import cv2
import mediapipe as mp
import csv
import os
from ..utils.image_io import to_rgb

mp_face_mesh = mp.solutions.face_mesh
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles


# ===============================
# Utility: landmark XY
# ===============================
def _P(lm, idx, w, h):
    p = lm[idx]
    return np.array([p.x * w, p.y * h])


# ===============================
# Debug image
# ===============================
def draw_debug(bgr: np.ndarray, res) -> np.ndarray:
    out = bgr.copy()
    rgb = to_rgb(out)
    if res and res.multi_face_landmarks:
        for face_lms in res.multi_face_landmarks:
            mp_draw.draw_landmarks(
                image=rgb,
                landmark_list=face_lms,
                connections=mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_styles.get_default_face_mesh_tesselation_style(),
            )
            mp_draw.draw_landmarks(
                image=rgb,
                landmark_list=face_lms,
                connections=mp_face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_styles.get_default_face_mesh_contours_style(),
            )
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


# ===============================
# CSV Logging
# ===============================
LOG_PATH = "face_shape_log.csv"

def log_face_shape(data: dict):
    """data = {
        'face_width': ...
        'face_length': ...
        ...
        'face_shape': ...
    }
    """
    file_exists = os.path.isfile(LOG_PATH)

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # 헤더 생성
        if not file_exists:
            writer.writerow(list(data.keys()))

        # 값 쓰기
        writer.writerow(list(data.values()))


# ===============================
# Main classifier
# ===============================
def classify_face_shape(bgr, return_debug: bool=False) -> Tuple[Dict[str, Any], bytes]:
    """얼굴형 분류: round/square/oval/oblong/heart/unknown"""

    rgb = to_rgb(bgr)
    h, w = rgb.shape[:2]

    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        refine_landmarks=True,
        max_num_faces=1,
        min_detection_confidence=0.5
    ) as mesh:
        res = mesh.process(rgb)

    if not res.multi_face_landmarks:
        return {"face_shape": "unknown", "metrics": None, "debug": "no_face"}, b""

    lm = res.multi_face_landmarks[0].landmark

    # landmarks
    left_face  = _P(lm, 234, w, h)
    right_face = _P(lm, 454, w, h)
    face_width = np.linalg.norm(right_face - left_face)

    forehead = _P(lm, 10, w, h)
    chin     = _P(lm, 152, w, h)
    face_length = np.linalg.norm(chin - forehead)

    brow_left  = _P(lm, 70, w, h)
    brow_right = _P(lm, 300, w, h)
    forehead_width = np.linalg.norm(brow_right - brow_left)

    jaw_width = face_width * 0.90  # 근사치

    # ratios
    R = face_length / (face_width + 1e-6)
    J = jaw_width / (forehead_width + 1e-6)

    # =====================================
    #      ★ 튜닝된 얼굴형 분류 로직 ★
    # =====================================
    fs = "oval"

    # 1) 긴 얼굴 → oblong
    if R >= 1.40:
        fs = "oblong"

    # 2) 이마 넓고 턱 좁음 → heart
    elif J < 0.90 and R >= 1.20:
        fs = "heart"

    # 3) 비교적 짧고 넓은 얼굴 (R가 작은 구간)
    elif R <= 1.14:
        # R이 짧고, 턱/이마 폭이 거의 비슷하거나 조금 넓은 경우 → round
        if J >= 1.11:
            fs = "round"
        elif J >= 1.06:
            # 살짝 각은 있지만, 아직은 oval 느낌 유지
            fs = "oval"
        else:
            # 턱이 이마보다 확 좁으면 동그랗게 보이는 쪽으로
            fs = "round"

    # 4) 중간 길이 (1.14 < R <= 1.22)
    elif R <= 1.22:
        # 이 구간에서는 턱이 이마보다 조금만 넓어도 사각 느낌이 강해짐
        if J >= 1.07:
            fs = "square"
        else:
            fs = "oval"

    # 5) 그보다 긴 얼굴 (1.22 < R < 1.40)
    else:
        if J >= 1.10:
            fs = "square"
        # 나머지는 기본 oval 유지

    # ===============================
    # Output dict
    # ===============================
    metrics = {
        "face_width": float(face_width),
        "face_length": float(face_length),
        "forehead_width": float(forehead_width),
        "jaw_width_est": float(jaw_width),
        "ratio_len_width": float(R),
        "ratio_jaw_forehead": float(J),
    }

    out = {
        "face_shape": fs,
        "metrics": metrics,
        "debug": "ok"
    }

    # ===============================
    # Log to CSV
    # ===============================
    log_data = metrics.copy()
    log_data["face_shape"] = fs
    log_face_shape(log_data)

    # ===============================
    # Debug image encode
    # ===============================
    debug_png = b""
    if return_debug:
        dbg = draw_debug(bgr, res)
        success, buf = cv2.imencode(".png", dbg)
        debug_png = buf.tobytes() if success else b""

    return out, debug_png
