import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def document_upload_path(instance: "Document", filename: str) -> str:
    """Store PDFs as media/documents/<user_id>/<uuid>.pdf (never trust the client filename)."""
    return f"documents/{instance.user_id}/{uuid.uuid4().hex}.pdf"


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        PROCESSING = "PROCESSING", "Processing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path, max_length=500)
    file_size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    page_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADED)
    processing_progress = models.PositiveSmallIntegerField(default=0)
    processing_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("user", "sha256"), name="uniq_document_user_sha256"),
        ]
        indexes = [
            models.Index(fields=("user", "created_at"), name="idx_document_user_created"),
            models.Index(fields=("user", "sha256"), name="idx_document_user_sha256"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_ready(self) -> bool:
        return self.status == self.Status.READY

    def set_progress(self, progress: int, status: str | None = None) -> None:
        """Persist progress (0-100) and optionally status using a minimal UPDATE."""
        self.processing_progress = max(0, min(100, int(progress)))
        fields = ["processing_progress", "updated_at"]
        if status is not None:
            self.status = status
            fields.append("status")
        self.save(update_fields=fields)

    def mark_failed(self, error: str) -> None:
        self.status = self.Status.FAILED
        self.processing_error = (error or "Unknown error")[:4000]
        self.save(update_fields=["status", "processing_error", "updated_at"])

    def file_path(self) -> Path:
        return Path(self.file.path)


class DocumentPage(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="pages")
    page_number = models.PositiveIntegerField()
    text = models.TextField()  # LONGTEXT on MySQL via migration
    has_text = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("page_number",)
        constraints = [
            models.UniqueConstraint(fields=("document", "page_number"), name="uniq_page_document_number"),
        ]
        indexes = [
            models.Index(fields=("document", "page_number"), name="idx_page_document_number"),
        ]

    def __str__(self) -> str:
        return f"Document {self.document_id} page {self.page_number}"


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    page_start = models.PositiveIntegerField()
    page_end = models.PositiveIntegerField()
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()  # LONGTEXT on MySQL via migration
    # UUID of the point stored in Qdrant. The embedding vector itself lives only in Qdrant.
    qdrant_point_id = models.CharField(max_length=36, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("chunk_index",)
        constraints = [
            models.UniqueConstraint(fields=("document", "chunk_index"), name="uniq_chunk_document_index"),
        ]
        indexes = [
            models.Index(fields=("document", "chunk_index"), name="idx_chunk_document_index"),
        ]

    def __str__(self) -> str:
        return f"Document {self.document_id} chunk {self.chunk_index} (p{self.page_start}-{self.page_end})"

    @property
    def page_label(self) -> str:
        if self.page_start == self.page_end:
            return str(self.page_start)
        return f"{self.page_start}-{self.page_end}"
