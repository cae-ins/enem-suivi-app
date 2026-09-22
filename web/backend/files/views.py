import datetime as dt
import re
import uuid
from dataclasses import fields, is_dataclass
from pathlib import Path
from django.conf import settings
from django.db import connection
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from modules import charger_modules
from .minio import ensure_buckets, s3_client, s3_public_client
from .models import Execution, StoredFile
from .serializers import ExecutionSerializer, StoredFileSerializer, UploadTicketRequestSerializer
from .tasks import run_execution


def _json_value(value):
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _parameter_schema(parameter):
    schema = {
        "key": parameter.cle,
        "label": parameter.libelle,
        "type": parameter.type,
        "default": _json_value(parameter.defaut),
        "required": parameter.obligatoire,
        "help": parameter.aide,
        "note": parameter.note,
        "group": parameter.groupe,
    }
    for attribute in ("mini", "maxi", "options", "types", "maxi_lignes"):
        if hasattr(parameter, attribute):
            schema[attribute] = _json_value(getattr(parameter, attribute))
    if hasattr(parameter, "colonnes"):
        schema["columns"] = _json_value(parameter.colonnes)
    return schema


@api_view(["GET"])
@permission_classes([AllowAny])
def health(_request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    ensure_buckets()
    return Response({"status": "ok", "database": "ok", "object_storage": "ok"})


@api_view(["GET"])
def module_catalog(_request):
    return Response([{"id": m.id, "name": m.nom, "short_name": m.nom_court or m.nom,
                      "description": m.description, "team": m.equipe,
                      "frequency": m.frequence_libelle, "order": m.ordre,
                      "parameters": [_parameter_schema(p) for p in m.parametres if p.cle != "dossier_sortie"]}
                     for m in charger_modules()])


class StoredFileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StoredFile.objects.select_related("created_by")
    serializer_class = StoredFileSerializer

    @action(detail=False, methods=["post"], url_path="upload-ticket")
    def upload_ticket(self, request):
        serializer = UploadTicketRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(data["filename"]).name).strip("._")
        if not safe_name:
            return Response({"detail": "Nom de fichier invalide"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        bucket = settings.MINIO_INPUT_BUCKET if data["category"] == "entrees" else settings.MINIO_REFERENCE_BUCKET
        file_id = uuid.uuid4()
        object_key = f"{data['quarter']}/{dt.date.today():%Y/%m}/{file_id}/{safe_name}"
        record = StoredFile.objects.create(id=file_id, original_name=data["filename"], bucket=bucket,
                                           object_key=object_key,
                                           content_type=data.get("content_type", ""), created_by=request.user)
        upload_url = s3_public_client().generate_presigned_url(
            "put_object", Params={"Bucket": bucket, "Key": record.object_key,
                                  "ContentType": record.content_type or "application/octet-stream"}, ExpiresIn=900)
        return Response({"id": record.id, "method": "PUT", "upload_url": upload_url,
                         "expires_in_seconds": 900}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete(self, _request, pk=None):
        record = self.get_object()
        try:
            info = s3_client().head_object(Bucket=record.bucket, Key=record.object_key)
        except Exception:
            return Response({"detail": "Objet non disponible dans MinIO"}, status=status.HTTP_409_CONFLICT)
        record.size_bytes = info["ContentLength"]
        record.status = StoredFile.Status.READY
        record.save(update_fields=["size_bytes", "status"])
        return Response(self.get_serializer(record).data)

    @action(detail=True, methods=["get"])
    def download(self, _request, pk=None):
        record = self.get_object()
        if record.status != StoredFile.Status.READY:
            return Response({"detail": "Fichier non disponible"}, status=status.HTTP_409_CONFLICT)
        url = s3_public_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": record.bucket,
                "Key": record.object_key,
                "ResponseContentDisposition": f'attachment; filename="{Path(record.original_name).name}"',
            },
            ExpiresIn=300,
        )
        return Response({"download_url": url, "expires_in_seconds": 300})


class ExecutionViewSet(viewsets.ModelViewSet):
    queryset = Execution.objects.select_related("created_by").prefetch_related("files")
    serializer_class = ExecutionSerializer
    http_method_names = ("get", "post", "head", "options")

    def perform_create(self, serializer):
        execution = serializer.save(created_by=self.request.user)

        def enqueue():
            task = run_execution.delay(str(execution.id))
            Execution.objects.filter(pk=execution.pk).update(celery_task_id=task.id)

        transaction.on_commit(enqueue)
