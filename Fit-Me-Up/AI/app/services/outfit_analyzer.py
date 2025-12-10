# app/services/outfit_analyzer.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import requests
import os, json
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Vision 모델 (원하면 gpt-4o-mini 등으로 바꿔도 됨)
VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")

client = OpenAI()

def _url_to_data_image(url: str, timeout: float = 8.0) -> str | None:
    """
    원격 이미지 URL -> data:image/...;base64,... 형태로 변환.
    OpenAI 서버가 직접 다운로드하지 않게 하기 위함.
    """
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "style-pipeline/1.0"})
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg")
        if not content_type.startswith("image/"):
            content_type = "image/jpeg"
        b64 = base64.b64encode(r.content).decode("utf-8")
        return f"data:{content_type};base64,{b64}"
    except Exception as e:
        # 디버그용으로만 출력
        print(f"[outfit_analyzer] _url_to_data_image ERROR url={url}, err={e}")
        return None


def analyze_outfit_with_gpt(image_urls: List[str]) -> Dict[str, Any]:
    """
    여러 장의 코디 이미지를 GPT Vision으로 분석해서
    공통된 스타일/아이템 정보를 JSON으로 반환.

    입력:
        image_urls: 분석할 이미지 URL 리스트

    반환 예시(자유도 있음, 지금은 대략 이런 구조를 가정):
    최종 스키마:
    {
      "looks": [
        {
          "overall_style": "minimal casual / formal office look / street / romantic 등",
          "garments": [
            {
              "name": "...",
              "category": "top|bottom|outer|dress|shoes|bag|accessory",
              "sub_category": "tshirt|shirt|jeans|skirt|blazer ...",
              "style": "minimal|street|classic|romantic|hiphop|cityboy|amekaji|formal",
              "color": "white|black|gray|navy|beige|brown|blue|red|green ...",
              "fit": "slim|regular|oversized|relaxed",
              "season": "spring|summer|fall|winter|all"
            }
          ],
          "image_url": "원래 입력 이미지 URL (파이썬에서 덮어씀)"
        }
      ],
      "summary": "전체 코디 특징 요약"
    }
    """
    if not image_urls:
        return {"looks": [], "summary": "no images"}

    # system 메시지: 역할 + 출력 포맷 힌트
    OUTFIT_PROMPT = """
        당신은 패션 전문 스타일리스트이자 패션 데이터셋 라벨러입니다.
        당신의 임무는 이미지 속 코디를 사람이 이해하기 쉽고, 기계가 재사용하기 좋은
        정규화된 JSON 구조로 표현하는 것입니다.

        =====================================================================
        [분석 대상]
        - 이미지 속 인물이 실제로 착용하고 있는 옷/신발/가방/악세사리만 추출하세요.
        - 배경 사물, 의자가 걸려 있는 옷, 그림 속 패턴은 절대 포함하지 마세요.
        - 여러 장의 이미지가 입력될 수 있으며, 각 이미지 → 하나의 look 으로 분석합니다.

        =====================================================================
        [필수 규칙 — 반드시 준수해야 합니다]
        1) 추측 금지: 보이지 않는 부위(예: 신발이 안 보임)는 절대 생성하지 말고 제외합니다.
        2) 실제 착용 아이템만 추출합니다. (옷걸이, 배경, 광고 텍스트 무시)
        3) 각 garment(아이템)에는 아래 필드를 반드시 포함해야 합니다:

        {
        "name": "사람이 이해할 수 있는 구체 명칭 (예: '화이트 린넨 크롭 블레이저')",
        "category": "top | bottom | outer | dress | shoes | bag | accessory",
        "sub_category": "tshirt | shirt | knit | hoodie | jeans | slacks | skirt | coat | jacket | blazer 등",
        "style": "minimal | street | classic | romantic | hiphop | cityboy | amekaji | formal 등 스타일 태그 1개",
        "color": "white | black | gray | navy | beige | brown | blue | red | green 등 기본 색상 이름",
        "fit": "slim | regular | oversized | relaxed",
        "season": "spring | summer | fall | winter | all"
        }

        ⚠ 중요:
        - 보이지 않는 정보는 무조건 "unknown" 대신 정확히 "all" 또는 "unknown" 으로 구분하여 넣어야 합니다.
        - season은 착용한 옷의 두께/스타일 기준으로 한계절 선택하거나, 모든 계절 가능하면 "all".
        - 모든 라벨은 영어 소문자로 표준화합니다.

        ============================================================
        [최종 출력 JSON 스키마 — 이 형식을 반드시 그대로 따르세요]
        
        {
        "looks": [
            {
            "overall_style": "미니멀 캐주얼 / 포멀 오피스룩 / 스트릿 / 로맨틱 등",
            "garments": [
                {
                    "name": "...",
                    "category": "...",
                    "sub_category": "...",
                    "style": "...",
                    "color": "...",
                    "fit": "...",
                    "season": "..."
                }
            ]
            }
        ],
        "summary": "전체 코디 특징 요약"
        }
        ============================================================

        [설명하지 말고 JSON만 출력하세요.]
    """

    # user 메시지 content 구성
    user_content: List[Dict[str, Any]] = []

    '''
    # 1) 텍스트 설명
    user_text = (
        "다음 이미지들에 대해 위에서 설명한 JSON 스키마에 맞춰 분석해줘.\n"
        "이미지들은 모두 같은 연예인(또는 비슷한 사람)의 코디 참고용이야.\n"
        "각 look마다 image_url 필드에 해당 이미지 URL을 그대로 넣어줘."
    )
    user_content.append({"type": "text", "text": user_text})

    # 2) 이미지 URL들 추가 (중요: type='image_url')
    for url in image_urls:
        if not url:
            continue
        user_content.append({
            "type": "image_url",
            "image_url": {"url": url}
        })'''
        
    # 1) 텍스트 설명
    user_text = (
        "다음 이미지들에 대해 위에서 설명한 JSON 스키마에 맞춰 분석해줘.\n"
        "이미지들은 모두 같은 연예인(또는 비슷한 사람)의 코디 참고용이야.\n"
        "각 look마다 image_url 필드에 해당 이미지 URL을 그대로 넣어줘."
    )
    user_content.append({"type": "text", "text": user_text})

    # 2) 이미지들을 data:image/...;base64 로 변환해서 추가
    valid_image_count = 0
    for url in image_urls:
        if not url:
            continue

        data_url = _url_to_data_image(url)
        if not data_url:
            # 다운로드 실패한 URL은 스킵
            continue

        user_content.append({
            "type": "image_url",
            "image_url": {"url": data_url}
        })
        valid_image_count += 1

    if valid_image_count == 0:
        # 이미지 하나도 못 가져왔으면 안전하게 fallback
        return {"looks": [], "summary": "no valid images"}


    # GPT 호출
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        temperature=0.2,
        max_tokens=1200,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": OUTFIT_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    content = resp.choices[0].message.content or "{}"

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # 혹시 모델이 JSON이 아닌 걸 내보내면, 최소한 래핑해서 반환
        data = {"raw": content}

    # 안전장치: 필드 기본값 보정
    data.setdefault("looks", [])
    if not isinstance(data["looks"], list):
        data["looks"] = []

    if "summary" not in data:
        # looks를 기반으로 간단 요약 만들어 넣기
        data["summary"] = f"{len(data['looks'])}개의 코디를 분석한 결과."
        
        # 🔥 여기서부터 URL 강제 매핑
    looks = data.get("looks")
    if isinstance(looks, list):
        for idx, look in enumerate(looks):
            if idx < len(image_urls):
                # 모델이 써준 image_url은 버리고, 우리가 입력한 URL을 덮어쓴다
                look["image_url"] = image_urls[idx]

    return data



# --------------------------------------------------
# 간단 CLI 테스트용 (선택)
# --------------------------------------------------
if __name__ == "__main__":
    # 예시: 임의의 이미지 URL들로 테스트
    test_urls = [
        # 실제 패션 이미지 URL을 넣어서 테스트하면 됨
        "https://example.com/some-outfit-image1.jpg",
        "https://example.com/some-outfit-image2.jpg",
    ]
    print("[TEST] analyze_outfit_with_gpt() 실행...")
    res = analyze_outfit_with_gpt(test_urls)
    print(json.dumps(res, ensure_ascii=False, indent=2))