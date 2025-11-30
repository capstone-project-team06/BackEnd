# app/services/clothes_analyzer.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
from typing import Dict, Any, List, Optional
from .outfit_embedding import style_to_vec
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
client = OpenAI()

CLOTHES_PROMPT = """
당신은 '온라인 패션 쇼핑몰 상품 메타데이터 태거'입니다.
입력으로 단일 의류 상품 이미지(상, 하의, 아우터, 원피스 등)를 보고
아래 스키마에 맞춰 JSON만 출력하세요.

[필수 필드]
- category: 대분류 (영어 소문자)
    - "top", "bottom", "outer", "dress", "shoes", "bag", "accessory" 중 하나
- sub_category: 조금 더 구체적인 카테고리 (영어 소문자)
    - 예: "tshirt", "shirt", "blouse", "hoodie", "knit", "jeans", "slacks",
          "skirt", "coat", "jacket", "cardigan", "sneakers", "boots" 등
- style: 전반적인 스타일 태그 (영어 소문자)
    - 예: "minimal", "street", "casual", "formal", "romantic", "sporty", "retro"
    - 모호할 땐 가장 대표되는 스타일 1개만 선택
- color: 가장 주된 색상을 영어 소문자 한 단어로
    - 예: "white", "black", "beige", "gray", "navy", "brown", "pink", "blue", "green"
- fit: 실루엣/핏 (영어 소문자)
    - "slim", "regular", "oversized", "relaxed" 중에서 가장 가까운 것
- season: 주로 어울리는 계절 (영어 소문자)
    - "spring", "summer", "fall", "winter", "all" 중 하나

[출력 JSON 스키마]
{
  "category": string,
  "sub_category": string,
  "style": string,
  "color": string,
  "fit": string,
  "season": string
}

- 설명 문장 없이 JSON만 출력하세요.
- 보이지 않는 정보는 추측하지 말고 가장 안전한 기본값을 선택하세요.
"""

# -----------------------
# 메인 분석 함수
# -----------------------


def analyze_clothes_from_url(
    image_url: str,
    name_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    단일 의류 이미지 URL을 입력 받아,
    백엔드 /clothes/<id>/analysis/ Body와 동일한 형태의 dict를 반환.

    반환 예:
    {
      "category": "top",
      "sub_category": "tshirt",
      "style": "minimal",
      "color": "white",
      "fit": "oversized",
      "season": "summer",
      "vector": [0.8, 0.8, 0.4, 0.8, 0.0, 0.9]   # 6D vector
    }
    """

    # 1) user 메시지 content 구성
    user_content: List[Dict[str, Any]] = []

    base_text = "다음 이미지는 단일 의류 상품 사진입니다. 위 규칙에 맞춰 JSON으로만 분석해 주세요."
    if name_hint:
        base_text += f'\n상품명 힌트: "{name_hint}" 도 참고해서 category/sub_category/style을 정교하게 선택해 주세요.'
    user_content.append({"type": "text", "text": base_text})

    user_content.append({
        "type": "image_url",
        "image_url": {"url": image_url}
    })

    # 2) GPT Vision 호출
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        temperature=0.2,
        max_tokens=600,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": CLOTHES_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    content = resp.choices[0].message.content or "{}"

    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        raw = {}

    category = raw.get("category", "top")
    sub_category = raw.get("sub_category", "tshirt")
    style = raw.get("style", "minimal")
    color = raw.get("color", "white")
    fit = raw.get("fit", "regular")
    season = raw.get("season", "all")

    # 3) Generate 6D vector
    vec = style_to_vec(style, season, color, category, fit)

    # 4) 백엔드 /clothes/<id>/analysis/ Body와 동일 구조로 반환
    return {
        "category": category,
        "sub_category": sub_category,
        "style": style,
        "color": color,
        "fit": fit,
        "season": season,
        "vector": vec,
    }


# -----------------------
# 간단 CLI 테스트
# -----------------------
if __name__ == "__main__":
    test_url = "https://fit-me-up-s3bucket.s3.ap-northeast-2.amazonaws.com/clothes/4fea8844-7ae4-4728-a2db-c7d93b79e559.jpg"
    print("[TEST] analyze_clothes_from_url() 실행...")
    res = analyze_clothes_from_url(test_url, name_hint="헨리넥 롱슬리브 [그레이]")
    print(json.dumps(res, ensure_ascii=False, indent=2))
