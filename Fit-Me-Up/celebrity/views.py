import uuid
import os
import boto3
import math
import requests

from django.conf import settings
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Celebrity, CelebrityAnalysis
from .serializers import CelebritySerializer, CelebrityAnalysisSerializer
from accounts.models import *

class CelebrityCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        name = request.data.get("name")
        gender = request.data.get("gender")
        face_file = request.FILES.get("face_image")
        body_file = request.FILES.get("body_image")

        if not name or not gender:
            return Response(
                {"error": "name, gender는 필수입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not face_file or not body_file:
            return Response(
                {"error": "face_image, body_image 두 파일이 모두 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

        def upload_to_s3(file_obj, subdir: str) -> str:
            ext = os.path.splitext(file_obj.name)[1] or ".jpg"
            file_name = f"celebs/{subdir}/{uuid.uuid4()}{ext}"
            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_name,
                Body=file_obj.read(),
                ContentType=file_obj.content_type,
            )
            return (
                f"https://{settings.AWS_STORAGE_BUCKET_NAME}"
                f".s3.{settings.AWS_REGION}.amazonaws.com/{file_name}"
            )

        face_url = upload_to_s3(face_file, "face")
        body_url = upload_to_s3(body_file, "body")

        celeb = Celebrity.objects.create(
            name=name,
            gender=gender,
            face_image_url=face_url,
            body_image_url=body_url,
        )

        return Response(CelebritySerializer(celeb).data,
                        status=status.HTTP_201_CREATED)


class CelebrityListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        celebs = Celebrity.objects.all()
        serializer = CelebritySerializer(celebs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class CelebrityBatchAnalyzeView(APIView):

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        force = request.query_params.get("force") == "true"

        qs = Celebrity.objects.all()
        if not force:
            qs = qs.filter(analysis__isnull=True)

        # face/body 둘 중 하나라도 비어 있으면 스킵
        qs = qs.exclude(face_image_url__isnull=True).exclude(body_image_url__isnull=True)

        processed = []
        failed = []

        for celeb in qs:
            try:
                ai_resp = requests.post(
                    f"{settings.AI_SERVER_URL}/user/analyze-url-multi",
                    json={
                        "face_image_url": celeb.face_image_url,
                        "body_image_url": celeb.body_image_url,
                    },
                    timeout=60,
                )
                ai_resp.raise_for_status()
                ai_json = ai_resp.json()
                analysis_data = ai_json.get("analysis") or ai_json

                CelebrityAnalysis.objects.update_or_create(
                    celebrity=celeb,
                    defaults={
                        "face_shape": analysis_data.get("face_shape"),
                        "body_shape": analysis_data.get("body_shape"),
                        "skin_tone": analysis_data.get("skin_tone"),
                        "vector": analysis_data.get("vector"),
                    },
                )
                processed.append(celeb.id)
            except Exception as e:
                failed.append({"id": celeb.id, "name": celeb.name, "error": str(e)})

        return Response(
            {
                "processed_ids": processed,
                "failed": failed,
                "force": force,
            },
            status=status.HTTP_200_OK,
        )


def cosine_similarity(vec1, vec2):

    if not vec1 or not vec2:
        return -1.0

    # 안전하게 float로 변환
    a = [float(x) for x in vec1]
    b = [float(x) for x in vec2]

    length = min(len(a), len(b))
    if length == 0:
        return -1.0

    dot = sum(a[i] * b[i] for i in range(length))
    norm_a = math.sqrt(sum(a[i] * a[i] for i in range(length)))
    norm_b = math.sqrt(sum(b[i] * b[i] for i in range(length)))

    if norm_a == 0 or norm_b == 0:
        return -1.0

    return dot / (norm_a * norm_b)


class ClosestCelebrityView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1) 유저 분석 결과 가져오기
        user_analysis = UserAnalysis.objects.filter(user=user).first()
        if not user_analysis or not user_analysis.vector:
            return Response(
                {"detail": "먼저 유저 분석(UserAnalysis)이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_vec = user_analysis.vector

        # 2) 연예인 분석들 가져오기 (벡터 있는 것만)
        celeb_analyses = (
            CelebrityAnalysis.objects
            .select_related("celebrity")
            .exclude(vector__isnull=True)
        )

        if not celeb_analyses.exists():
            return Response(
                {"detail": "분석된 연예인 정보가 없습니다. CelebrityAnalysis를 먼저 채워주세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3) 가장 유사한 연예인 찾기
        best_celeb = None
        best_score = -2.0  # 코사인 유사도는 -1 ~ 1 범위

        # (선택) top-k 리스트도 보고 싶으면 저장해 둘 수 있음
        top_list = []

        for ca in celeb_analyses:
            vec = ca.vector
            if not vec:
                continue

            score = cosine_similarity(user_vec, vec)

            top_list.append((score, ca))

            if score > best_score:
                best_score = score
                best_celeb = ca

        if not best_celeb:
            return Response(
                {"detail": "유효한 연예인 벡터가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        celeb_data = CelebritySerializer(best_celeb.celebrity).data

        # (선택) top 3 같이 보내고 싶으면 여기서 정렬해서 추가
        top_list.sort(key=lambda x: x[0], reverse=True)
        top3 = []
        for score, ca in top_list[:3]:
            top3.append({
                "celebrity": CelebritySerializer(ca.celebrity).data,
                "similarity": score,
            })

        return Response(
            {
                "user_id": user.id,
                "best_match": {
                    "celebrity": celeb_data,
                    "similarity": best_score,
                },
                "top3": top3,   # 필요 없으면 이 키는 제거해도 됨
            },
            status=status.HTTP_200_OK,
        )