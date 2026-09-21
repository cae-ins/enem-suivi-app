import uuid
from django.conf import settings
from django.db import models


class Execution(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "En attente"
        RUNNING = "running", "En cours"
        SUCCEEDED = "succeeded", "Terminee"
        FAILED = "failed", "Erreur"
        CANCELLED = "cancelled", "Arretee"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module_id = models.CharField(max_length=100, db_index=True)
    quarter = models.CharField(max_length=20, blank=True)
    parameters = models.JSONField(default=dict)
    global_parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    progress_message = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.module_id} - {self.status}"


class StoredFile(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        READY = "ready", "Disponible"
        REJECTED = "rejected", "Rejete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_name = models.CharField(max_length=255)
    bucket = models.CharField(max_length=63, db_index=True)
    object_key = models.CharField(max_length=1024, unique=True)
    content_type = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    execution = models.ForeignKey(Execution, null=True, blank=True, related_name="files", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_name
