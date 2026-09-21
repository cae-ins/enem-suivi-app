import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="StoredFile", fields=[
        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ("original_name", models.CharField(max_length=255)), ("bucket", models.CharField(db_index=True, max_length=63)),
        ("object_key", models.CharField(max_length=1024, unique=True)),
        ("content_type", models.CharField(blank=True, max_length=255)),
        ("size_bytes", models.BigIntegerField(blank=True, null=True)), ("sha256", models.CharField(blank=True, max_length=64)),
        ("status", models.CharField(choices=[("pending", "En attente"), ("ready", "Disponible"),
                                             ("rejected", "Rejete")], db_index=True, default="pending", max_length=32)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                         to=settings.AUTH_USER_MODEL)),
    ], options={"ordering": ["-created_at"]})]
