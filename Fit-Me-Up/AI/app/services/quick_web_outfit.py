# app/services/quick_web_outfit.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, sys, time
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI
from string import Template

# STEP 2에서 Vision 분석 위해 이 함수 필요함
from services.outfit_analyzer import analyze_outfit_with_gpt

load_dotenv()
client = OpenAI()

MODEL = os.getenv("OPENAI_OUTFIT_WEB_MODEL", "gpt-5")

# -------------------------------
# STEP 1: 이미지 URL 후보 선정용 프롬프트
# -------------------------------
PROMPT_SELECT_IMAGES = Template("""
당신은 패션 웹 리서처입니다.
목표:
- "$celeb" + "$needs" 관련된 실제 착장 사진을 찾기 위해 web_search 도구를 사용하고
- 중복되지 않는 좋은 품질의 실제 코디 이미지 3~5장을 선정하세요.
- 이미지 직접 URL(image_url)과 그 URL을 포함한 페이지(source_url)를 JSON으로 출력하세요.

출력 스키마:
{
  "selected_images": [
    {"image_url": "...", "source_url": "..."},
    ...
  ]
}

JSON만 출력하세요.
""")



def select_images_from_web(celeb: str, needs: List[str]) -> List[Dict[str, str]]:
    """STEP 1: GPT web_search 로 이미지 URL 3~5개 선정."""
    needs_txt = ", ".join(needs)
    prompt = PROMPT_SELECT_IMAGES.substitute(celeb=celeb, needs=needs_txt)

    resp = client.responses.create(
        model=MODEL,
        tools=[{"type": "web_search"}],
        tool_choice="auto",
        input=prompt,
    )

    text = resp.output_text
    try:
        data = json.loads(text)
    except:
        # fallback parsing
        s = text.find("{")
        e = text.rfind("}")
        data = json.loads(text[s:e+1])

    images = data.get("selected_images", [])
    clean = []
    for it in images:
        if it.get("image_url"):
            clean.append({
                "image_url": it["image_url"],
                "source_url": it.get("source_url", "")
            })
    return clean



# -------------------------------
# STEP 2 + STEP 3: Vision 분석 + Merge
# -------------------------------
def quick_outfit_from_web(celeb: str, needs: List[str]) -> Dict[str, Any]:
    """A 파이프라인: 이미지 선정 + Vision 분석 -> 최종 JSON"""
    print("[A] STEP 1: 이미지 후보 선정 시작...")
    t0 = time.perf_counter()

    selected = select_images_from_web(celeb, needs)
    print(f"[A] STEP 1: 완료. 선정된 이미지 {len(selected)}개")

    if not selected:
        return {"looks": [], "summary": "이미지를 찾지 못함"}

    # Vision 분석용 URL 리스트
    image_urls = [x["image_url"] for x in selected]

    print("[A] STEP 2: Vision 분석 시작...")
    vision_json = analyze_outfit_with_gpt(image_urls)

    # Vision 결과의 looks에 source_url 붙이기
    looks = vision_json.get("looks", [])
    for i, look in enumerate(looks):
        if i < len(selected):
            look["source_url"] = selected[i].get("source_url")

    total = time.perf_counter() - t0
    print(f"[A] TOTAL = {total:.2f} sec")

    return {
        "looks": looks,
        "summary": vision_json.get("summary", ""),
        "selected_images": selected,
        "time_sec": total
    }



# --------------------------------------------------
# CLI 테스트
# --------------------------------------------------
if __name__ == "__main__":
    celeb = sys.argv[1] if len(sys.argv) > 1 else "아이유"
    needs_arg = sys.argv[2] if len(sys.argv) > 2 else "여름,블레이저"
    needs = [s.strip() for s in needs_arg.split(",") if s.strip()]

    result = quick_outfit_from_web(celeb, needs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
