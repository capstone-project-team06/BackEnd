from rest_framework import serializers
from .models import Clothes, ClothesAnalysis


class ClothesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clothes
        fields = "__all__"


class ClothesAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClothesAnalysis
        fields = "__all__"