from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

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
    styles = models.JSONField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

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
    image_url = models.URLField(max_length=500)
    image_type = models.CharField(max_length=10, choices=IMAGE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image of {self.user.name} ({self.image_type})"


    
class UserAnalysis(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analysis",
    )

    face_image = models.ForeignKey(
        UserImage,
        null=True,
        on_delete=models.SET_NULL,
        related_name='face_analysis',
    )
    body_image = models.ForeignKey(
        UserImage,
        null=True,
        on_delete=models.SET_NULL,
        related_name='body_analysis',
    )

    face_shape = models.CharField(max_length=50, null=True, blank=True)
    body_shape = models.CharField(max_length=50, null=True, blank=True)
    skin_tone = models.CharField(max_length=50, null=True, blank=True)
    vector = models.JSONField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"UserAnalysis(user={self.user_id})"