from rest_framework import serializers          # Serializer 관련 기본 클래스
from django.contrib.auth import get_user_model  # User 모델 가져오기 (CustomUser 대응)
from rest_framework_simplejwt.tokens import RefreshToken  # JWT 토큰 생성용

from .models import User 

# 회원가입용 시리얼라이저
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(required=True)
    username = serializers.CharField(required=True)

    class Meta:
        model = User

        # 필요한 필드값만 지정, 회원가입은 email까지 필요
        fields = ['username', 'password']
    
    # create() 재정의
    def create(self, validated_data):
    
        # 비밀번호 분리
        password = validated_data.pop('password')

        # user 객체 생성
        user = User(**validated_data)

        # 비밀번호는 해싱해서 저장
        user.set_password(password)
        user.save()

        return user
    

# 로그인용 시리얼라이저
class AuthSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    
    class Meta:
        model = User

        # 로그인은 username과 password만 필요
        fields = ['username', 'password']

    # 로그인 유효성 검사 함수
    def validate(self, data):
        username = data.get('username', None)
        password = data.get('password', None)
		    
		    # username으로 사용자 찾는 모델 함수
        user = User.get_user_by_username(username=username)
        
        # 존재하는 회원인지 확인
        if user is None:
            raise serializers.ValidationError("User does not exist.")
        else:
			      # 비밀번호 일치 여부 확인
            if not user.check_password(password):
                raise serializers.ValidationError("Wrong password.")
        
        token = RefreshToken.for_user(user)
        refresh_token = str(token)
        access_token = str(token.access_token)

        data = {
            "user": user,
            "refresh_token": refresh_token,
            "access_token": access_token,
        }

        return data