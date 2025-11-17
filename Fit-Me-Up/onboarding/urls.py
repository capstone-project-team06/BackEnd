from django.urls import path
from .views import OnboardingView

urlpatterns = [
    path("", OnboardingView.as_view(), name="onboarding"),
]