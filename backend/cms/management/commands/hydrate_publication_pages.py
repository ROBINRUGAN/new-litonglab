# designed by mew
"""Fill newly introduced paper poster fields without changing editor-owned values."""

import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import ContentItem, Revision
from cms.services import record_revision


class Command(BaseCommand):
    help = "为已有论文补入对应 PDF 的摘要和配图；已编辑的字段保持不变。"

    @transaction.atomic
    def handle(self, *args, **options):
        path = settings.BASE_DIR / "content" / "seed" / "publications.json"
        papers = {paper["id"]: paper for paper in json.loads(path.read_text())}
        count = 0
        legacy_images = {
            "pub-1": "/assets/protocols.webp",
            "pub-4": "/assets/systems.webp",
            "pub-6": "/assets/intelligence.webp",
        }
        for item in ContentItem.objects.select_for_update().filter(kind="publication"):
            source = papers.get(item.key)
            if not source:
                continue
            if Revision.objects.filter(item=item, action="补入论文摘要和配图").exists():
                continue
            changed = False
            for data in [item.payload, (item.live or {}).get("data")]:
                if data is None:
                    continue
                for field in (
                    "abstract_en",
                    "abstract_zh",
                    "imageCaption_en",
                    "imageCaption_zh",
                    "image",
                ):
                    incoming = source.get(field, "")
                    current = data.get(field, "")
                    if incoming and (
                        field not in data
                        or (
                            field == "image"
                            and (not current or current == legacy_images.get(item.key))
                        )
                    ):
                        data[field] = incoming
                        changed = True
            if changed:
                item.version += 1
                item.save(update_fields=["payload", "live", "version", "updated_at"])
                record_revision(item, None, "补入论文摘要和配图")
                count += 1
        self.stdout.write(self.style.SUCCESS(f"更新 {count} 条论文；已有手动修改已保留。"))
