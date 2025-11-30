# app/api/dto.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# ============================================
# 1) Backend → AI 서버 통신용 DTO
# ============================================

class UserBriefDTO(BaseModel):
    """
    /account/info/ 응답에 대응하는 구조
    - user basic info
    """
    id: int
    username: str
    gender: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None


class OnboardingDTO(BaseModel):
    """
    backend onboarding 구조 변환:
    {
      "styles": [...],
      "preferred_colors": [...],
      "preferred_fits": [...]
    }
    → AI 내부에서는 colors / fits 로 명칭 통일
    """
    styles: List[str] = []
    colors: List[str] = []     # rename from preferred_colors
    fits: List[str] = []       # rename from preferred_fits


class UserAnalysisDTO(BaseModel):
    """
    UserAnalysis (유저 사진 분석 결과)
    - backend가 저장 → 나중에 다시 /style/profile 호출 시 전달받음
    """
    id: Optional[int] = None
    user_id: Optional[int] = None
    face_shape: str
    body_shape: str
    skin_tone: str
    vector: List[float]


# ============================================
# 2) Celebrity
# ============================================

class CelebrityDTO(BaseModel):
    id: int
    name: str
    gender: Optional[str] = None
    image_url: Optional[str] = None
    vector: Optional[List[float]] = None  # 연예인 feature vector


# ============================================
# 3) Reference (연예인 기반 스타일 프로필)
# ============================================

class ReferenceImageDTO(BaseModel):
    image: str
    thumb: Optional[str] = None
    page: Optional[str] = None
    source: str
    host: Optional[str] = None


class ReferenceDTO(BaseModel):
    celeb_id: int
    celeb_name: str
    similarity_score: float
    reference_images: List[ReferenceImageDTO]
    outfit_json: Dict[str, Any]
    reason: Optional[str] = None


# ============================================
# 4) API DTO (AI Server Endpoint)
# ============================================

class UserAnalyzeResponse(BaseModel):
    analysis: UserAnalysisDTO


class StyleProfileRequest(BaseModel):
    """
    POST /style/profile 요청
    백엔드가 user_analysis + onboarding + celeb_id(매칭 결과)를 넘겨줌
    """
    user_analysis: UserAnalysisDTO
    onboarding: Optional[OnboardingDTO] = None
    celeb_id: int
    celeb_name: str


class StyleProfileResponse(BaseModel):
    """
    AI response: user info + reference outfit info 반환
    """
    user_analysis: UserAnalysisDTO
    onboarding: Optional[OnboardingDTO]
    reference: ReferenceDTO


# ============================================
# 5) Clothes 분석 API
# ============================================

class ClothesAnalyzeRequest(BaseModel):
    clothes_id: int
    image_url: str
    name: Optional[str] = None


class ClothesAnalyzeResponse(BaseModel):
    clothes_id: int
    category: str
    sub_category: str
    style: str
    color: str
    fit: str
    season: str
    vector: List[float]


# ============================================
#  레퍼런스 search 및 분석 API
# ============================================

class StyleAnalyzeRequest(BaseModel):
    celeb_name: str
    needs: List[str]
    max_results: Optional[int] = 12
    max_analyze_images: Optional[int] = 6


class GarmentDTO(BaseModel):
    name: str
    category: str
    sub_category: Optional[str] = None
    style: Optional[str] = None
    color: Optional[str] = None
    fit: Optional[str] = None
    season: Optional[str] = None
    vector: Optional[List[float]] = None


class LookDTO(BaseModel):
    image_url: str
    overall_style: Optional[str] = None
    garments: List[GarmentDTO]


class StyleAnalyzeResponse(BaseModel):
    input_images: List[str]
    looks: List[LookDTO]
    summary: str = ""
