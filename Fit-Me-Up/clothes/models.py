from django.db import models


class Clothes(models.Model):
    name = models.CharField(max_length=200)
    shop_link = models.URLField(max_length=500)
    image_url = models.URLField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.name


class ClothesAnalysis(models.Model):
    clothes = models.OneToOneField(
        Clothes,
        on_delete=models.CASCADE,
        related_name="analysis"
    )

    category = models.CharField(max_length=100, blank=True, null=True)
    sub_category = models.CharField(max_length=100, blank=True, null=True)
    style = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=100, blank=True, null=True)
    fit = models.CharField(max_length=100, blank=True, null=True)
    season = models.CharField(max_length=100, blank=True, null=True)

    vector = models.JSONField(blank=True, null=True)


    def __str__(self):
        return f"{self.clothes.name} analysis"