import uuid
import os
import boto3
import requests

from django.conf import settings
from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.response import Response

from .models import Clothes, ClothesAnalysis
from .serializers import ClothesSerializer, ClothesAnalysisSerializer


class ClothesCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        name = request.data.get("name")
        shop_link = request.data.get("shop_link")
        image_file = request.FILES.get("image")

        if not name or not shop_link:
            return Response(
                {"error": "name, shop_link는 필수입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        image_url = None
        if image_file:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )

            ext = os.path.splitext(image_file.name)[1] or ".jpg"
            file_name = f"clothes/{uuid.uuid4()}{ext}"

            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_name,
                Body=image_file.read(),
                ContentType=image_file.content_type,
            )

            image_url = (
                f"https://{settings.AWS_STORAGE_BUCKET_NAME}"
                f".s3.{settings.AWS_REGION}.amazonaws.com/{file_name}"
            )

        clothes = Clothes.objects.create(
            name=name,
            shop_link=shop_link,
            image_url=image_url,
        )

        return Response(
            ClothesSerializer(clothes).data,
            status=status.HTTP_201_CREATED,
        )


class ClothesListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        items = Clothes.objects.all()
        serializer = ClothesSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClothesBatchAnalyzeView(APIView):

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # ?force=true 이면 이미 분석된 것도 포함
        force = request.query_params.get("force") == "true"

        qs = Clothes.objects.all()
        if not force:
            qs = qs.filter(analysis__isnull=True)

        # image_url 없는 건 스킵
        qs = qs.exclude(image_url__isnull=True).exclude(image_url="")

        processed = []
        failed = []

        for c in qs:
            try:
                ai_resp = requests.post(
                    f"{settings.AI_SERVER_URL}/ai/clothes/analyze",
                    json={
                        "clothes_id": c.id,
                        "name": c.name,
                        "image_url": c.image_url,
                    },
                    timeout=120,
                )
                ai_resp.raise_for_status()
                ai_json = ai_resp.json()

                ClothesAnalysis.objects.update_or_create(
                    clothes=c,
                    defaults={
                        "category": ai_json.get("category"),
                        "sub_category": ai_json.get("sub_category"),
                        "style": ai_json.get("style"),
                        "color": ai_json.get("color"),
                        "fit": ai_json.get("fit"),
                        "season": ai_json.get("season"),
                        "vector": ai_json.get("vector"),
                    },
                )
                processed.append(c.id)

            except Exception as e:
                failed.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "error": str(e),
                    }
                )

        return Response(
            {
                "processed_ids": processed,
                "failed": failed,
                "force": force,
            },
            status=status.HTTP_200_OK,
        )