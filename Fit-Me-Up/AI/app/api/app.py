# app/api/main.py
# -*- coding: utf-8 -*-
"""
AI Server main entry (FastAPI)

핵심 API:
1) POST /user/analyze-photo
   - 유저/연예인 사진 1장 → 얼굴형/체형/피부톤 + feature vector(UserAnalysisDTO)

2) POST /ai/clothes/analyze
   - 단일 의류 이미지(URL) → 스타일 태그 + 6D 벡터
   - 백엔드는 /clothes/<id>/analysis/ 에 이 결과를 저장

3) POST /ai/style/analyze
   - 여러 장의 코디/레퍼런스 이미지 → look/garment 단위 스타일 + 6D 벡터

디버깅용 기존 엔드포인트:
  /face, /body, /skin, /face/overlay, /body/overlay, /skin/overlay
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, HttpUrl

# 패키지 루트 인식용 (app/ 기준)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- 내부 모듈 import ---
from ..utils.image_io import load_image_bgr_from_bytes
from ..classifiers import face as face_mod
from ..classifiers import body as body_mod
from ..classifiers import skin as skin_mod

from ..services.clothes_analyzer import analyze_clothes_from_url
from ..services.outfit_analyzer import analyze_outfit_with_gpt
from ..services.url_analyzer import analyze_image_from_url
from ..services.image_searcher import search_reference_images
from ..services.outfit_embedding import style_vec_from_dict
from ..services.quick_web_outfit import quick_outfit_from_web
from ..services.appearance_gpt import analyze_image_from_url_gpt
from ..services.feature_builder import build_feature_vector


from ..api.dto import UserAnalysisDTO, UserAnalyzeResponse, ClothesAnalyzeRequest, ClothesAnalyzeResponse, GarmentDTO, LookDTO, StyleAnalyzeResponse, StyleAnalyzeRequest

# feature_builder가 아직 없을 수 있으니 fallback 제공
try:
    from ..services.feature_builder import build_feature_vector
except ImportError:
    def build_feature_vector(face_res: Dict[str, Any],
                             body_res: Dict[str, Any],
                             skin_res: Dict[str, Any]) -> List[float]:
        """
        임시 fallback: face/body/skin 문자열을 해시해서 간단한 3D 벡터 생성.
        나중에 실제 feature_builder 구현하면 이 함수는 자동으로 대체됨.
        """
        def _h(s: str) -> float:
            return (hash(s) % 1000) / 1000.0

        return [
            _h(face_res.get("face_shape", "unknown")),
            _h(body_res.get("body_shape", "unknown")),
            _h(skin_res.get("skin_tone", "unknown")),
        ]


app = FastAPI(
    title="Style Pipeline AI Server",
    version="1.0.0",
    description="User/Celeb analysis + Clothes/Style analysis",
)

# ======================================================
# 1) POST /user/analyze-photo
#    유저/연예인 사진 → UserAnalysisDTO
# ======================================================
@app.post("/user/analyze-photo", response_model=UserAnalyzeResponse)
async def analyze_user_photo_multi(
    face_image: UploadFile = File(...),
    body_image: UploadFile = File(...),
):
    """
    - face_image: 얼굴 위주 사진 (셀카 느낌)
      -> face_shape, skin_tone 분석
    - body_image: 전신 사진
      -> body_shape 분석

    최종적으로 face/body/skin + vector 를 한 번에 리턴.
    """

    # 1) 얼굴/피부용 이미지 로드
    face_bgr = load_image_bgr_from_bytes(await face_image.read())
    face_res, _ = face_mod.classify(face_bgr, return_debug=False)
    # 피부톤도 얼굴 위주 샷에서 뽑는 게 자연스럽다면:
    skin_res, _ = skin_mod.classify(face_bgr, return_debug=False)

    # 2) 체형용 이미지 로드
    body_bgr = load_image_bgr_from_bytes(await body_image.read())
    body_res, _ = body_mod.classify(body_bgr, return_debug=False)

    # 3) 공통 feature vector 생성 (기존 build_feature_vector 재사용)
    vec = build_feature_vector(face_res, body_res, skin_res)

    analysis = UserAnalysisDTO(
        id=None,
        user_id=None,
        face_shape=face_res.get("face_shape", "unknown"),
        body_shape=body_res.get("body_shape", "unknown"),
        skin_tone=skin_res.get("skin_tone", "unknown"),
        vector=vec,
    )

    return UserAnalyzeResponse(analysis=analysis)

class AnalyzeUserUrlMultiRequest(BaseModel):
    face_image_url: str
    body_image_url: str

@app.post("/user/analyze-url-multi", response_model=UserAnalyzeResponse)
async def analyze_user_url_multi(payload: AnalyzeUserUrlMultiRequest):
    # 1) 얼굴/피부
    face_data = analyze_image_from_url(payload.face_image_url)
    # 여기선 face_data 안에 face/body/skin 다 있지만,
    # 얼굴샷이니까 face/skin만 쓰고 body는 무시해도 됨
    face_res = face_data["face"]
    skin_res = face_data["skin"]

    # 2) 전신
    body_data = analyze_image_from_url(payload.body_image_url)
    body_res = body_data["body"]

    # 3) vector 생성
    vec = build_feature_vector(face_res, body_res, skin_res)

    analysis = UserAnalysisDTO(
        id=None,
        user_id=None,
        face_shape=face_res.get("face_shape", "unknown"),
        body_shape=body_res.get("body_shape", "unknown"),
        skin_tone=skin_res.get("skin_tone", "unknown"),
        vector=vec,
    )

    return UserAnalyzeResponse(analysis=analysis)


# ======================================================
# 2) POST /ai/clothes/analyze
#    단일 의류 이미지 → 스타일 태그 + 6D 벡터
# ======================================================
@app.post("/ai/clothes/analyze", response_model=ClothesAnalyzeResponse)
async def ai_clothes_analyze(payload: ClothesAnalyzeRequest):
    """
    의류 한 벌(image_url 기준)에 대해 스타일 메타데이터를 분석.

    백엔드 흐름 예:
      1) /clothes/ 에서 의류 목록 조회
      2) {id, name, image_url} 을 /ai/clothes/analyze 에 POST
      3) 여기서 받은 결과(category~vector)를
         /clothes/<id>/analysis/ 에 Body로 그대로 저장
    """
    raw = analyze_clothes_from_url(
        image_url=str(payload.image_url),
        name_hint=payload.name,
    )

    return ClothesAnalyzeResponse(
        clothes_id=payload.clothes_id,
        category=raw["category"],
        sub_category=raw["sub_category"],
        style=raw["style"],
        color=raw["color"],
        fit=raw["fit"],
        season=raw["season"],
        vector=raw["vector"],
    )


# ======================================================
# 3) POST /ai/style/analyze
#    레퍼런스 코디 이미지들 → look/garment 스타일 + 6D 벡터
# ======================================================

@app.post("/ai/style/analyze", response_model=StyleAnalyzeResponse)
async def ai_style_analyze(payload: StyleAnalyzeRequest):
    """
    1) 연예인 이름 + 스타일 니즈 기반 이미지 검색
    2) 상위 N개 URL을 GPT Vision으로 분석
    3) garment 항목마다 임베딩 벡터 생성
    """

    # 1) 이미지 검색
    search_items = search_reference_images(
        celeb_name=payload.celeb_name,
        needs=payload.needs,
        max_results=payload.max_results,
    )

    image_urls = [it.get("image") for it in search_items if it.get("image")]
    image_urls = image_urls[: payload.max_analyze_images]

    if not image_urls:
        return StyleAnalyzeResponse(
            input_images=[],
            looks=[],
            summary="검색된 이미지 없음",
        )

    # 2) GPT Vision 분석
    outfit_json = analyze_outfit_with_gpt(image_urls) # 첫 번째 레퍼런스만 분석하게 변경

    looks = outfit_json.get("looks", []) or []
    summary = outfit_json.get("summary", "")

    # 3) 벡터 추가
    final_looks: List[LookDTO] = []
    for idx, l in enumerate(looks):
        garments = []
        for g in l.get("garments", []):
            # 벡터 생성
            vec = style_vec_from_dict(g)

            garments.append(
                GarmentDTO(
                    name=g.get("name") or "",
                    category=g.get("category") or "",
                    sub_category=g.get("sub_category"),
                    style=g.get("style"),
                    color=g.get("color"),
                    fit=g.get("fit"),
                    season=g.get("season"),
                    vector=vec,
                )
            )

        final_looks.append(
            LookDTO(
                image_url=image_urls[idx] if idx < len(image_urls) else "",
                overall_style=l.get("overall_style"),
                garments=garments,
            )
        )

    return StyleAnalyzeResponse(
        input_images=image_urls,
        looks=final_looks,
        summary=summary,
    )
    
    


# ======================================================
# 디버깅용 기존 API (원하면 그대로 유지)
# ======================================================
# ======================================================
# 4) POST /ai/style/analyze/quick
#    quick_web_outfit 파이프라인 (web_search + vision 통합)
# ======================================================
@app.post("/ai/style/analyze/quick", response_model=StyleAnalyzeResponse)
async def ai_style_analyze_quick(payload: StyleAnalyzeRequest):
    """
    A 파이프라인:
      - quick_web_outfit 이 web_search + 이미지 선택 + 스타일 분석을 한 번에 수행
      - 반환된 looks 중에서 needs에 가장 잘 맞는 1개만 선택
      - 각 garment에 6D 스타일 벡터를 붙여서 반환
    """

    # 1) quick_web_outfit 호출 (연예인 + 니즈 기반)
    raw = quick_outfit_from_web(
        celeb_name=payload.celeb_name,
        needs=payload.needs,
    )
    # raw 예:
    # {
    #   "looks": [
    #       {
    #           "overall_style": "...",
    #           "garments": [...],
    #           "image_url": "...",
    #           "source_url": "..."
    #       },
    #       ...
    #   ],
    #   "summary": "..."
    # }

    # 2) needs 기준으로 "가장 잘 맞는 look 1개"만 선택
    looks = raw.get("looks") or [][:0] # 1개만 보여주게 함 나중에[:#] 여기 수정가능
    summary = raw.get("summary", "")

    final_looks: List[LookDTO] = []
    input_images: List[str] = []

    for look in looks:
        img_url = look.get("image_url") or ""
        if img_url:
            input_images.append(img_url)

        garments: List[GarmentDTO] = []
        for g in look.get("garments", []) or []:
            vec = style_vec_from_dict(g)

            garments.append(
                GarmentDTO(
                    name=g.get("name") or "",
                    category=g.get("category") or "",
                    sub_category=g.get("sub_category"),
                    style=g.get("style"),
                    color=g.get("color"),
                    fit=g.get("fit"),
                    season=g.get("season"),
                    vector=vec,
                )
            )

        final_looks.append(
            LookDTO(
                image_url=img_url,
                overall_style=look.get("overall_style"),
                garments=garments,
            )
        )

    return StyleAnalyzeResponse(
        input_images=input_images,
        looks=final_looks,
        summary=summary,
    )
    
    
@app.post("/user/analyze-url-multi-gpt", response_model=UserAnalyzeResponse)
async def analyze_user_url_multi_gpt(payload: AnalyzeUserUrlMultiRequest):
    """
    GPT Vision 기반 버전:
      - face_image_url → face_shape / skin_tone (body는 무시)
      - body_image_url → body_shape
      - build_feature_vector 로 3개 합쳐서 vector 생성
    """

    # 1) 얼굴/피부 (얼굴 위주 샷이니까 body는 무시해도 됨)
    face_data = analyze_image_from_url_gpt(payload.face_image_url)
    if not face_data:
        raise HTTPException(status_code=400, detail="Failed to analyze face image with GPT.")

    face_res = face_data["face"]
    skin_res = face_data["skin"]

    # 2) 전신 (body_shape만 사용)
    body_data = analyze_image_from_url_gpt(payload.body_image_url)
    if not body_data:
        raise HTTPException(status_code=400, detail="Failed to analyze body image with GPT.")

    body_res = body_data["body"]

    # 3) vector 생성 (기존과 동일한 인터페이스 사용)
    vec = build_feature_vector(face_res, body_res, skin_res)

    analysis = UserAnalysisDTO(
        id=None,
        user_id=None,
        face_shape=face_res.get("face_shape", "unknown"),
        body_shape=body_res.get("body_shape", "unknown"),
        skin_tone=skin_res.get("skin_tone", "unknown"),
        vector=vec,
    )

    return UserAnalyzeResponse(analysis=analysis)


@app.post("/face")
async def api_face(image: UploadFile = File(...)):
    bgr = load_image_bgr_from_bytes(await image.read())
    res, _ = face_mod.classify_face_shape(bgr, return_debug=False)
    return JSONResponse(res)


@app.post("/body")
async def api_body(image: UploadFile = File(...)):
    bgr = load_image_bgr_from_bytes(await image.read())
    res, _ = body_mod.classify_body_shape(bgr, return_debug=False)
    return JSONResponse(res)


@app.post("/skin")
async def api_skin(image: UploadFile = File(...)):
    bgr = load_image_bgr_from_bytes(await image.read())
    res, _ = skin_mod.classify_skin_tone(bgr, return_debug=False)
    return JSONResponse(res)


@app.post("/face/overlay")
async def face_overlay(image: UploadFile = File(...)):
    bgr = load_image_bgr_from_bytes(await image.read())
    _, dbg = face_mod.classify_face_shape(bgr, return_debug=True)
    return Response(content=dbg, media_type="image/png")


@app.post("/body/overlay")
async def body_overlay(image: UploadFile = File(...)):
    bgr = load_image_bgr_from_bytes(await image.read())
    _, dbg = body_mod.classify_body_shape(bgr, return_debug=True)
    return Response(content=dbg, media_type="image/png")


@app.post("/skin/overlay")
async def skin_overlay(image: UploadFile = File(...)):
    bgr = load_image_bgr_from_bytes(await image.read())
    _, dbg = skin_mod.classify_skin_tone(bgr, return_debug=True)
    return Response(content=dbg, media_type="image/png")
