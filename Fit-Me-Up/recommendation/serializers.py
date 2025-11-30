# recommendation/serializers.py
from rest_framework import serializers
from .models import RecommendationRequest

MAIN_CATEGORY_CHOICES = (
    "top",
    "bottom",
    "outer",
)

class RecommendationRequestSerializer(serializers.ModelSerializer):
    main_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=MAIN_CATEGORY_CHOICES),
        allow_empty=False,
    )
    sub_categories = serializers.ListField(
        child=serializers.CharField(max_length=50),
        allow_empty=True,
        required=False,
    )

    class Meta:
        model = RecommendationRequest
        fields = [
            "id",
            "user",
            "main_categories",
            "sub_categories",
            "situation",
        ]
        read_only_fields = ["id", "user"]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["user"] = user
        return super().create(validated_data)