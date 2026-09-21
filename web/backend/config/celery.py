import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.backend.config.settings")
app = Celery("enem_suivi")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
