from rest_framework.routers import SimpleRouter

from .views import ChatSessionViewSet

app_name = "chats"

router = SimpleRouter()
router.register("", ChatSessionViewSet, basename="chat")

urlpatterns = router.urls
