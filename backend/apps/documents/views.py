import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, parsers, status, viewsets
from rest_framework.response import Response

from config.exceptions import ServiceUnavailable

from .models import Document
from .serializers import DocumentSerializer, DocumentUploadSerializer
from .services.deletion import VectorStoreError, delete_document
from .tasks import process_document

logger = logging.getLogger(__name__)


class DocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Upload, list, inspect and delete the current user's PDF documents.
    Object-level security: the queryset is always scoped to request.user,
    so another user's document id yields 404.
    """

    queryset = Document.objects.all()  # only used for schema generation; get_queryset() scopes to the user
    serializer_class = DocumentSerializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser)
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentUploadSerializer
        return DocumentSerializer

    @extend_schema(
        request={"multipart/form-data": DocumentUploadSerializer},
        responses={201: DocumentSerializer, 400: OpenApiResponse(description="Validation error")},
        description="Upload a PDF (multipart/form-data, field `file`). Processing runs in the background.",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        process_document.delay(document.id)
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None, 503: OpenApiResponse(description="Vector store unavailable")})
    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        try:
            delete_document(document)
        except VectorStoreError as exc:
            logger.error("Delete aborted for document %s: %s", document.id, exc)
            raise ServiceUnavailable("Vector store is unavailable; the document was not deleted. Try again.")
        return Response(status=status.HTTP_204_NO_CONTENT)
