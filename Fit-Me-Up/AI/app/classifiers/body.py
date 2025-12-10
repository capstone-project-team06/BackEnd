# -*- coding: utf-8 -*-
from typing import Dict, Any, Tuple, Optional
import numpy as np
import mediapipe as mp
import cv2
from ..utils.image_io import to_rgb

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

def _P(lm, idx, w, h):
    p = lm[idx]
    return np.array([p.x * w, p.y * h], dtype=np.float32)

def _seg_row_width(seg: np.ndarray, y: float, thr: float = 0.5) -> Optional[Tuple[float, int, int]]:
    """
    segmentation_mask의 특정 y에서 실루엣 폭 측정.
    return: (width, x_min, x_max) or None
    """
    h, w = seg.shape[:2]
    y_i = int(round(y))
    if y_i < 0 or y_i >= h:
        return None

    row = seg[y_i, :]
    mask = row > thr
    if not np.any(mask):
        return None

    xs = np.where(mask)[0]
    x_min, x_max = int(xs[0]), int(xs[-1])
    width = float(x_max - x_min)
    return width, x_min, x_max

def draw_debug(bgr: np.ndarray, res, waist_y: Optional[float] = None) -> np.ndarray:
    out = bgr.copy()
    rgb = to_rgb(out)
    h, w = rgb.shape[:2]

    if res and res.pose_landmarks:
        mp_draw.draw_landmarks(
            rgb, res.pose_landmarks,
            mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style()
        )
    # 허리 y 라인 시각화
    if waist_y is not None:
        y_i = int(round(waist_y))
        if 0 <= y_i < h:
            cv2.line(rgb, (0, y_i), (w-1, y_i), (0, 255, 0), 1)

    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

def classify_body_shape(bgr, return_debug: bool=False) -> Tuple[Dict[str, Any], bytes]:
    """
    체형 분류: inverted_triangle/triangle/hourglass/rectangle/balanced/unknown
    - 어깨/골반 폭: 포즈 랜드마크 기반 + segmentation 기반 보정
    - 허리 폭: segmentation_mask에서 실루엣 폭으로 측정
    """
    rgb = to_rgb(bgr)
    h, w = rgb.shape[:2]

    with mp_pose.Pose(
        static_image_mode=True,
        enable_segmentation=True,   # ★ segmentation 활성화
        model_complexity=1
    ) as pose:
        res = pose.process(rgb)

    if not res.pose_landmarks:
        out = {"body_shape": "unknown", "metrics": None, "debug": "no_pose"}
        return out, b""

    seg = getattr(res, "segmentation_mask", None)
    if seg is None:
        # segmentation 실패 시: 예전 방식으로 fallback 가능하지만,
        # 일단 unknown으로 두는 것도 선택지
        out = {"body_shape": "unknown", "metrics": None, "debug": "no_segmentation"}
        return out, b""

    lm = res.pose_landmarks.landmark

    # ---- 기본 랜드마크 좌표 ----
    LSh, RSh = _P(lm, 11, w, h), _P(lm, 12, w, h)
    LHip, RHip = _P(lm, 23, w, h), _P(lm, 24, w, h)

    # 중심 y (어깨 / 골반)
    y_shoulder = float((LSh[1] + RSh[1]) * 0.5)
    y_hip      = float((LHip[1] + RHip[1]) * 0.5)

    # ---- landmark 기반 폭(백업용) ----
    shoulder_width_lm = float(np.linalg.norm(RSh - LSh))
    hip_width_lm      = float(np.linalg.norm(RHip - LHip))

    # ---- segmentation 기반 실루엣 폭 측정 ----
    # 어깨 / 골반은 segmentation row에서 보정 시도, 실패하면 landmark 폭 사용
    shoulder_seg = _seg_row_width(seg, y_shoulder, thr=0.5)
    hip_seg      = _seg_row_width(seg, y_hip, thr=0.5)

    if shoulder_seg is not None:
        shoulder_width, sh_x_min, sh_x_max = shoulder_seg
    else:
        shoulder_width, sh_x_min, sh_x_max = shoulder_width_lm, int(LSh[0]), int(RSh[0])

    if hip_seg is not None:
        hip_width, hip_x_min, hip_x_max = hip_seg
    else:
        hip_width, hip_x_min, hip_x_max = hip_width_lm, int(LHip[0]), int(RHip[0])

    # ---- 허리 위치 결정 (어깨~골반 사이 선형 보간) ----
    # 허리는 골반에 조금 더 가까운 y 지점으로 설정 (0.0=어깨, 1.0=골반)
    t_waist = 0.6
    y_waist = (1.0 - t_waist) * y_shoulder + t_waist * y_hip

    # 허리 폭은 주변 여러 줄 평균으로 조금 안정화
    waist_widths = []
    waist_xmins  = []
    waist_xmaxs  = []
    for dy in [-4, -2, 0, 2, 4]:
        ws = _seg_row_width(seg, y_waist + dy, thr=0.5)
        if ws is not None:
            wv, x_min, x_max = ws
            waist_widths.append(wv)
            waist_xmins.append(x_min)
            waist_xmaxs.append(x_max)

    if len(waist_widths) == 0:
        # 허리 실루엣 추출 실패 → hourglass 판단은 의미가 없으니 상/하체 비만 사용
        waist_width = (shoulder_width + hip_width) * 0.5  # 대충 평균값
        waist_from_seg = False
    else:
        waist_width = float(np.mean(waist_widths))
        waist_from_seg = True

    eps = 1e-6
    s_h = shoulder_width / (hip_width + eps)     # 어깨 / 골반
    w_s = waist_width   / (shoulder_width + eps) # 허리 / 어깨
    w_h = waist_width   / (hip_width + eps)      # 허리 / 골반

    drop_s = 1.0 - w_s  # 어깨 대비 허리 감소율 (양수면 잘록, 음수면 허리가 더 큼)
    drop_h = 1.0 - w_h  # 골반 대비 허리 감소율

    body = "balanced"

    if s_h > 1.9 or s_h < 0.6:
        body = "unknown"
        debug_flag = "ratio_outlier"
    else:
        # 0) 허리가 제일 넓은 체형 (apple / oval 계열) → inverted_rectangle로 표시
        if w_s >= 1.10 and w_h >= 1.05:
            # 허리가 어깨보다 10% 이상, 골반보다 5% 이상 넓으면
            body = "inverted_rectangle"

        # 1) 상/하체 비가 많이 다른 경우 (허리는 크게 안 들어간 조건 하에서만)
        elif s_h >= 1.25 and drop_h < 0.12:
            body = "inverted_triangle"
        elif s_h <= 0.85 and drop_h < 0.12:
            body = "triangle"

        else:
            # 2) 그 외는 허리 감소율로 hourglass / rectangle / balanced
            if drop_s >= 0.18 and drop_h >= 0.12:
                # 어깨 대비 18%+, 골반 대비 12%+ 감소 → 모래시계
                body = "hourglass"
            elif abs(drop_s) <= 0.12 and abs(drop_h) <= 0.12:
                # 허리가 어깨/골반과 거의 비슷 (±12% 이내) → 직사각형
                body = "rectangle"
            else:
                body = "balanced"

        debug_flag = "ok"


    out = {
        "body_shape": body,
        "metrics": {
            "shoulder_width_seg": float(shoulder_width),
            "hip_width_seg": float(hip_width),
            "waist_width_seg": float(waist_width),
            "shoulder_width_lm": float(shoulder_width_lm),
            "hip_width_lm": float(hip_width_lm),
            "s_h": float(s_h),
            "w_s": float(w_s),
            "w_h": float(w_h),
            "y_shoulder": float(y_shoulder),
            "y_waist": float(y_waist),
            "y_hip": float(y_hip),
            "waist_from_seg": bool(waist_from_seg),
        },
        "debug": debug_flag,
    }

    debug_png = b""
    if return_debug:
        dbg = draw_debug(bgr, res, waist_y=y_waist)
        ok, buf = cv2.imencode(".png", dbg)
        debug_png = buf.tobytes() if ok else b""

    return out, debug_png
