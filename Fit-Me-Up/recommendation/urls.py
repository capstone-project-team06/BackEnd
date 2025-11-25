from django.urls import path
from .views import RecommendationFromAIView, RecommendationView

urlpatterns = [
    path("create/", RecommendationFromAIView.as_view(), name="recommendation-from-ai"),
    path("", RecommendationView.as_view(), name="recommendation"),
]