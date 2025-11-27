from rest_framework import serializers          # Serializer 관련 기본 클래스
from django.contrib.auth import get_user_model  # User 모델 가져오기 (CustomUser 대응)
from rest_framework_simplejwt.tokens import RefreshToken  # JWT 토큰 생성용
from .models import UserImage


from .models import User 

# 회원가입용 시리얼라이저
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "name", "gender", "age", "height_cm", "weight_kg"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    

# 로그인용 시리얼라이저
class AuthSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        # email로 유저 찾기
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist.")

        # 비밀번호 확인
        if not user.check_password(password):
            raise serializers.ValidationError("Wrong password.")

        # JWT 생성
        token = RefreshToken.for_user(user)

        return {
            "user": user,
            "refresh_token": str(token),
            "access_token": str(token.access_token),
        }
    

class UserImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserImage
        fields = "__all__"