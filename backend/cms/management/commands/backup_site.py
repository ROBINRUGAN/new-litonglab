# designed by mew
"""Portable snapshot of SQLite, revision history, accounts, and uploaded media."""

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "在线备份数据库与全部素材；备份目录不能位于公开媒体目录内。"

    def add_arguments(self, parser):
        parser.add_argument("--output", default=str(settings.DATA_DIR / "backups"))
        parser.add_argument("--keep", type=int, default=30)

    def handle(self, *args, **options):
        directory = Path(options["output"]).resolve()
        if directory.is_relative_to(Path(settings.MEDIA_ROOT).resolve()):
            raise CommandError("备份不能放入公开素材目录。")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / (
            "litonglab-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".zip"
        )
        with tempfile.TemporaryDirectory() as work:
            database = Path(work) / "lab.sqlite3"
            with (
                sqlite3.connect(settings.DATABASES["default"]["NAME"]) as source,
                sqlite3.connect(database) as target,
            ):
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise CommandError("数据库完整性检查失败，备份未生成。")
            files = [("lab.sqlite3", database)]
            media = Path(settings.MEDIA_ROOT)
            if media.exists():
                files += [
                    ("media/" + str(p.relative_to(media)), p)
                    for p in sorted(media.rglob("*"))
                    if p.is_file() and not p.is_symlink()
                ]
            manifest = {
                "format": 1,
                "created": datetime.now(timezone.utc).isoformat(),
                "files": {name: file_sha256(source) for name, source in files},
            }
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with (
                os.fdopen(descriptor, "wb") as output,
                zipfile.ZipFile(
                    output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
                ) as archive,
            ):
                for name, source in files:
                    archive.write(source, name)
                archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        if options["keep"] > 0:
            for old in sorted(directory.glob("litonglab-*.zip"), reverse=True)[options["keep"] :]:
                old.unlink()
        self.stdout.write(self.style.SUCCESS(f"备份完成：{path}"))
