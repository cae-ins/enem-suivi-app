from rest_framework import serializers
from enem_core.parametres import valider
from modules import charger_modules
from .models import Execution, StoredFile


class StoredFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoredFile
        fields = ("id", "original_name", "bucket", "object_key", "content_type", "size_bytes",
                  "sha256", "status", "created_by", "created_at")
        read_only_fields = fields


class UploadTicketRequestSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=255, required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=("entrees", "references"), default="entrees")
    quarter = serializers.RegexField(r"^[A-Za-z0-9_-]{1,20}$", required=False, default="non-classe")


class ExecutionSerializer(serializers.ModelSerializer):
    files = StoredFileSerializer(many=True, read_only=True)

    class Meta:
        model = Execution
        fields = ("id", "module_id", "quarter", "parameters", "global_parameters", "status", "progress",
                  "progress_message", "summary", "celery_task_id", "created_by", "created_at", "started_at",
                  "finished_at", "files")
        read_only_fields = ("status", "progress", "progress_message", "summary", "celery_task_id", "created_by",
                            "created_at", "started_at", "finished_at", "files")

    def validate_module_id(self, value):
        if value not in {module.id for module in charger_modules()}:
            raise serializers.ValidationError("Module inconnu")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        parameters = attrs.get("parameters", {})
        if not isinstance(parameters, dict):
            raise serializers.ValidationError({"parameters": ["Un objet JSON est attendu."]})
        module = next((item for item in charger_modules() if item.id == attrs.get("module_id")), None)
        if module is None:
            return attrs
        values = dict(parameters)
        values["dossier_sortie"] = "/tmp/enem-validation"
        _converted, errors = valider(module.parametres, values)
        if errors:
            raise serializers.ValidationError({"parameters": errors})
        attrs["parameters"] = {
            parameter.cle: parameters.get(parameter.cle, parameter.defaut)
            for parameter in module.parametres
            if parameter.cle != "dossier_sortie"
        }
        return attrs
