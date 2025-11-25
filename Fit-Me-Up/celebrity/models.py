from django.db import models


class Celebrity(models.Model):
    GENDER_CHOICES = (
        ("M", "Male"),
        ("F", "Female"),
    )

    name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    image_url = models.URLField(max_length=500, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.get_gender_display()})"


class CelebrityAnalysis(models.Model):
    celebrity = models.OneToOneField(
        Celebrity,
        on_delete=models.CASCADE,
        related_name="analysis"
    )

    face_shape = models.CharField(max_length=50, blank=True, null=True)
    body_shape = models.CharField(max_length=50, blank=True, null=True)
    skin_tone = models.CharField(max_length=50, blank=True, null=True)
    vector = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Analysis of {self.celebrity.name}"