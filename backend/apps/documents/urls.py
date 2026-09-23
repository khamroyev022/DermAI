from rest_framework.routers import SimpleRouter

from .views import DocumentViewSet

app_name = "documents"

router = SimpleRouter()
router.register("", DocumentViewSet, basename="document")

urlpatterns = router.urls
