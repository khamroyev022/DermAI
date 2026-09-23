import logging

from django.db.models import Count, Prefetch
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.documents.models import Document
from apps.rag.services.llm import LLMError
from apps.rag.services.qdrant_service import VectorStoreError
from config.exceptions import ServiceUnavailable, UpstreamLLMError

from .models import ChatMessage, ChatSession
from .serializers import (
    ChatDocumentSerializer,
    ChatMessageSerializer,
    ChatSessionCreateSerializer,
    ChatSessionDetailSerializer,
    ChatSessionSerializer,
    SendMessageResponseSerializer,
    SendMessageSerializer,
)
from .services.chat_service import answer_question

logger = logging.getLogger(__name__)


class ChatSessionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Chat sessions are always scoped to the requesting user (object-level security)."""

    queryset = ChatSession.objects.all()  # only used for schema generation; get_queryset() scopes to the user
    serializer_class = ChatSessionSerializer
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        qs = (
            ChatSession.objects.filter(user=self.request.user)
            .select_related("document")
            .annotate(message_count=Count("messages"))
            .order_by("-updated_at")
        )
        document_id = self.request.query_params.get("document")
        if document_id and document_id.isdigit():
            qs = qs.filter(document_id=int(document_id))
        if self.action == "retrieve":
            qs = qs.prefetch_related(Prefetch("messages", queryset=ChatMessage.objects.order_by("created_at", "id")))
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return ChatSessionCreateSerializer
        if self.action == "retrieve":
            return ChatSessionDetailSerializer
        if self.action == "send_message":
            return SendMessageSerializer
        return ChatSessionSerializer

    @extend_schema(request=ChatSessionCreateSerializer, responses={201: ChatSessionSerializer})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=SendMessageSerializer,
        responses={
            200: SendMessageResponseSerializer,
            409: OpenApiResponse(description="Document not ready"),
            502: OpenApiResponse(description="LLM error"),
            503: OpenApiResponse(description="Vector store unavailable"),
        },
        description="Ask a question about the chat's document. Answers are grounded only in that document.",
    )
    @action(detail=True, methods=["post"], url_path="messages")
    def send_message(self, request, pk=None):
        chat = self.get_object()
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if chat.document.status != Document.Status.READY:
            return Response({"detail": "Document is not ready for chat."}, status=status.HTTP_409_CONFLICT)

        try:
            result = answer_question(chat, serializer.validated_data["message"])
        except VectorStoreError:
            raise ServiceUnavailable("Vector store is unavailable. Please try again.")
        except LLMError:
            raise UpstreamLLMError()

        payload = {
            "answer": result.answer,
            "sources": result.sources,
            "document": ChatDocumentSerializer(chat.document).data,
            "user_message": ChatMessageSerializer(result.user_message).data,
            "assistant_message": ChatMessageSerializer(result.assistant_message).data,
        }
        return Response(payload, status=status.HTTP_200_OK)
