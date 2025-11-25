from django.urls import path
from .views import *

urlpatterns = [
    path("create/", ClothesCreateView.as_view()),
    path("", ClothesListView.as_view()),
    path("<int:pk>/analysis/", ClothesAnalysisUpdateView.as_view()),
]