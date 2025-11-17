from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    name = models.CharField(max_length=20, blank=True)

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
    
    # 모델 함수
    @staticmethod
    def get_user_by_username(username):
        try:
            return User.objects.get(username=username)
        except Exception:
            return None