import uuid
import os
import boto3

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
            return Response({"error": "name, shop_link는 필수입니다."},
                            status=status.HTTP_400_BAD_REQUEST)

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
            image_url=image_url
        )

        return Response(ClothesSerializer(clothes).data,
                        status=status.HTTP_201_CREATED)
    

class ClothesListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        items = Clothes.objects.all()
        serializer = ClothesSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class ClothesAnalysisUpdateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        try:
            clothes = Clothes.objects.get(pk=pk)
        except Clothes.DoesNotExist:
            return Response({"error": "Clothes not found"}, status=404)

        analysis, created = ClothesAnalysis.objects.get_or_create(clothes=clothes)

        serializer = ClothesAnalysisSerializer(
            analysis,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)

        return Response(serializer.errors, status=400)