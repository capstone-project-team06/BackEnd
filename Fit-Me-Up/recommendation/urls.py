from django.urls import path
from .views import *

urlpatterns = [
    path("requests/", RecommendationRequestView.as_view(), name="recommendation-requests"),
    path("final/", RecommendStyleFromCelebrityView.as_view(), name="recommend-style-from-celeb"),
    path("celebrity-look/", CelebrityStyleOnlyView.as_view(), name="celebrity-style-only"),
    path("recommendation/debug/celebrity-style/", DebugCelebrityStyleProxyView.as_view()),
]