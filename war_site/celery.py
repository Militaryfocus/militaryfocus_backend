"""
Celery configuration for war_site project.
"""
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

app = Celery('war_site')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery beat schedule
app.conf.beat_schedule = {
    'scrape-vesti-articles': {
        'task': 'scrape_content_application.tasks.scrape_vesti_articles',
        'schedule': 600.0,  # Every 10 minutes
    },
    'scrape-youtube-videos': {
        'task': 'scrape_content_application.tasks.scrape_youtube_videos',
        'schedule': 1800.0,  # Every 30 minutes
    },
    'cleanup-old-media': {
        'task': 'scrape_content_application.tasks.cleanup_old_media',
        'schedule': 86400.0,  # Every 24 hours
    },
}

app.conf.timezone = 'Europe/Moscow'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')