import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

from django.conf import settings  # noqa: E402

if settings.EMBEDDING_PRELOAD:
    # Load the embedding model once at web-process start so chat requests never
    # pay the model load cost.
    from apps.rag.services.embeddings import get_embedding_provider  # noqa: E402

    get_embedding_provider().warm_up()
