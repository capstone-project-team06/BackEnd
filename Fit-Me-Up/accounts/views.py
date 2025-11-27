from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from django.conf import settings

from .serializers import (
    RegisterSerializer,
    AuthSerializer,
    UserImageSerializer,
)
from .models import UserImage

import os
import uuid
import boto3
from rest_framework.permissions import AllowAny


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        # 유효성 검사
        if serializer.is_valid(raise_exception=True):

            # 유효성 검사 통과 후 객체 생성
            user = serializer.save()

            # user에게 refresh token 발급
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


class UserImageUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        # 파일 유무 확인
        if "image" not in request.FILES:
            return Response(
                {"error": "No image file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        image_file = request.FILES["image"]

        # image_type(FACE/BODY) 같이 받기
        image_type = request.data.get("image_type")
        if image_type not in ["FACE", "BODY"]:
            return Response(
                {"error": "image_type must be FACE or BODY"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # S3 클라이언트 생성
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

        # 파일 확장자
        _, ext = os.path.splitext(image_file.name)
        ext = ext or ".jpg"

        # S3에 저장할 경로 (user별 디렉토리)
        file_name = f"{uuid.uuid4()}{ext}"
        file_path = f"uploads/user/{user.id}/{file_name}"

        # S3 업로드
        try:
            s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_path,
                Body=image_file.read(),
                ContentType=image_file.content_type,
            )
        except Exception as e:
            return Response(
                {"error": f"S3 Upload Failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 업로드된 파일의 S3 URL
        image_url = (
            f"https://{settings.AWS_STORAGE_BUCKET_NAME}"
            f".s3.{settings.AWS_REGION}.amazonaws.com/{file_path}"
        )

        # DB에 저장
        image_instance = UserImage.objects.create(
            user=user,
            image_url=image_url,
            image_type=image_type,
        )
        serializer = UserImageSerializer(image_instance)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserImageListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        images = UserImage.objects.filter(user=user)

        data = [
            {
                "image_type": img.image_type,   # FACE / BODY
                "image_url": img.image_url,     # S3 URL
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