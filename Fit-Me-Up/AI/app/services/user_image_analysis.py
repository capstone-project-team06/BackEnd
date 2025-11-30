# app/services/user_image_analysis.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Dict, Any, List

from app.clients.backend_client import fetch_user_images
from .url_analyzer import analyze_image_from_url


async def analyze_latest_body_image(token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    백엔드에서 BODY 타입 이미지 목록을 받아와서,
    가장 최근 한 장에 대해 분석을 수행.
    """
    data = await fetch_user_images(token=token)
    # created_at 기준으로 BODY만 필터 후 최신순 정렬
    body_images = [img for img in data.images if img.image_type.upper() == "BODY"]

    if not body_images:
        return None

    # 가장 최근 것 (created_at이 문자열이라면 그냥 마지막으로 가정해도 됨)
    latest = sorted(body_images, key=lambda x: x.created_at)[-1]
    return analyze_image_from_url(latest.image_url)


async def analyze_all_body_images(token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    BODY 이미지 전부에 대해 분석 (비용 크니까 필요할 때만 사용)
    """
    data = await fetch_user_images(token=token)
    body_images = [img for img in data.images if img.image_type.upper() == "BODY"]

    results: List[Dict[str, Any]] = []
    for img in body_images:
        try:
            res = analyze_image_from_url(img.image_url)
            results.append(res)
        except Exception as e:
            # 개별 실패는 무시하고 계속
            print(f"[WARN] analyze failed for {img.image_url}: {e}")
    return results
