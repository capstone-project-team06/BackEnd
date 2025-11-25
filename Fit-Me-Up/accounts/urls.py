from django.urls import path
from .views import *


urlpatterns = [
  
    path("join/", RegisterView.as_view()),
    path("login/", AuthView.as_view()), 
    path("info/",UserInfoView.as_view()),
    path("images/upload/", UserImageUploadView.as_view(), name="user-image-upload"),
    path("images/", UserImageListView.as_view(), name="user-image-list"),
]