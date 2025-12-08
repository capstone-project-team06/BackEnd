from math import sqrt
import math
import requests
from typing import List, Optional

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from accounts.models import UserAnalysis
from celebrity.models import Celebrity, CelebrityAnalysis
from clothes.models import Clothes
from clothes.models import ClothesAnalysis
from clothes.serializers import ClothesSerializer
from .models import RecommendationRequest
from .serializers import RecommendationRequestSerializer


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


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


class CelebrityStyleOnlyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            user_analysis = UserAnalysis.objects.get(user=user)
        except UserAnalysis.DoesNotExist:
            return Response({"detail": "UserAnalysis 필요"}, status=status.HTTP_400_BAD_REQUEST)

        user_vec = user_analysis.vector or []
        if not user_vec:
            return Response({"detail": "user vector 없음"}, status=status.HTTP_400_BAD_REQUEST)

        req: Optional[RecommendationRequest] = (
            RecommendationRequest.objects.filter(user=user).order_by("-id").first()
        )
        if not req:
            return Response({"detail": "RecommendationRequest 필요"}, status=status.HTTP_400_BAD_REQUEST)

        styles = user.styles
        styles_text = ""
        if isinstance(styles, list):
            styles_text = ", ".join(styles)
        elif isinstance(styles, dict):
            styles_text = ", ".join(styles.get("keywords", []))

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

        celeb_analyses = CelebrityAnalysis.objects.select_related("celebrity")
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
            return Response({"detail": "연예인 분석 데이터 부족"}, status=status.HTTP_400_BAD_REQUEST)

        celeb = best_celeb.celebrity

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
                    "detail": "AI 호출 실패",
                    "error": str(e),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        celeb_face_image = (
            getattr(celeb, "face_image_url", None)
            or getattr(celeb, "image_url", None)
            or getattr(celeb, "profile_image_url", None)
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
                    "image_url": celeb_face_image,
                },
                "user_analysis": {
                    "face_shape": user_analysis.face_shape,
                    "body_shape": user_analysis.body_shape,
                    "skin_tone": user_analysis.skin_tone,
                },
                "needs": needs_text,
                "needs_list": needs_list,
                "ai_style": ai_json,
            },
            status=status.HTTP_200_OK,
        )


class RecommendStyleFromCelebrityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            user_analysis = UserAnalysis.objects.get(user=user)
        except UserAnalysis.DoesNotExist:
            return Response({"detail": "UserAnalysis 필요"}, status=status.HTTP_400_BAD_REQUEST)

        user_vec = user_analysis.vector or []
        if not user_vec:
            return Response({"detail": "user vector 없음"}, status=status.HTTP_400_BAD_REQUEST)

        req: Optional[RecommendationRequest] = (
            RecommendationRequest.objects.filter(user=user).order_by("-id").first()
        )
        if not req:
            return Response({"detail": "RecommendationRequest 필요"}, status=status.HTTP_400_BAD_REQUEST)

        styles = user.styles
        styles_text = ""
        if isinstance(styles, list):
            styles_text = ", ".join(styles)
        elif isinstance(styles, dict):
            styles_text = ", ".join(styles.get("keywords", []))

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

        celeb_analyses = CelebrityAnalysis.objects.select_related("celebrity")
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
            return Response({"detail": "연예인 분석 데이터 부족"}, status=status.HTTP_400_BAD_REQUEST)

        celeb = best_celeb.celebrity

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
                {"detail": "AI 호출 실패", "error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        looks = ai_json.get("looks") or []
        summary = ai_json.get("summary", "")

        all_garments = []
        for look in looks:
            for g in (look.get("garments") or []):
                all_garments.append(g)

        recommendations = self._recommend_by_main_categories(
            garments=all_garments,
            main_categories=main_cats,
            sub_categories=sub_cats,
        )

        req_serializer = RecommendationRequestSerializer(req)

        celeb_face_image = (
            getattr(celeb, "face_image_url", None)
            or getattr(celeb, "image_url", None)
            or getattr(celeb, "profile_image_url", None)
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
                    "image_url": celeb_face_image,
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

    def _recommend_by_main_categories(self, garments, main_categories, sub_categories):
        def cos(a, b):
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        sub_map = {}
        for idx, cat in enumerate(main_categories):
            if idx < len(sub_categories):
                sub_map[cat] = sub_categories[idx]
            else:
                sub_map[cat] = None

        results = []

        for cat in main_categories:
            desired_sub = sub_map.get(cat)

            ref_items = []
            if desired_sub:
                ref_items = [
                    g
                    for g in garments
                    if g.get("category") == cat and g.get("sub_category") == desired_sub
                ]

            if not ref_items:
                ref_items = [g for g in garments if g.get("category") == cat]

            if not ref_items and garments:
                ref_items = garments

            if not ref_items:
                results.append(
                    {
                        "category": cat,
                        "sub_category": desired_sub,
                        "items": [],
                    }
                )
                continue

            db_items = ClothesAnalysis.objects.filter(
                category=cat
            ).exclude(vector__isnull=True).select_related("clothes")

            if desired_sub:
                filtered = db_items.filter(sub_category=desired_sub)
                if filtered.exists():
                    db_items = filtered

            scored = []

            for ref in ref_items:
                ref_vec = ref.get("vector") or []
                for ca in db_items:
                    sim = cos(ref_vec, ca.vector or [])
                    if sim > 0:
                        scored.append((sim, ca))

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

            results.append(
                {
                    "category": cat,
                    "sub_category": desired_sub,
                    "items": items,
                }
            )

        return results