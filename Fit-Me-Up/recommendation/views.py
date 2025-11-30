from math import sqrt
from typing import List, Optional

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

import requests

from accounts.models import UserAnalysis
from celebrity.models import Celebrity, CelebrityAnalysis
from .models import RecommendationRequest
from .serializers import RecommendationRequestSerializer
from clothes.models import Clothes, ClothesAnalysis
from clothes.serializers import ClothesSerializer

import math

class RecommendationRequestView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # 내 히스토리 전체 조회 (필요 없으면 나중에 지워도 됨)
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
    

def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class RecommendStyleFromCelebrityView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1) 유저 분석 존재 여부 확인
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

        # 3) 유저 styles, 카테고리, 상황을 needs_list로 구성
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

        # 4) 가장 비슷한 연예인 찾기 (코사인 유사도)
        celeb_analyses = (
            CelebrityAnalysis.objects
            .select_related("celebrity")
            .all()
        )

        if user.gender:
            celeb_analyses = celeb_analyses.filter(
                celebrity__gender=user.gender
            )

        best_celeb = None
        best_sim = -1.0

        for ca in celeb_analyses:
            vec = ca.vector or []
            sim = cosine_similarity(user_vec, vec)
            if sim > best_sim:
                best_sim = sim
                best_celeb = ca

        if not best_celeb:
            return Response(
                {"detail": "유사도를 계산할 연예인 분석 데이터가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        celeb = best_celeb.celebrity

        # 5) AI 서버 호출 → /ai/style/analyze
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
                    "needs": needs_text,
                    "needs_list": needs_list,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 6) AI가 준 look/garment들 + 우리 DB ClothesAnalysis 매칭 후
        #    "실제 추천용 의상 리스트"만 뽑기
        looks = ai_json.get("looks") or []

        scored_items = []  # (sim, ClothesAnalysis)

        for look in looks:
            garments = look.get("garments") or []
            for g in garments:
                g_vec = g.get("vector") or []
                if not g_vec:
                    continue

                qs = ClothesAnalysis.objects.exclude(vector__isnull=True)

                g_cat = g.get("category")
                g_sub = g.get("sub_category")

                if g_cat:
                    qs = qs.filter(category=g_cat)
                if g_sub:
                    qs = qs.filter(sub_category=g_sub)

                for ca in qs.select_related("clothes"):
                    c_vec = ca.vector or []
                    sim = cosine_similarity(g_vec, c_vec)
                    if sim <= 0.0:
                        continue
                    scored_items.append((sim, ca))

        # 7) 유사도 순으로 정렬 + 같은 옷 중복 제거 + 상위 N개만
        scored_items.sort(key=lambda x: x[0], reverse=True)

        TOP_N = 10
        seen_ids = set()
        recommended_clothes = []

        for sim, ca in scored_items:
            cid = ca.clothes.id
            if cid in seen_ids:
                continue
            seen_ids.add(cid)

            recommended_clothes.append(
                {
                    "id": ca.clothes.id,
                    "name": ca.clothes.name,
                    "image_url": ca.clothes.image_url,
                    "shop_link": ca.clothes.shop_link,
                    "similarity": sim,
                }
            )
            if len(recommended_clothes) >= TOP_N:
                break

        # 8) 최종 응답: summary + 추천 옷만
        return Response(
            {
                "summary": ai_json.get("summary", ""),
                "recommended_clothes": recommended_clothes,
            },
            status=status.HTTP_200_OK,
        )

class CelebrityLookOnlyView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1) 유저 분석 존재 여부 확인
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
            .order_by("-id")  # 제일 최근 요청 사용
            .first()
        )

        if not req:
            return Response(
                {"detail": "먼저 추천 요청(RecommendationRequest)을 생성해 주세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3) 유저 styles, 카테고리, 상황을 문자열 + 리스트(needs_list)로 구성
        styles = user.styles  # JSONField: 리스트 or dict라고 가정
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
            needs_text = " / ".join(parts)          # 사람 읽기용
            needs_list = parts                      # AI 서버 전달용
        else:
            needs_text = "일상적인 데일리 코디"
            needs_list = [needs_text]

        # 4) 가장 비슷한 연예인 찾기 (코사인 유사도)
        celeb_analyses = (
            CelebrityAnalysis.objects
            .select_related("celebrity")
            .all()
        )

        if user.gender:
            celeb_analyses = celeb_analyses.filter(
                celebrity__gender=user.gender
            )

        best_celeb = None
        best_sim = -1.0

        for ca in celeb_analyses:
            vec = ca.vector or []
            sim = cosine_similarity(user_vec, vec)
            if sim > best_sim:
                best_sim = sim
                best_celeb = ca

        if not best_celeb:
            return Response(
                {"detail": "유사도를 계산할 연예인 분석 데이터가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        celeb = best_celeb.celebrity

        # 5) AI 서버 호출 → /ai/style/analyze (연예인 착장만 분석)
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

        # 6) 응답 구성 (연예인 착장만)
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
                "needs_list": needs_list,
                "ai_style": ai_json,   # ★ 우리 DB 매칭 없이, 연예인 착장 분석 결과만
            },
            status=status.HTTP_200_OK,
        )