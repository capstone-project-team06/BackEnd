from rest_framework import serializers
from .models import Celebrity, CelebrityAnalysis


class CelebritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Celebrity
        fields = "__all__"


class CelebrityAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = CelebrityAnalysis
        fields = "__all__"
