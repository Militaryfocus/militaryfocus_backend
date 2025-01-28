from django.urls import path
from . import views  # Импортируйте ваши views

urlpatterns = [
    path('', views.main_page, name='home'),  # Главная страница
    path('feed/', views.feed_page, name='feed'),  # Страница со статьями
    path('archive/', views.archive_page, name='архив'),  # Архив новостей
]