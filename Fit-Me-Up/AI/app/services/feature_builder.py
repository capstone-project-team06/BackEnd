# app/services/feature_builder.py
"""
face / body / skin classifier 출력으로부터
- 카테고리(one-hot) 중심
- metric은 보조적으로만 쓰는
feature vector를 생성하는 모듈.

입력: face, body, skin (각각 dict 형태)
출력: L2-normalized 1D np.array
"""

import numpy as np


# ----- 1. 카테고리 → one-hot 매핑 -----

BODY_SHAPE_MAP = {
    "inverted_triangle": [1, 0, 0, 0, 0],
    "triangle":          [0, 1, 0, 0, 0],
    "hourglass":         [0, 0, 1, 0, 0],
    "rectangle":         [0, 0, 0, 1, 0],
    "balanced":          [0, 0, 0, 0, 1],
    "unknown":           [0, 0, 0, 0, 0],
}

FACE_SHAPE_MAP = {
    "oval":    [1, 0, 0, 0, 0],
    "round":   [0, 1, 0, 0, 0],
    "square":  [0, 0, 1, 0, 0],
    "heart":   [0, 0, 0, 1, 0],
    "oblong":  [0, 0, 0, 0, 1],
    "unknown": [0, 0, 0, 0, 0],
}

# ----- SKIN: depth / undertone 분리 -----
SKIN_DEPTH_MAP = {
    "light":   [1, 0, 0],
    "medium":  [0, 1, 0],
    "deep":    [0, 0, 1],
    "unknown": [0, 0, 0],
}

SKIN_UNDERTONE_MAP = {
    "warm":    [1, 0, 0],
    "cool":    [0, 1, 0],
    "neutral": [0, 0, 1],
    "unknown": [0, 0, 0],
}


def _safe_get(m, key, default=0.0):
    if not m:
        return float(default)
    v = m.get(key, default)
    try:
        return float(v)
    except Exception:
        return float(default)


def build_feature_vector(face, body, skin):
    """
    카테고리(one-hot)를 메인으로, metric은 낮은 weight로 보조에만 쓰는 임베딩 생성.
    - face: face_shape + face metrics
    - body: body_shape + body metrics
    - skin: skin_tone + skin metrics
    """
    cat_vec = []   # 카테고리 one-hot들
    num_vec = []   # 연속형 metric들

    # ---------- BODY ----------
    bm = body.get("metrics") or {}
    body_label = body.get("body_shape", "unknown")
    # 카테고리 (메인축)
    cat_vec.extend(BODY_SHAPE_MAP.get(body_label, BODY_SHAPE_MAP["unknown"]))
    # metric (보조)
    num_vec.extend([
        _safe_get(bm, "s_h"),
        _safe_get(bm, "w_s"),
        _safe_get(bm, "w_h"),
    ])

    # ---------- FACE ----------
    fm = face.get("metrics") or {}
    face_label = face.get("face_shape", "unknown")
    cat_vec.extend(FACE_SHAPE_MAP.get(face_label, FACE_SHAPE_MAP["unknown"]))
    num_vec.extend([
        _safe_get(fm, "face_width"),
        _safe_get(fm, "face_length"),
        _safe_get(fm, "forehead_width"),
        _safe_get(fm, "jaw_width_est"),
        _safe_get(fm, "ratio_len_width"),
        _safe_get(fm, "ratio_jaw_forehead"),
    ])

    # ---------- SKIN ----------
    sm = skin.get("metrics") or {}
    skin_label = skin.get("skin_tone", "unknown")
    cat_vec.extend(SKIN_TONE_MAP.get(skin_label, SKIN_TONE_MAP["unknown"]))
    num_vec.extend([
        _safe_get(sm, "L_mean"),
        _safe_get(sm, "a_mean"),
        _safe_get(sm, "b_mean"),
        _safe_get(sm, "H_mean"),
        _safe_get(sm, "S_mean"),
        _safe_get(sm, "V_mean"),
    ])

    # ---------- metric scale 줄여주기 (카테고리 중심으로 만들기 위해) ----------
    num_vec = np.array(num_vec, dtype=float)

    # 아주 러프하게 스케일 줄이기: 값이 너무 크면 0~1 근처 수준으로 줄여줌
    # - 길이/폭 픽셀 값들은 대략 100~300 정도 → 0.01 곱해서 1~3 수준
    # - ratio 계열은 원래 0~2 정도라 크게 문제 안 됨
    numeric_scale = 0.01
    num_vec = num_vec * numeric_scale

    # 최종 벡터 = [카테고리 one-hot..., scaled metrics...]
    full_vec = np.array(cat_vec + num_vec.tolist(), dtype=float)

    # L2 normalize
    norm = np.linalg.norm(full_vec) + 1e-8
    return full_vec / norm

def build_feature_vector(face, body, skin):
    """
    카테고리(one-hot)를 메인으로, metrics는 보조적인 weight로 사용하는 임베딩 생성.
    - face: face_shape + face metrics
    - body: body_shape + body metrics
    - skin: depth(one-hot) + undertone(one-hot) + Lab/HSV metrics
    """
    cat_vec = []
    num_vec = []

    # ---------- BODY ----------
    bm = body.get("metrics") or {}
    body_label = body.get("body_shape", "unknown")
    cat_vec.extend(BODY_SHAPE_MAP.get(body_label, BODY_SHAPE_MAP["unknown"]))
    num_vec.extend([
        _safe_get(bm, "s_h"),
        _safe_get(bm, "w_s"),
        _safe_get(bm, "w_h"),
    ])

    # ---------- FACE ----------
    fm = face.get("metrics") or {}
    face_label = face.get("face_shape", "unknown")
    cat_vec.extend(FACE_SHAPE_MAP.get(face_label, FACE_SHAPE_MAP["unknown"]))
    num_vec.extend([
        _safe_get(fm, "face_width"),
        _safe_get(fm, "face_length"),
        _safe_get(fm, "forehead_width"),
        _safe_get(fm, "jaw_width_est"),
        _safe_get(fm, "ratio_len_width"),
        _safe_get(fm, "ratio_jaw_forehead"),
    ])

    # ---------- SKIN ----------
    sm = skin.get("metrics") or {}
    skin_label = skin.get("skin_tone", "unknown")  # 예: "light_warm"

    depth, undertone = "unknown", "unknown"
    if isinstance(skin_label, str) and "_" in skin_label:
        d, u = skin_label.split("_", 1)
        depth = d if d in SKIN_DEPTH_MAP else "unknown"
        undertone = u if u in SKIN_UNDERTONE_MAP else "unknown"

    cat_vec.extend(SKIN_DEPTH_MAP.get(depth, SKIN_DEPTH_MAP["unknown"]))
    cat_vec.extend(SKIN_UNDERTONE_MAP.get(undertone, SKIN_UNDERTONE_MAP["unknown"]))

    num_vec.extend([
        _safe_get(sm, "L_mean"),
        _safe_get(sm, "a_mean"),
        _safe_get(sm, "b_mean"),
        _safe_get(sm, "H_mean"),
        _safe_get(sm, "S_mean"),
        _safe_get(sm, "V_mean"),
    ])

    # ---------- metrics weight 줄이기 ----------
    num_vec = np.array(num_vec, dtype=float)
    numeric_scale = 0.01      # 카테고리가 메인, metric은 보조 역할
    num_vec = num_vec * numeric_scale

    full_vec = np.array(cat_vec + num_vec.tolist(), dtype=float)
    norm = np.linalg.norm(full_vec) + 1e-8
    return full_vec / norm