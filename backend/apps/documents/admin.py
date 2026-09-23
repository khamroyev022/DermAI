from django.contrib import admin

from .models import Document, DocumentChunk, DocumentPage


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "status", "processing_progress", "page_count", "file_size", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "original_filename", "sha256", "user__username")
    readonly_fields = ("sha256", "file_size", "created_at", "updated_at")


@admin.register(DocumentPage)
class DocumentPageAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "page_number", "has_text")
    list_filter = ("has_text",)
    search_fields = ("document__title",)


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "chunk_index", "page_start", "page_end", "qdrant_point_id")
    search_fields = ("document__title", "qdrant_point_id")
