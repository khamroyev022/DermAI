import os

from celery import Celery
from celery.signals import worker_process_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("book_ai")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_process_init.connect
def preload_embedding_model(**kwargs):
    """Load the embedding model once per worker process instead of per task."""
    from django.conf import settings

    if not settings.EMBEDDING_PRELOAD:
        return
    from apps.rag.services.embeddings import get_embedding_provider

    get_embedding_provider().warm_up()
