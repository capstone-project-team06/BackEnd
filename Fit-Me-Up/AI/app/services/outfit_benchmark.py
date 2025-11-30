# app/services/outfit_benchmark.py
# -*- coding: utf-8 -*-
"""
quick_web_outfit  vs  image_searcher + outfit_analyzer
두 파이프라인의 latency, 결과 구조를 빠르게 비교하기 위한 CLI 스크립트.

사용 예:
    cd app
    # 기본: 아이유 + "여름,블레이저"
    python -m services.outfit_benchmark "아이유" "여름,블레이저"

전제:
    - services.quick_web_outfit.quick_outfit_from_web 이 구현되어 있음
    - services.image_searcher.search_reference_images 가 SerpAPI(or Bing/Google) 기반으로 동작
    - services.outfit_analyzer.analyze_outfit_with_gpt 가 [image_url 리스트]를 입력으로 받음
"""

from __future__ import annotations
import time
import json
import sys
from typing import List

from dotenv import load_dotenv
load_dotenv()

# 프로젝트 구조 상, app/ 디렉토리에서
#   python -m services.outfit_benchmark
# 로 실행한다고 가정
from services.quick_web_outfit import quick_outfit_from_web
from services.image_searcher import search_reference_images
from services.outfit_analyzer import analyze_outfit_with_gpt


# ----------------------------------------------------
# 파이프라인 A: quick_web_outfit (검색+분석 전부 GPT가 수행)
# ----------------------------------------------------
def pipeline_quick_web_outfit(
    celeb_name: str,
    needs: List[str],
) -> dict:
    """
    GPT web_search + Vision 분석까지 한 번에 하는 버전.
    quick_web_outfit이 내부에서 web_search tool + vision model을 사용한다고 가정.
    """
    result = quick_outfit_from_web(celeb_name, needs)
    # result 예시(가정):
    # {
    #   "celeb_name": "아이유",
    #   "query_needs": ["여름","블레이저"],
    #   "looks": [
    #       {
    #           "title": "...",
    #           "image_url": "...",
    #           "source_url": "...",
    #           "garments": [...]
    #       },
    #       ...
    #   ]
    # }
    return result or {}


# ----------------------------------------------------
# 파이프라인 B: image_searcher + outfit_analyzer
# ----------------------------------------------------
def pipeline_external_search_plus_analyzer(
    celeb_name: str,
    needs: List[str],
    max_results: int = 12,
    max_analyze_images: int = 6,
) -> dict:
    """
    1) 외부 이미지 검색 (SerpAPI Bing / Google 등)
    2) 상위 N개 URL을 GPT Vision outfit_analyzer에 넣어 분석
    """
    # 1. 이미지 검색
    search_items = search_reference_images(
        celeb_name=celeb_name,
        needs=needs,
        max_results=max_results,
    )

    image_urls = [it.get("image") for it in search_items if it.get("image")]
    image_urls = image_urls[:max_analyze_images]

    if not image_urls:
        return {
            "input_images": [],
            "outfit_json": {},
        }

    # 2. GPT Vision 기반 outfit 분석
    outfit_json = analyze_outfit_with_gpt(image_urls)

    return {
        "input_images": image_urls,
        "outfit_json": outfit_json,
    }


# ----------------------------------------------------
# 벤치마크 유틸
# ----------------------------------------------------
def bench_once(
    celeb_name: str,
    needs: List[str],
    max_results: int = 12,
    max_analyze_images: int = 6,
) -> None:
    print(f"[BENCH] celeb={celeb_name}, needs={needs}")
    print("-" * 60)
    
    # A) quick_web_outfit
    t0 = time.perf_counter()
    quick_res = pipeline_quick_web_outfit(celeb_name, needs)
    dt_quick = time.perf_counter() - t0

    looks = quick_res.get("looks", []) or []
    print(f"[A] quick_web_outfit")
    print(f"    - time: {dt_quick:.2f} sec")
    print(f"    - looks: {len(looks)}")
    # 상위 1~2개만 프린트 (너무 길면 의미 없으니)
    print("    - sample (truncated):")
    print(json.dumps(looks[:2], ensure_ascii=False, indent=2))

    print("\n" + "-" * 60)
    
    # B) external search + outfit_analyzer
    t0 = time.perf_counter()
    ext_res = pipeline_external_search_plus_analyzer(
        celeb_name,
        needs,
        max_results=max_results,
        max_analyze_images=max_analyze_images,
    )
    dt_ext = time.perf_counter() - t0

    print(f"[B] image_searcher + outfit_analyzer")
    print(f"    - time: {dt_ext:.2f} sec")
    print(f"    - input_images: {len(ext_res.get('input_images', []))}")
    print("    - sample images:")
    print(json.dumps(ext_res.get("input_images", [])[:3], ensure_ascii=False, indent=2))

    print("    - outfit_json (truncated):")
    print(json.dumps(ext_res.get("outfit_json", {}), ensure_ascii=False, indent=2)[:1500])

    print("\n" + "=" * 60)
    print("[SUMMARY]")
    print(f"  A) quick_web_outfit              : {dt_quick:.2f} sec")
    print(f"  B) external + outfit_analyzer    : {dt_ext:.2f} sec")
    print("=" * 60)


def main():
    # 사용법:
    #   python -m services.outfit_benchmark "아이유" "여름,블레이저"
    celeb = sys.argv[1] if len(sys.argv) > 1 else "아이유"
    needs_arg = sys.argv[2] if len(sys.argv) > 2 else "여름,블레이저"
    needs = [s.strip() for s in needs_arg.split(",") if s.strip()]

    bench_once(celeb, needs)


if __name__ == "__main__":
    main()
