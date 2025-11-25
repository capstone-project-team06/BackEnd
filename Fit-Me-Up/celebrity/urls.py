from django.urls import path
from .views import *



urlpatterns = [
    path("", CelebrityListView.as_view()),
    path("create/", CelebrityCreateView.as_view()),
    path("<int:pk>/analysis/", CelebrityAnalysisUpdateView.as_view()),
]