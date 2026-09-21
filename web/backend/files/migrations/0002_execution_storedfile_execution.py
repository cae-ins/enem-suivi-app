import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("files", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Execution",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("module_id", models.CharField(db_index=True, max_length=100)),
                ("quarter", models.CharField(blank=True, max_length=20)),
                ("parameters", models.JSONField(default=dict)),
                ("global_parameters", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("queued", "En attente"), ("running", "En cours"),
                    ("succeeded", "Terminee"), ("failed", "Erreur"), ("cancelled", "Arretee")],
                    db_index=True, default="queued", max_length=20)),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("progress_message", models.CharField(blank=True, max_length=255)),
                ("summary", models.TextField(blank=True)),
                ("celery_task_id", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="storedfile", name="execution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name="files", to="files.execution"),
        ),
    ]
