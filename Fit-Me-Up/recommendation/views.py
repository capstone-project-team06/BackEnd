from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from django.contrib.auth import get_user_model

from celebrity.models import Celebrity
from clothes.models import Clothes
from .models import RecommendationSession

User = get_user_model()


class RecommendationFromAIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data

        user_id = data.get("user_id")
        matched_celebrity = data.get("matched_celebrity")
        reference_outfit = data.get("reference_outfit")

        # 1) 필수 필드 체크
        if not user_id or not matched_celebrity or not reference_outfit:
            return Response(
                {"error": "user_id, matched_celebrity, reference_outfit는 필수입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) 유저 존재 여부 확인
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 3) 연예인 존재 여부 확인 (optional)
        celeb_id = matched_celebrity.get("id")
        celeb_obj = None
        if celeb_id is not None:
            try:
                celeb_obj = Celebrity.objects.get(id=celeb_id)
            except Celebrity.DoesNotExist:
                # 연예인 정보가 DB에 없으면 celeb_obj는 None으로 두고 넘어감
                celeb_obj = None

        # 4) 추천된 옷 id 유효성 간단 검증 (있으면 확인, 없어도 에러는 안 냄)
        items = reference_outfit.get("items", [])
        for item in items:
            for rc in item.get("recommended_clothes", []):
                clothes_id = rc.get("id")
                if clothes_id is None:
                    continue
                # 존재하지 않아도 전체를 실패로 만들지 않고 그냥 skip 가능
                try:
                    Clothes.objects.get(id=clothes_id)
                except Clothes.DoesNotExist:
                    # 여기서는 단순 경고만, 실제 로직에선 로그 남기는 용도로 쓰면 좋음
                    continue

        # 5) 세션 저장 (payload 전체 저장)
        session = RecommendationSession.objects.create(
            user=user,
            matched_celebrity=celeb_obj,
            payload=data,  # 받은 JSON 전체 저장
        )

        # 6) 그대로 응답 (AI → 백엔드 → 프론트 바로 확인용)
        return Response(session.payload, status=status.HTTP_201_CREATED)
    

class RecommendationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        session = RecommendationSession.objects.filter(user=user).first()
        if not session:
            return Response(
                {"detail": "추천 결과가 아직 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(session.payload, status=status.HTTP_200_OK)