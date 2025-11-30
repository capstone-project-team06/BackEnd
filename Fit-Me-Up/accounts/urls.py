# accounts/urls.py
from django.urls import path
from .views import (
    RegisterView,
    AuthView,
    UserInfoView,
    UserImageAnalyzeUploadView,
    UserAnalysisView,
    UserImageListView,
)

urlpatterns = [
    path("join/", RegisterView.as_view(), name="join"),
    path("login/", AuthView.as_view(), name="login"),
    path("info/", UserInfoView.as_view(), name="info"),
    path("images/analyze-upload/",UserImageAnalyzeUploadView.as_view(),name="user_image_analyze_upload"),
    path("analysis/", UserAnalysisView.as_view(), name="user_analysis"),
    path("images/", UserImageListView.as_view(), name="user_image_list"),
]