from __future__ import annotations

import datetime as dt
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from enem_core.execution import lancer
from modules import charger_modules

from .minio import ensure_buckets, s3_client
from .models import Execution, StoredFile


@shared_task
def service_ping() -> dict[str, str]:
    return {"status": "ok", "worker": "celery"}


@shared_task(bind=True)
def run_execution(self, execution_id: str) -> dict[str, str]:
    execution = Execution.objects.get(pk=execution_id)
    modules = {module.id: module for module in charger_modules()}
    module = modules.get(execution.module_id)
    if module is None:
        return _fail(execution, "Module inconnu")

    execution.status = Execution.Status.RUNNING
    execution.started_at = timezone.now()
    execution.celery_task_id = self.request.id or execution.celery_task_id
    execution.save(update_fields=["status", "started_at", "celery_task_id"])
    work_root = Path("/tmp/enem-executions") / str(execution.id)
    parameters = dict(execution.parameters)
    parameters["dossier_sortie"] = str(work_root)

    def progression(value, message):
        progress = max(0, min(100, int(value)))
        Execution.objects.filter(pk=execution.pk).update(progress=progress, progress_message=message[:255])

    try:
        result = lancer(module, parameters, dict(execution.global_parameters), progression=progression)
        if result.statut != "termine" and result.statut != "terminé":
            return _fail(execution, result.resume or result.statut)
        ensure_buckets()
        client = s3_client()
        for filename in result.fichiers:
            path = Path(filename)
            if not path.exists() or not path.is_file():
                continue
            key = f"{execution.quarter or 'non-classe'}/{execution.module_id}/{execution.id}/{path.name}"
            client.upload_file(str(path), settings.MINIO_OUTPUT_BUCKET, key)
            StoredFile.objects.create(
                original_name=path.name,
                bucket=settings.MINIO_OUTPUT_BUCKET,
                object_key=key,
                size_bytes=path.stat().st_size,
                status=StoredFile.Status.READY,
                created_by=execution.created_by,
                execution=execution,
            )
        execution.status = Execution.Status.SUCCEEDED
        execution.progress = 100
        execution.summary = result.resume
        execution.finished_at = timezone.now()
        execution.save(update_fields=["status", "progress", "summary", "finished_at"])
        return {"status": execution.status, "execution_id": str(execution.id)}
    except Exception as exc:
        return _fail(execution, f"{type(exc).__name__}: {exc}")


def _fail(execution: Execution, message: str) -> dict[str, str]:
    execution.status = Execution.Status.FAILED
    execution.summary = message
    execution.finished_at = timezone.now()
    execution.save(update_fields=["status", "summary", "finished_at"])
    return {"status": execution.status, "execution_id": str(execution.id), "message": message}
