from math import sqrt
from typing import List, Optional

import math
import requests

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from accounts.models import UserAnalysis
from celebrity.models import Celebrity, CelebrityAnalysis
from clothes.models import Clothes, ClothesAnalysis
from clothes.serializers import ClothesSerializer
from .models import RecommendationRequest
from .serializers import RecommendationRequestSerializer


# -----------------------------
# 공통: 코사인 유사도
# -----------------------------
def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# -----------------------------
# 추천 요청 저장용 API
# -----------------------------
class RecommendationRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = RecommendationRequest.objects.filter(user=request.user)
        serializer = RecommendationRequestSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = RecommendationRequestSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            instance = serializer.save()
            return Response(
                RecommendationRequestSerializer(instance).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------
# 연예인 착장만 분석해서 그대로 보여주는 API
# (우리 옷 매칭 없이, AI 응답만 보고 싶을 때)
# -----------------------------
class CelebrityStyleOnlyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1) 유저 분석 확인
        try:
            user_analysis = UserAnalysis.objects.get(user=user)
        except UserAnalysis.DoesNotExist:
            return Response(
                {"detail": "먼저 유저 분석(UserAnalysis)이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_vec = user_analysis.vector or []
        if not user_vec:
            return Response(
                {"detail": "유저 분석 벡터(vector)가 비어 있습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) 최신 RecommendationRequest
        req: Optional[RecommendationRequest] = (
            RecommendationRequest.objects
            .filter(user=user)
            .order_by("-id")
            .first()
        )
        if not req:
            return Response(
                {"detail": "먼저 추천 요청(RecommendationRequest)을 생성해 주세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3) needs 구성
        styles = user.styles
        styles_text = ""
        if isinstance(styles, list):
            styles_text = ", ".join(map(str, styles))
        elif isinstance(styles, dict):
            styles_text = ", ".join(map(str, styles.get("keywords", [])))

        main_cats = req.main_categories or []
        sub_cats = req.sub_categories or []
        situations = (req.situation or "").strip()

        parts = []
        if situations:
            parts.append(f"상황: {situations}")
        if styles_text:
            parts.append(f"선호 스타일: {styles_text}")
        if main_cats:
            parts.append("메인 카테고리: " + ", ".join(main_cats))
        if sub_cats:
            parts.append("세부 카테고리: " + ", ".join(sub_cats))

        if parts:
            needs_text = " / ".join(parts)
            needs_list = parts
        else:
            needs_text = "일상적인 데일리 코디"
            needs_list = [needs_text]

        # 4) 유사 연예인 찾기
        celeb_analyses = CelebrityAnalysis.objects.select_related("celebrity").all()
        if user.gender:
            celeb_analyses = celeb_analyses.filter(celebrity__gender=user.gender)

        best_celeb = None
        best_sim = -1.0
        for ca in celeb_analyses:
            sim = cosine_similarity(user_vec, ca.vector or [])
            if sim > best_sim:
                best_sim = sim
                best_celeb = ca

        if not best_celeb:
            return Response(
                {"detail": "유사도를 계산할 연예인 분석 데이터가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        celeb = best_celeb.celebrity

        # 5) AI 서버 호출 (연예인 착장 분석만)
        try:
            ai_url = f"{settings.AI_SERVER_URL}/ai/style/analyze"
            payload = {
                "celeb_name": celeb.name,
                "needs": needs_list,
                "max_results": 10,
                "max_analyze_images": 3,
            }
            ai_resp = requests.post(ai_url, json=payload, timeout=120)
            ai_resp.raise_for_status()
            ai_json = ai_resp.json()
        except Exception as e:
            return Response(
                {
                    "detail": "AI 스타일 분석 호출에 실패했습니다.",
                    "error": str(e),
                    "matched_celebrity": {
                        "id": celeb.id,
                        "name": celeb.name,
                        "gender": celeb.gender,
                        "face_shape": best_celeb.face_shape,
                        "body_shape": best_celeb.body_shape,
                        "skin_tone": best_celeb.skin_tone,
                    },
                    "needs": needs_text,
                    "needs_list": needs_list,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "matched_celebrity": {
                    "id": celeb.id,
                    "name": celeb.name,
                    "gender": celeb.gender,
                    "face_shape": best_celeb.face_shape,
                    "body_shape": best_celeb.body_shape,
                    "skin_tone": best_celeb.skin_tone,
                    "similarity": best_sim,
                },
                "user_analysis": {
                    "face_shape": user_analysis.face_shape,
                    "body_shape": user_analysis.body_shape,
                    "skin_tone": user_analysis.skin_tone,
                },
                "needs": needs_text,
                "needs_list": needs_list,
                "ai_style": ai_json,  # 연예인 착장 원본 정보
            },
            status=status.HTTP_200_OK,
        )


# -----------------------------
# 우리 DB 옷까지 매칭해서
# "실제 구매용 추천"까지 주는 메인 API
# -----------------------------
class RecommendStyleFromCelebrityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1) 유저 분석 확인
        try:
            user_analysis = UserAnalysis.objects.get(user=user)
        except UserAnalysis.DoesNotExist:
            return Response(
                {"detail": "먼저 유저 분석(UserAnalysis)이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_vec = user_analysis.vector or []
        if not user_vec:
            return Response(
                {"detail": "유저 분석 벡터(vector)가 비어 있습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) 가장 최근 RecommendationRequest 가져오기
        req: Optional[RecommendationRequest] = (
            RecommendationRequest.objects
            .filter(user=user)
            .order_by("-id")
            .first()
        )
        if not req:
            return Response(
                {"detail": "먼저 추천 요청(RecommendationRequest)을 생성해 주세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3) needs(텍스트 + 리스트) 구성
        styles = user.styles
        styles_text = ""
        if isinstance(styles, list):
            styles_text = ", ".join(map(str, styles))
        elif isinstance(styles, dict):
            styles_text = ", ".join(map(str, styles.get("keywords", [])))

        main_cats = req.main_categories or []
        sub_cats = req.sub_categories or []
        situations = (req.situation or "").strip()

        parts = []
        if situations:
            parts.append(f"상황: {situations}")
        if styles_text:
            parts.append(f"선호 스타일: {styles_text}")
        if main_cats:
            parts.append("메인 카테고리: " + ", ".join(main_cats))
        if sub_cats:
            parts.append("세부 카테고리: " + ", ".join(sub_cats))

        if parts:
            needs_text = " / ".join(parts)
            needs_list = parts
        else:
            needs_text = "일상적인 데일리 코디"
            needs_list = [needs_text]

        # 4) 가장 비슷한 연예인 찾기
        celeb_analyses = CelebrityAnalysis.objects.select_related("celebrity").all()
        if user.gender:
            celeb_analyses = celeb_analyses.filter(celebrity__gender=user.gender)

        best_celeb = None
        best_sim = -1.0
        for ca in celeb_analyses:
            sim = cosine_similarity(user_vec, ca.vector or [])
            if sim > best_sim:
                best_sim = sim
                best_celeb = ca

        if not best_celeb:
            return Response(
                {"detail": "유사도를 계산할 연예인 분석 데이터가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        celeb = best_celeb.celebrity

        # 5) AI 서버 호출 → 연예인 착장 분석
        try:
            ai_url = f"{settings.AI_SERVER_URL}/ai/style/analyze"
            payload = {
                "celeb_name": celeb.name,
                "needs": needs_list,
                "max_results": 10,
                "max_analyze_images": 3,
            }
            ai_resp = requests.post(ai_url, json=payload, timeout=120)
            ai_resp.raise_for_status()
            ai_json = ai_resp.json()
        except Exception as e:
            return Response(
                {
                    "detail": "AI 스타일 분석 호출에 실패했습니다.",
                    "error": str(e),
                    "matched_celebrity": {
                        "id": celeb.id,
                        "name": celeb.name,
                        "gender": celeb.gender,
                        "face_shape": best_celeb.face_shape,
                        "body_shape": best_celeb.body_shape,
                        "skin_tone": best_celeb.skin_tone,
                    },
                    "needs": needs_text,
                    "needs_list": needs_list,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        looks = ai_json.get("looks") or []
        summary = ai_json.get("summary", "")

        # 6) 연예인 착장에서 모든 garments 모으기
        all_garments = []
        for look in looks:
            for g in (look.get("garments") or []):
                all_garments.append(g)

        # 7) 카테고리별로 우리 옷 2개씩 추천
        recommendations = self._recommend_by_main_categories(
            garments=all_garments,
            main_categories=main_cats,
        )

        # 8) 응답
        req_serializer = RecommendationRequestSerializer(req)

        return Response(
            {
                "matched_celebrity": {
                    "id": celeb.id,
                    "name": celeb.name,
                    "gender": celeb.gender,
                    "face_shape": best_celeb.face_shape,
                    "body_shape": best_celeb.body_shape,
                    "skin_tone": best_celeb.skin_tone,
                    "similarity": best_sim,
                },
                "user_analysis": {
                    "face_shape": user_analysis.face_shape,
                    "body_shape": user_analysis.body_shape,
                    "skin_tone": user_analysis.skin_tone,
                },
                "recommendation_request": req_serializer.data,
                "needs": needs_text,
                "summary": summary,
                "recommendations": recommendations,
            },
            status=status.HTTP_200_OK,
        )

    # -------------------------
    # 카테고리별 상위 2개 추천 로직
    # -------------------------
    def _recommend_by_main_categories(self, garments, main_categories):
        """
        garments: AI가 분석한 연예인 착장의 garment들 (list of dict)
        main_categories: 유저가 선택한 main category 리스트
        """
        def cos(a, b):
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        results = []

        for cat in main_categories:
            # 1) 해당 카테고리의 연예인 garment들
            ref_items = [g for g in garments if g.get("category") == cat]

            if not ref_items:
                results.append({
                    "category": cat,
                    "items": [],
                })
                continue

            # 2) 우리 DB에서 해당 카테고리 옷들
            db_items = ClothesAnalysis.objects.filter(
                category=cat
            ).exclude(vector__isnull=True).select_related("clothes")

            scored = []

            # 3) 각 참조 garment vs DB 옷들 → 유사도 계산
            for ref in ref_items:
                ref_vec = ref.get("vector") or []
                for ca in db_items:
                    sim = cos(ref_vec, ca.vector or [])
                    if sim > 0:
                        scored.append((sim, ca))

            # 4) 유사도 순 정렬 & 상위 2개
            scored.sort(key=lambda x: x[0], reverse=True)
            top2 = scored[:2]

            items = []
            for sim, ca in top2:
                clothes = ca.clothes
                items.append(
                    {
                        "name": clothes.name,
                        "image_url": clothes.image_url,
                        "shop_link": clothes.shop_link,
                        "similarity": sim,
                    }
                )

            results.append({
                "category": cat,
                "items": items,
            })

        return results