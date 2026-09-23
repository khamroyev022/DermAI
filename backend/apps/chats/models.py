from django.conf import settings
from django.db import models

from apps.documents.models import Document


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chat_sessions")
    title = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=("user", "document"), name="idx_chat_user_document"),
            models.Index(fields=("user", "updated_at"), name="idx_chat_user_updated"),
        ]

    def __str__(self) -> str:
        return self.title or f"Chat {self.pk}"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "USER", "User"
        ASSISTANT = "ASSISTANT", "Assistant"

    chat = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()  # LONGTEXT on MySQL
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(fields=("chat", "created_at"), name="idx_message_chat_created"),
        ]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:40]}"
