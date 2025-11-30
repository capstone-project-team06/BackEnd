from django.db import models
from django.conf import settings


class RecommendationRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    main_categories = models.JSONField(default=list)   # 상, 하의, 아우터 같은 리스트
    sub_categories = models.JSONField(default=list, blank=True, null=True)
    situation = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"RecommendationRequest(user={self.user_id})"