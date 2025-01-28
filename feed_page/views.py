from django.shortcuts import render
from django.template.response import TemplateResponse
from django.http import JsonResponse
from scrape_content_application.models import ArticleContent


# Create your views here.
def feed_page(request):
    articles = list(ArticleContent.objects.all().order_by('-created_at').values('article_title', 'article_content', 'article_image', 'article_link', 'created_at', 'source'))
    return JsonResponse({'articles': articles}, safe=False)


def main_page(request):
    return TemplateResponse(request, "first_main_page/main.html")