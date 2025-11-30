# app/services/style_from_outfit.py
from __future__ import annotations
from typing import Dict, Any, List
from outfit_embedding import style_to_vec

def outfit_to_cloth_like_items(outfit_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    outfit_analyzer 결과(outfit_json)에서
    ClothAnalysis와 동일한 스키마 + vector까지 붙인 아이템 리스트를 생성.

    반환 예:
    [
      {
        "name": "크롭 블레이저",
        "category": "top",
        "sub_category": "tshirt",
        "style": "minimal",
        "color": "white",
        "fit": "oversized",
        "season": "summer",
        "vector": [...],
      },
      ...
    ]
    """
    items: List[Dict[str, Any]] = []

    for look in outfit_json.get("looks", []) or []:
        for g in look.get("garments", []) or []:
            cat  = (g.get("category") or "unknown").lower()
            sub  = (g.get("sub_category") or "unknown").lower()
            sty  = (g.get("style") or "unknown").lower()
            col  = (g.get("color") or "unknown").lower()
            fit  = (g.get("fit") or "unknown").lower()
            seas = (g.get("season") or "all").lower()

            vec = style_to_vec(
                category=cat,
                sub_category=sub,
                style=sty,
                color=col,
                fit=fit,
                season=seas,
            )

            items.append(
                {
                    "name": g.get("name") or "",
                    "category": cat,
                    "sub_category": sub,
                    "style": sty,
                    "color": col,
                    "fit": fit,
                    "season": seas,
                    "vector": vec,
                }
            )

    return items
