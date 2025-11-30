# celebrity/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    path("create/", CelebrityCreateView.as_view()),
    path("list/", CelebrityListView.as_view()),
    path("batch-analyze/", CelebrityBatchAnalyzeView.as_view()),
    path("match/", ClosestCelebrityView.as_view()),

]