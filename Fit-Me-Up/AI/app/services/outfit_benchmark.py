# app/services/outfit_benchmark.py
# -*- coding: utf-8 -*-
"""
quick_web_outfit  vs  image_searcher + outfit_analyzer
두 파이프라인의 latency, 결과 구조를 빠르게 비교하기 위한 CLI 스크립트.

사용 예:
    cd app
    # 기본: 아이유 + "여름,블레이저" 한 번만 실행
    python -m services.outfit_benchmark "아이유" "여름,블레이저"

    # 100번 반복 실행 + CSV/그래프 저장
    python -m services.outfit_benchmark "아이유" "여름,블레이저" 100

전제:
    - services.quick_web_outfit.quick_outfit_from_web 이 구현되어 있음
    - services.image_searcher.search_reference_images 가 SerpAPI(or Bing/Google) 기반으로 동작
    - services.outfit_analyzer.analyze_outfit_with_gpt 가 [image_url 리스트]를 입력으로 받음
"""

from __future__ import annotations
import time
import json
import sys
from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv()

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

    outfit_json = analyze_outfit_with_gpt(image_urls)

    return {
        "input_images": image_urls,
        "outfit_json": outfit_json,
    }


# ----------------------------------------------------
# 벤치마크: 한 번 실행 (텍스트 출력 + 타이밍 리턴)
# ----------------------------------------------------
def bench_once(
    celeb_name: str,
    needs: List[str],
    max_results: int = 12,
    max_analyze_images: int = 6,
) -> Dict[str, Any]:
    """
    한 번 실행해서 결과를 콘솔에 찍고,
    타이밍/요약 정보를 dict로도 리턴.
    """
    print(f"[BENCH] celeb={celeb_name}, needs={needs}")
    print("-" * 60)

    # A) quick_web_outfit
    t0 = time.perf_counter()
    quick_res = pipeline_quick_web_outfit(celeb_name, needs)
    dt_quick = time.perf_counter() - t0

    looks = quick_res.get("looks", []) or []
    quick_looks_count = len(looks)

    print(f"[A] quick_web_outfit")
    print(f"    - time: {dt_quick:.2f} sec")
    print(f"    - looks: {quick_looks_count}")
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

    ext_input_images = ext_res.get("input_images", []) or []
    ext_images_count = len(ext_input_images)

    print(f"[B] image_searcher + outfit_analyzer")
    print(f"    - time: {dt_ext:.2f} sec")
    print(f"    - input_images: {ext_images_count}")
    print("    - sample images:")
    print(json.dumps(ext_input_images[:3], ensure_ascii=False, indent=2))

    print("    - outfit_json (truncated):")
    print(json.dumps(ext_res.get("outfit_json", {}), ensure_ascii=False, indent=2)[:1500])

    print("\n" + "=" * 60)
    print("[SUMMARY]")
    print(f"  A) quick_web_outfit              : {dt_quick:.2f} sec")
    print(f"  B) external + outfit_analyzer    : {dt_ext:.2f} sec")
    print("=" * 60)

    # 반복 벤치마크용 요약 리턴
    return {
        "dt_quick": dt_quick,
        "dt_ext": dt_ext,
        "quick_looks_count": quick_looks_count,
        "ext_images_count": ext_images_count,
    }


# ----------------------------------------------------
# N번 반복 벤치마크 + CSV/그래프 저장
# ----------------------------------------------------
def run_benchmark(
    celeb_name: str,
    needs: List[str],
    repeat: int = 100,
    max_results: int = 12,
    max_analyze_images: int = 6,
    csv_path: str = "outfit_benchmark_results.csv",
    plot_prefix: str = "outfit_benchmark",
) -> None:
    """
    같은 입력으로 repeat번 실행해서:
      - 각 run의 latency/요약을 CSV로 저장
      - 전체 통계 요약을 콘솔에 출력
      - 박스플롯 + run-index vs time 그래프를 PNG로 저장
    """
    import csv
    import statistics
    from pathlib import Path

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        plt = None
        print("[WARN] matplotlib이 설치되어 있지 않아 그래프는 저장하지 않습니다.")
        print("       conda / pip 로 'matplotlib'를 설치하면 그래프 저장 가능.\n")

    print(f"[RUN_BENCHMARK] repeat={repeat}, celeb={celeb_name}, needs={needs}")
    print("-" * 60)

    records: List[dict] = []

    # 필요하면 1번 정도 워밍업 (옵션)
    # bench_once(celeb_name, needs, max_results, max_analyze_images)
    # print("[INFO] Warm-up run finished.\n")

    for i in range(repeat):
        print(f"\n--- Run {i+1}/{repeat} ---")
        res = bench_once(celeb_name, needs, max_results, max_analyze_images)
        res["run_idx"] = i + 1
        records.append(res)

    # 타임 배열
    quick_times = [r["dt_quick"] for r in records]
    ext_times = [r["dt_ext"] for r in records]

    # 통계 계산
    def stats(values: List[float]) -> dict:
        return {
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
            "median": statistics.median(values),
        }

    quick_stats = stats(quick_times)
    ext_stats = stats(ext_times)

    speedup = quick_stats["mean"] / ext_stats["mean"] if ext_stats["mean"] > 0 else None

    print("\n" + "#" * 60)
    print("[AGGREGATED STATS]")
    print("A) quick_web_outfit")
    for k, v in quick_stats.items():
        print(f"  - {k}: {v:.3f} sec")

    print("\nB) external + outfit_analyzer")
    for k, v in ext_stats.items():
        print(f"  - {k}: {v:.3f} sec")

    if speedup is not None:
        print(f"\n[INFO] 평균 기준으로, quick_web_outfit / external = {speedup:.2f} 배")
        if speedup < 1:
            print("       -> quick_web_outfit 쪽이 더 빠름")
        else:
            print("       -> external + outfit_analyzer 쪽이 더 빠름")

    print("#" * 60 + "\n")

    # CSV 저장
    csv_path = str(csv_path)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run_idx",
                "dt_quick",
                "dt_ext",
                "quick_looks_count",
                "ext_images_count",
            ],
        )
        writer.writeheader()
        for r in records:
            writer.writerow(r)

    print(f"[SAVE] CSV saved to: {csv_path}")

    # 그래프 저장 (matplotlib 있을 때만)
    if plt is not None:
        prefix = Path(plot_prefix)

        # 1) 박스플롯 (distribution 비교)
        plt.figure()
        plt.boxplot(
            [quick_times, ext_times],
            labels=["quick_web_outfit", "external+analyzer"],
        )
        plt.ylabel("Latency (sec)")
        plt.title(f"Latency Distribution (n={repeat})")
        boxplot_path = prefix.with_name(prefix.stem + "_box.png")
        plt.savefig(boxplot_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"[SAVE] Boxplot saved to: {boxplot_path}")

        # 2) run index vs time 라인 그래프
        x = list(range(1, repeat + 1))
        plt.figure()
        plt.plot(x, quick_times, marker="o", label="quick_web_outfit")
        plt.plot(x, ext_times, marker="o", label="external+analyzer")
        plt.xlabel("Run index")
        plt.ylabel("Latency (sec)")
        plt.title(f"Latency per Run (n={repeat})")
        plt.legend()
        lineplot_path = prefix.with_name(prefix.stem + "_line.png")
        plt.savefig(lineplot_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"[SAVE] Line plot saved to: {lineplot_path}")


def main():
    # 사용법:
    #   python -m services.outfit_benchmark "아이유" "여름,블레이저"
    #   python -m services.outfit_benchmark "아이유" "여름,블레이저" 100
    celeb = sys.argv[1] if len(sys.argv) > 1 else "아이유"
    needs_arg = sys.argv[2] if len(sys.argv) > 2 else "여름,블레이저"
    needs = [s.strip() for s in needs_arg.split(",") if s.strip()]

    # 세 번째 인자 있으면 repeat으로 사용
    if len(sys.argv) > 3:
        try:
            repeat = int(sys.argv[3])
        except ValueError:
            repeat = 1
    else:
        repeat = 1

    if repeat <= 1:
        # 기존처럼 한 번만 실행
        bench_once(celeb, needs)
    else:
        # N번 반복 + CSV/그래프
        run_benchmark(
            celeb_name=celeb,
            needs=needs,
            repeat=repeat,
        )


if __name__ == "__main__":
    main()
