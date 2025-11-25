import uuid
import os
import boto3

from django.conf import settings
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework.response import Response

from .models import Celebrity, CelebrityAnalysis
from .serializers import CelebritySerializer, CelebrityAnalysisSerializer


class CelebrityCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        name = request.data.get("name")
        gender = request.data.get("gender")
        image_file = request.FILES.get("image")

        if not name or not gender:
            return Response({"error": "name, gender는 필수입니다."},
                            status=status.HTTP_400_BAD_REQUEST)

        image_url = None
        if image_file:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )

            ext = os.path.splitext(image_file.name)[1] or ".jpg"
            file_name = f"celebs/{uuid.uuid4()}{ext}"

            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_name,
                Body=image_file.read(),
                ContentType=image_file.content_type
            )

            image_url = (
                f"https://{settings.AWS_STORAGE_BUCKET_NAME}"
                f".s3.{settings.AWS_REGION}.amazonaws.com/{file_name}"
            )

        celeb = Celebrity.objects.create(
            name=name,
            gender=gender,
            image_url=image_url
        )

        return Response(CelebritySerializer(celeb).data,
                        status=status.HTTP_201_CREATED)


class CelebrityListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        celebs = Celebrity.objects.all()
        serializer = CelebritySerializer(celebs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class CelebrityAnalysisUpdateView(APIView):
    permission_classes = [permissions.AllowAny]   # AI 서버가 호출하는 용도

    def post(self, request, pk):

        # 연예인 존재 여부 확인
        try:
            celeb = Celebrity.objects.get(pk=pk)
        except Celebrity.DoesNotExist:
            return Response({"error": "Celebrity not found"}, status=404)

        # 기존 분석정보 가져오거나 새로 생성
        analysis, created = CelebrityAnalysis.objects.get_or_create(celebrity=celeb)

        serializer = CelebrityAnalysisSerializer(
            analysis,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)

        return Response(serializer.errors, status=400)