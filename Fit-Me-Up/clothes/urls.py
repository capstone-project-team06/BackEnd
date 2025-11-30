from django.urls import path
from .views import *

urlpatterns = [
    path("create/", ClothesCreateView.as_view(), name="clothes-create"),
    path("", ClothesListView.as_view(), name="clothes-list"),
    path("batch-analyze/", ClothesBatchAnalyzeView.as_view(), name="clothes-batch-analyze"),
]