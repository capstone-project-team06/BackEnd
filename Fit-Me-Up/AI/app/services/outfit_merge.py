# app/services/outfit_merge.py
# -*- coding: utf-8 -*-
"""
여러 이미지에서 나온 outfit JSON을 하나로 통합.
레퍼런스 이미지가 1장만 있을 때 -> outfit_json = analyze_outfit_with_gpt([one_url]) -> merge 필요없음
"""
from __future__ import annotations
from typing import Dict, List, Any
import collections

def merge_outfit_jsons(outfits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    여러 outfit JSON → 하나의 unified JSON으로 병합.
    룰:
    - 동일 category 항목은 가장 많이 등장한 속성으로 선택
    - color/material/fit은 frequency 기반 majority vote
    """

    category_map = collections.defaultdict(list)

    for outfit in outfits:
        for g in outfit.get("garments", []):
            category_map[g["category"]].append(g)

    merged = {"garments": []}

    for category, items in category_map.items():
        # 가장 많이 등장한 속성 선택
        counter_name = collections.Counter([it.get("name") for it in items if it.get("name")])
        counter_color = collections.Counter([it.get("color") for it in items if it.get("color")])
        counter_material = collections.Counter([it.get("material") for it in items if it.get("material")])
        counter_fit = collections.Counter([it.get("fit") for it in items if it.get("fit")])

        merged["garments"].append({
            "category": category,
            "name": counter_name.most_common(1)[0][0] if counter_name else None,
            "color": counter_color.most_common(1)[0][0] if counter_color else None,
            "material": counter_material.most_common(1)[0][0] if counter_material else None,
            "fit": counter_fit.most_common(1)[0][0] if counter_fit else None,
        })

    return merged
