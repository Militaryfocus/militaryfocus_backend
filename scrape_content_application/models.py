from django.db import models
# Create your models here.


class ContentSource(models.Model):
    name = models.CharField("Название источника", max_length=200)
    description = models.TextField("Описание источника")
    source_link = models.URLField("Ссылка на источник", max_length=160, unique=True)
    period = models.IntegerField("Периодичность парсинга источника. В часах")
    youtube_link = models.BooleanField("Является ли ютуб-каналом", default=False)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Источник"
        verbose_name_plural = "Источники"

from django.utils import timezone
class ArticleContent(models.Model):
    article_title = models.CharField("Заголовок статьи", max_length=200)
    article_content = models.TextField("Содержимое статьи")
    article_image = models.ImageField('Image', null=True, blank=True)
    article_link = models.URLField("Ссылка на статью", max_length=160, unique=True, default="default_link_value", null=False)
    created_at = models.DateTimeField(default=timezone.now)
    source = models.ForeignKey(ContentSource, on_delete=models.CASCADE, verbose_name="Источник статьи")


    def __str__(self):
        return f"{self.article_title}, Источник: {self.source}"

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"

    objects = models.Manager()
