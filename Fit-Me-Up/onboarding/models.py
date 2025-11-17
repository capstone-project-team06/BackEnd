from django.db import models

from accounts.models import User

# Create your models here.
class Onboarding(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="onboarding",
    )

    styles = models.JSONField(null=True, blank=True)
    preferred_colors = models.JSONField(null=True, blank=True, help_text="['black', 'white']")
    preferred_fits = models.JSONField(null=True, blank=True, help_text="['oversized', 'regular']")

    def __str__(self):
        return f"OnboardingProfile(user={self.user.username})"