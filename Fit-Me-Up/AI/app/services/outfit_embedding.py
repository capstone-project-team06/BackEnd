# app/services/outfit_embedding.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, List

# ---------------------------------------------------------
# 6D Rule-based Style Vector
# ---------------------------------------------------------
def _normalize(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _same_color_family(a: str, b: str) -> bool:
    a = _normalize(a)
    b = _normalize(b)
    groups = [
        {"white", "ivory", "beige", "cream"},
        {"black", "charcoal"},
        {"gray", "grey"},
        {"navy", "blue"},
        {"brown", "khaki"},
        {"pink", "red"},
        {"green", "olive"},
    ]
    for g in groups:
        if a in g and b in g:
            return True
    return False


def style_to_vec(style: str, season: str, color: str,
                 category: str, fit: str) -> List[float]:

    style = _normalize(style)
    season = _normalize(season)
    color = _normalize(color)
    category = _normalize(category)
    fit = _normalize(fit)

    v = [0.0] * 6

    # -------------------------------------
    # v0: minimal(+1) ↔ street(-1)
    # -------------------------------------
    if style == "minimal":
        v[0] = 0.9
    elif style == "street":
        v[0] = -0.9
    elif style in ("casual", "sporty"):
        v[0] = 0.3
    elif style in ("retro", "romantic"):
        v[0] = -0.3
    elif style == "formal":
        v[0] = 0.2

    # -------------------------------------
    # v1: casual(+1) ↔ formal(-1)
    # -------------------------------------
    if style in ("casual", "street", "sporty"):
        v[1] = 0.8
    elif style == "formal":
        v[1] = -0.8
    elif style in ("minimal", "retro", "romantic"):
        v[1] = 0.1

    # -------------------------------------
    # v2: soft-tone(+1) ↔ vivid-tone(-1)
    # -------------------------------------
    soft_colors = {"white", "ivory", "beige", "cream", "lightgray", "gray"}
    vivid_colors = {"red", "yellow", "green", "blue", "pink", "orange", "purple"}

    if color in soft_colors:
        v[2] = 0.8
    elif color in vivid_colors:
        v[2] = -0.8
    else:
        if any(_same_color_family(color, c) for c in soft_colors):
            v[2] = 0.4
        elif any(_same_color_family(color, c) for c in vivid_colors):
            v[2] = -0.4
        else:
            v[2] = 0.0

    # -------------------------------------
    # v3: category axis
    # -------------------------------------
    cat_map = {
        "top": 0.8,
        "bottom": 0.4,
        "outer": -0.2,
        "dress": 0.6,
        "shoes": -0.6,
        "bag": -0.8,
        "accessory": -0.4,
    }
    v[3] = cat_map.get(category, 0.0)

    # -------------------------------------
    # v4: fit axis (slim ↔ oversized)
    # -------------------------------------
    fit_map = {
        "slim": -0.8,
        "regular": 0.0,
        "relaxed": 0.4,
        "oversized": 0.8,
    }
    v[4] = fit_map.get(fit, 0.0)

    # -------------------------------------
    # v5: season axis
    # -------------------------------------
    if season in ("spring", "summer"):
        v[5] = 0.9
    elif season in ("fall", "autumn", "winter"):
        v[5] = -0.9
    elif season == "all":
        v[5] = 0.0

    return v

def style_vec_from_dict(garment: dict) -> List[float]:
    """
    GPT가 만든 garment dict (category, style, color, fit, season 포함)를
    그대로 받아서 vector를 만들어주는 편의 함수.

    예)
      g = {
        "category": "top",
        "sub_category": "tshirt",
        "style": "minimal",
        "color": "white",
        "fit": "oversized",
        "season": "summer"
      }
      vec = style_vec_from_dict(g)
    """
    return style_to_vec(
        style=garment.get("style", ""),
        season=garment.get("season", ""),
        color=garment.get("color", ""),
        category=garment.get("category", ""),
        fit=garment.get("fit", ""),
    )