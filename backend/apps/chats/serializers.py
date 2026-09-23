from rest_framework import serializers

from apps.documents.models import Document

from .models import ChatMessage, ChatSession


class ChatDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ("id", "title", "status", "page_count")
        read_only_fields = fields


class SourceSerializer(serializers.Serializer):
    chunk_id = serializers.IntegerField()
    page_start = serializers.IntegerField()
    page_end = serializers.IntegerField()
    score = serializers.FloatField(required=False)
    excerpt = serializers.CharField()


class ChatMessageSerializer(serializers.ModelSerializer):
    sources = SourceSerializer(many=True, read_only=True)

    class Meta:
        model = ChatMessage
        fields = ("id", "role", "content", "sources", "created_at")
        read_only_fields = fields


class ChatSessionSerializer(serializers.ModelSerializer):
    document = ChatDocumentSerializer(read_only=True)
    message_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChatSession
        fields = ("id", "title", "document", "message_count", "created_at", "updated_at")
        read_only_fields = fields


class ChatSessionDetailSerializer(ChatSessionSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta(ChatSessionSerializer.Meta):
        fields = ChatSessionSerializer.Meta.fields + ("messages",)


class ChatSessionCreateSerializer(serializers.Serializer):
    document_id = serializers.IntegerField()
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_document_id(self, value: int) -> int:
        user = self.context["request"].user
        try:
            document = Document.objects.get(pk=value, user=user)
        except Document.DoesNotExist:
            raise serializers.ValidationError("Document not found.")
        if document.status != Document.Status.READY:
            raise serializers.ValidationError("Document is not ready for chat yet.")
        self.context["document"] = document
        return value

    def create(self, validated_data):
        document = self.context["document"]
        title = (validated_data.get("title") or "").strip() or document.title[:255]
        return ChatSession.objects.create(user=self.context["request"].user, document=document, title=title)

    def to_representation(self, instance):
        instance.message_count = 0
        return ChatSessionSerializer(instance, context=self.context).data


class SendMessageSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=8000, trim_whitespace=True)

    def validate_message(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message cannot be empty.")
        return value


class SendMessageResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    sources = SourceSerializer(many=True)
    document = ChatDocumentSerializer()
    user_message = ChatMessageSerializer()
    assistant_message = ChatMessageSerializer()
