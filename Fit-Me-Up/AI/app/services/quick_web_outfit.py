# app/services/quick_web_outfit.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, sys
from typing import List
from dotenv import load_dotenv
from openai import OpenAI
import time

load_dotenv()

client = OpenAI()
print("has responses?", hasattr(client, "responses"))

MODEL = os.getenv("OPENAI_OUTFIT_WEB_MODEL", "gpt-5")  # 필요하면 o4-mini 등으로 변경 가능


PROMPT_TEMPLATE = """
역할: 당신은 패션 스타일리스트 + 웹 리서처입니다.

목표:
- "{celeb}"의 실제 코디 사진들을 웹에서 찾아,
- 사용자가 요구한 "{needs}" 상황/스타일에 맞는 룩 3~5개를 고르고,
- 각 룩을 구조적인 JSON으로만 정리하세요.

지침:
1. 먼저 web_search 도구를 사용해 "{celeb} {needs}" 관련 이미지를 포함한 페이지들을 찾으세요.
2. 이미지나 캡션/문맥을 바탕으로, 실제 착장을 최대한 구체적으로 추론하세요.
3. 동일한 코디가 중복되지 않도록 3~5개의 서로 다른 룩을 선택하세요.
4. 아래 스키마로만 응답하고, JSON 이외의 텍스트는 절대 출력하지 마세요.

출력 JSON 스키마:
{{
  "celeb_name": string,
  "query_needs": [string],
  "looks": [
    {{
      "title": string,            # 예: "아이유 화이트 블레이저 여름 공항룩"
      "image_url": string,        # 대표 이미지 URL
      "source_url": string,       # 원본 페이지 URL
      "garments": [
        {{
          "category": "top" | "bottom" | "outer" | "dress" | "shoes" | "bag" | "accessory",
          "name": string,         # 예: "화이트 린넨 블레이저"
          "color": string | null, # 예: "white"
          "material": string | null, # 예: "linen"
          "fit": string | null    # 예: "oversized", "regular", "slim"
        }}
      ]
    }}
  ]
}}
"""

def quick_outfit_from_web(celeb_name: str, needs: List[str]) -> dict:
    """GPT가 web_search를 포함해서 레퍼런스 코디를 찾고, JSON으로 정리."""
    print("[DEBUG] quick_outfit_from_web() called")
    needs_clean = [n for n in needs if n]
    prompt = PROMPT_TEMPLATE.format(
        celeb=celeb_name,
        needs=", ".join(needs_clean) if needs_clean else "일반 코디"
    )

    # 전체 함수 시간 측정 시작
    func_start = time.perf_counter()
    
    print("[DEBUG] calling client.responses.create()...")
    resp = client.responses.create(
        model=MODEL,
        tools=[{"type": "web_search"}],
        tool_choice="auto",
        input=prompt,
        # JSON만 받도록 강하게 유도 (Responses는 response_format 옵션이 없어도 이 정도면 충분)
        # 모델이 텍스트를 섞으면 아래에서 json.loads에서 에러 날 수 있으니 try/except 처리.
    )
    print("[DEBUG] got response from API")

    text = resp.output_text  # SDK가 편하게 합쳐준 텍스트
    print("[DEBUG] resp.output_text len =", len(text) if isinstance(text, str) else type(text))
    
    try:
        data = json.loads(text)
    except Exception:
        # 혹시라도 모델이 설명 문장을 섞었다면, { ... } 부분만 잘라내는 아주 단순한 fallback
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end+1])
            except Exception:
                data = {"error": "failed_to_parse_json", "raw": text}
        else:
            data = {"error": "no_json_found", "raw": text}

    total = time.perf_counter() - func_start
    print(f"[DEBUG] quick_outfit_from_web() TOTAL {total:.2f} seconds")
    
    return data

if __name__ == "__main__":
    # 사용 예:
    #   python -m services.quick_web_outfit "아이유" "여름,블레이저"
    print("[DEBUG] __main__ block entered")

    celeb = sys.argv[1] if len(sys.argv) > 1 else "아이유"
    needs_arg = sys.argv[2] if len(sys.argv) > 2 else "여름,블레이저"
    needs = [s.strip() for s in needs_arg.split(",") if s.strip()]

    print(f"[TEST] celeb={celeb}, needs={needs}")
    try:
        result = quick_outfit_from_web(celeb, needs)
        print("\n[RESULT JSON]")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print("[ERROR in __main__]", repr(e))