from django.contrib import admin
from .models import Execution, StoredFile


@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = ("module_id", "quarter", "status", "progress", "created_by", "created_at", "finished_at")
    list_filter = ("module_id", "status", "quarter")
    search_fields = ("module_id", "summary", "celery_task_id")
    readonly_fields = ("id", "celery_task_id", "created_at", "started_at", "finished_at")


@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    list_display = ("original_name", "bucket", "status", "size_bytes", "created_by", "created_at")
    list_filter = ("bucket", "status", "created_at")
    search_fields = ("original_name", "object_key", "sha256")
    readonly_fields = ("id", "object_key", "size_bytes", "sha256", "created_at")
