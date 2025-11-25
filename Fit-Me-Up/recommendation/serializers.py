from rest_framework import serializers
from .models import UserRecommendation
from celebrities.serializers import CelebritySerializer
from clothes.serializers import ClothesSerializer


class UserRecommendationSerializer(serializers.ModelSerializer):
    celebrity = CelebritySerializer(read_only=True)
    clothes = ClothesSerializer(read_only=True)

    class Meta:
        model = UserRecommendation
        fields = [
            "id",
            "celebrity",
            "clothes",
            "rank",
            "score",
        ]