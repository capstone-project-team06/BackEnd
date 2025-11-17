from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Onboarding
from .serializers import OnboardingSerializer


class OnboardingView(APIView):
    # permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        try:
            onboarding = user.onboarding
            is_create = False
        except Onboarding.DoesNotExist:
            onboarding = None
            is_create = True

        serializer = OnboardingSerializer(onboarding, data=request.data, partial=True)

        if serializer.is_valid():
            if is_create:
                serializer.save(user=user)
            else:
                serializer.save()

            return Response(
                {
                    "message": "온보딩 입력 성공",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        user = request.user

        try:
            onboarding = user.onboarding
        except Onboarding.DoesNotExist:
            return Response(
                {"detail": "온보딩 데이터가 존재하지 않습니다."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OnboardingSerializer(onboarding)    
        return Response(
            {
                "message": "온보딩 불러오기 성공",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
