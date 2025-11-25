from django.db import models
from django.conf import settings
from celebrity.models import Celebrity  # 이미 만든 연예인 모델

class RecommendationSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendation_sessions",
    )
    matched_celebrity = models.ForeignKey(
        Celebrity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_sessions",
    )
    payload = models.JSONField()  # AI가 보내준 전체 결과 JSON 저장

    def __str__(self):
        return f"RecommendationSession(user={self.user_id}, celeb={self.matched_celebrity_id})"