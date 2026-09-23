from rest_framework import serializers

from .models import Document
from .services.validation import validate_pdf_upload


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "original_filename",
            "file_size",
            "sha256",
            "page_count",
            "status",
            "processing_progress",
            "processing_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(write_only=True)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        uploaded = attrs["file"]
        inspection = validate_pdf_upload(uploaded)
        user = self.context["request"].user
        if Document.objects.filter(user=user, sha256=inspection.sha256).exists():
            raise serializers.ValidationError({"file": "You have already uploaded this PDF."})
        attrs["inspection"] = inspection
        return attrs

    def create(self, validated_data):
        uploaded = validated_data["file"]
        inspection = validated_data["inspection"]
        title = (validated_data.get("title") or "").strip() or inspection.title
        return Document.objects.create(
            user=self.context["request"].user,
            title=title[:255],
            original_filename=(uploaded.name or "upload.pdf")[:255],
            file=uploaded,
            file_size=inspection.size,
            sha256=inspection.sha256,
            page_count=inspection.page_count,
            status=Document.Status.UPLOADED,
            processing_progress=0,
        )

    def to_representation(self, instance):
        return DocumentSerializer(instance, context=self.context).data
