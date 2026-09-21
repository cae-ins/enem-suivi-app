from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...minio import ensure_buckets, s3_client
from ...models import StoredFile


SUPPORTED_EXTENSIONS = {".csv", ".dta", ".parquet", ".sav", ".xls", ".xlsx"}


class Command(BaseCommand):
    help = "Importe dans MinIO des fichiers locaux montes en lecture seule."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default="/data/import")
        parser.add_argument("--category", choices=("entrees", "references"), default="entrees")
        parser.add_argument("--quarter", default="non-classe")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        root = Path(options["path"]).resolve()
        if not root.exists() or not root.is_dir():
            raise CommandError(f"Dossier introuvable : {root}")
        files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS)
        self.stdout.write(f"{len(files)} fichier(s) admissible(s) dans {root}")
        if options["dry_run"]:
            for path in files:
                self.stdout.write(f"  {path.relative_to(root)}")
            return

        ensure_buckets()
        client = s3_client()
        bucket = settings.MINIO_INPUT_BUCKET if options["category"] == "entrees" else settings.MINIO_REFERENCE_BUCKET
        imported = skipped = 0
        for path in files:
            digest = self._sha256(path)
            if StoredFile.objects.filter(sha256=digest, status=StoredFile.Status.READY).exists():
                skipped += 1
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            object_key = str(PurePosixPath(options["quarter"], "import-local", digest[:12], relative))
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            client.upload_file(str(path), bucket, object_key, ExtraArgs={"ContentType": content_type})
            StoredFile.objects.create(
                original_name=path.name,
                bucket=bucket,
                object_key=object_key,
                content_type=content_type,
                size_bytes=path.stat().st_size,
                sha256=digest,
                status=StoredFile.Status.READY,
            )
            imported += 1
            self.stdout.write(self.style.SUCCESS(f"Importe : {relative}"))
        self.stdout.write(self.style.SUCCESS(f"Termine : {imported} importe(s), {skipped} deja present(s)"))

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
