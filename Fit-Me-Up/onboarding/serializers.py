from rest_framework import serializers
from .models import Onboarding


class OnboardingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Onboarding
        fields = [
            "styles",
            "preferred_colors",
            "preferred_fits",
        ]
