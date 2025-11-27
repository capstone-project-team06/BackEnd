from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    username = None
    name = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=50, unique=True)

    GENDER_CHOICES = (
        ("M", "Male"),
        ("F", "Female"),
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        null=True,
        blank=True,
    )

    age = models.PositiveIntegerField(null=True, blank=True)

    height_cm = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.PositiveIntegerField(null=True, blank=True)
    
    USERNAME_FIELD = "email"   # 🔥 로그인 ID로 사용할 필드
    REQUIRED_FIELDS = []       # createsuperuser 할 때 추가로 필수로 받을 필드 목록 (email은 자동)

    def __str__(self):
        return self.email
        

class UserImage(models.Model):
    IMAGE_TYPE_CHOICES = (
        ("FACE", "Face"),
        ("BODY", "Body"),
    )

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_images",
    )
    image_url = models.URLField(max_length=500)  # S3 URL 저장
    image_type = models.CharField(max_length=10, choices=IMAGE_TYPE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image of {self.user.name} ({self.image_type})"