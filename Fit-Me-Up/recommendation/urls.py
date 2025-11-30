from django.urls import path
from .views import *

urlpatterns = [
    path("requests/", RecommendationRequestView.as_view(), name="recommendation-requests"),
    path("final/", RecommendStyleFromCelebrityView.as_view(), name="recommend-style-from-celeb"),
    path("celebrity-look/", CelebrityLookOnlyView.as_view(), name="celebrity-look-only"),
]