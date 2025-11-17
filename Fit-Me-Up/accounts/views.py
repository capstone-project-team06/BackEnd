from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import RegisterSerializer, AuthSerializer
from rest_framework import status, permissions

from django.contrib.auth import get_user_model
from onboarding.models import Onboarding
from onboarding.serializers import OnboardingSerializer


class RegisterView(APIView):
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
    def post(self, request):
        serializer = AuthSerializer(data=request.data)
        
        # 유효성 검사
        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data['user']
            access_token = serializer.validated_data['access_token']
            refresh_token = serializer.validated_data['refresh_token']

            res = Response(
                {
                    "user": {
                        "id": user.id,
                        "username": user.username,
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
        
        # 유효성 검사 실패 시 오류 반환
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class UserInfoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            onboarding = user.onboarding
            onboarding_data = OnboardingSerializer(onboarding).data
        except Onboarding.DoesNotExist:
            onboarding_data = None

        data = {
            "id": user.id,
            "username": user.username,
            "gender": getattr(user, "gender", None),
            "age": getattr(user, "age", None),
            "height_cm": getattr(user, "height_cm", None),
            "weight_kg": getattr(user, "weight_kg", None),
            "onboarding": onboarding_data,
        }

        return Response(data, status=status.HTTP_200_OK)
