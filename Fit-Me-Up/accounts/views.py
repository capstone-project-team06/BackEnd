from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework_simplejwt.tokens import RefreshToken

from django.conf import settings

from .serializers import (
    RegisterSerializer,
    AuthSerializer,
    UserImageSerializer,
    UserAnalysisSerializer,
)
from .models import UserImage, UserAnalysis

import os
import uuid
import boto3
import requests


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.save()

            token = RefreshToken.for_user(user)
            refresh_token = str(token)
            access_token = str(token.access_token)

            res = Response(
                {
                    "user": serializer.data,
                    "message": "register success!",
                    "token": {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                    },
                },
                status=status.HTTP_201_CREATED,
            )
            return res


class AuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = AuthSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data["user"]
            access_token = serializer.validated_data["access_token"]
            refresh_token = serializer.validated_data["refresh_token"]

            res = Response(
                {
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "gender": user.gender,
                        "age": user.age,
                        "height_cm": user.height_cm,
                        "weight_kg": user.weight_kg,
                        "styles": user.styles,
                    },
                    "message": "login success!",
                    "token": {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                    },
                },
                status=status.HTTP_200_OK,
            )

            res.set_cookie("access_token", access_token, httponly=True)
            res.set_cookie("refresh_token", refresh_token, httponly=True)
            return res


class UserInfoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        data = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "gender": getattr(user, "gender", None),
            "age": getattr(user, "age", None),
            "height_cm": getattr(user, "height_cm", None),
            "weight_kg": getattr(user, "weight_kg", None),
            "styles": getattr(user, "styles", None),
        }

        return Response(data, status=status.HTTP_200_OK)


class UserImageAnalyzeUploadView(APIView):

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        user = request.user

        # 1) 두 파일 다 있는지 확인
        face_file = request.FILES.get("face_image")
        body_file = request.FILES.get("body_image")

        if not face_file or not body_file:
            return Response(
                {"detail": "face_image와 body_image 두 파일이 모두 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) S3 클라이언트 준비
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

        def upload_to_s3(file_obj, image_type: str) -> UserImage:
            _, ext = os.path.splitext(file_obj.name)
            ext = ext or ".jpg"
            file_name = f"{uuid.uuid4()}{ext}"
            file_path = f"uploads/user/{user.id}/{image_type.lower()}/{file_name}"

            s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_path,
                Body=file_obj.read(),
                ContentType=file_obj.content_type,
            )

            image_url = (
                f"https://{settings.AWS_STORAGE_BUCKET_NAME}"
                f".s3.{settings.AWS_REGION}.amazonaws.com/{file_path}"
            )

            return UserImage.objects.create(
                user=user,
                image_url=image_url,
                image_type=image_type,
            )

        # 3) 얼굴/몸 사진 각각 업로드 + DB 저장
        face_image = upload_to_s3(face_file, "FACE")
        body_image = upload_to_s3(body_file, "BODY")

        # 4) AI 서버 호출
        try:
            ai_resp = requests.post(
                f"{settings.AI_SERVER_URL}/user/analyze-url-multi",
                json={
                    "face_image_url": face_image.image_url,
                    "body_image_url": body_image.image_url,
                },
                timeout=60,
            )
            ai_resp.raise_for_status()
            ai_json = ai_resp.json()
            analysis_data = ai_json.get("analysis") or ai_json
        except Exception as e:
            return Response(
                {
                    "detail": "이미지는 업로드했지만 AI 분석 호출에 실패했습니다.",
                    "error": str(e),
                    "face_image": UserImageSerializer(face_image).data,
                    "body_image": UserImageSerializer(body_image).data,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 5) UserAnalysis 저장/업데이트
        analysis, _ = UserAnalysis.objects.update_or_create(
            user=user,
            defaults={
                "face_image": face_image,
                "body_image": body_image,
                "face_shape": analysis_data.get("face_shape"),
                "body_shape": analysis_data.get("body_shape"),
                "skin_tone": analysis_data.get("skin_tone"),
                "vector": analysis_data.get("vector"),
            },
        )

        # 6) 응답
        analysis_serializer = UserAnalysisSerializer(analysis)

        return Response(
            {
                "face_image": UserImageSerializer(face_image).data,
                "body_image": UserImageSerializer(body_image).data,
                "analysis": analysis_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class UserAnalysisView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            analysis = user.analysis
        except UserAnalysis.DoesNotExist:
            return Response(
                {"detail": "아직 저장된 분석 결과가 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UserAnalysisSerializer(analysis)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserImageListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        images = UserImage.objects.filter(user=user)

        data = [
            {
                "image_type": img.image_type,
                "image_url": img.image_url,
                "created_at": img.created_at,
            }
            for img in images
        ]

        return Response(
            {
                "user_id": user.id,
                "images": data,
            },
            status=status.HTTP_200_OK,
        )