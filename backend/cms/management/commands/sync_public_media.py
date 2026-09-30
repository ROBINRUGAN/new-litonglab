# designed by mew
"""Register bundled public files in the editable media browser."""

import json
import re
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from cms.media_library import (
    MIME_BY_SUFFIX,
    default_media_category,
    media_titles,
    mime_for_path,
    referenced_media_categories,
)
from cms.models import ContentItem, MediaAsset

ASSET_SUFFIXES = set(MIME_BY_SUFFIX)
LEGACY_PORTRAIT = re.compile(r"^/images/people/[a-z0-9-]+\.jpe?g$")
PERSON_PLACEHOLDER = "/images/person-placeholder.svg"


def normalize_person_photos(items):
    for item in items:
        if item.kind != "person":
            continue
        updates = []
        for field in ("payload", "live"):
            value = getattr(item, field)
            data = value.get("data", {}) if field == "live" and isinstance(value, dict) else value
            if not isinstance(data, dict):
                continue
            changed = any(name in data for name in ("imagePosition", "portraitInset"))
            data.pop("imagePosition", None)
            data.pop("portraitInset", None)
            if data.get("image") in ("/images/litong.webp", "/media/original/images/litong.webp"):
                data["image"] = "/images/litong-portrait.webp"
                changed = True
            if changed:
                updates.append(field)
        if updates:
            item.version += 1
            item.save(update_fields=[*updates, "version", "updated_at"])
    references = json.dumps(list(ContentItem.objects.values_list("payload", "live")))
    if "images/litong.webp" not in references:
        relative = "original/images/litong.webp"
        MediaAsset.objects.filter(file=relative).delete()
        (Path(settings.MEDIA_ROOT) / relative).unlink(missing_ok=True)


def is_default_title(asset, desired):
    current = asset.title.strip()
    old_label = desired.split("】", 1)[1] if desired.startswith("【") else desired
    if current in {Path(asset.file.name).stem, Path(asset.file.name).name, old_label}:
        return True
    return asset.file.name.startswith("uploads/") and Path(current).suffix.lower() in ASSET_SUFFIXES


def repair_legacy_portraits(items):
    legacy_urls = set()
    repaired = 0
    for item in items:
        if item.kind != "person" or not item.payload.get("placeholder"):
            continue
        updates = []
        for field in ("payload", "live"):
            value = getattr(item, field)
            data = value.get("data", {}) if field == "live" and isinstance(value, dict) else value
            if isinstance(data, dict) and LEGACY_PORTRAIT.fullmatch(str(data.get("image", ""))):
                legacy_urls.add(data["image"])
                data["image"] = PERSON_PLACEHOLDER
                updates.append(field)
        if updates:
            item.save(update_fields=updates)
            repaired += 1
    references = json.dumps(
        list(ContentItem.objects.values_list("payload", "live")), ensure_ascii=False
    )
    deleted = 0
    for url in legacy_urls:
        if url in references:
            continue
        relative = "original/" + url.lstrip("/")
        MediaAsset.objects.filter(file=relative).delete()
        file = Path(settings.MEDIA_ROOT) / relative
        if file.is_file():
            file.unlink()
            deleted += 1
    return repaired, deleted


class Command(BaseCommand):
    help = "Add newly bundled images, videos and PDFs to the media browser."

    def handle(self, *args, **options):
        public = settings.BASE_DIR / "frontend" / "public"
        if not public.exists():
            public = settings.FRONTEND_DIR
        content_items = list(ContentItem.objects.filter(is_deleted=False))
        repaired, deleted = repair_legacy_portraits(content_items)
        normalize_person_photos(content_items)
        titles = media_titles(content_items)
        categories = referenced_media_categories(content_items)
        paper_titles = {
            item.payload.get("title") for item in content_items if item.kind == "publication"
        }
        created = 0
        for source in public.rglob("*"):
            if not source.is_file() or source.suffix.lower() not in ASSET_SUFFIXES:
                continue
            relative = "original/" + str(source.relative_to(public))
            if MediaAsset.objects.filter(file=relative).exists():
                continue
            title = titles.get(relative, source.stem)[:200]
            target = Path(settings.MEDIA_ROOT) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            MediaAsset.objects.create(
                title=title,
                alt_zh=title,
                alt_en=title,
                file=relative,
                mime_type=mime_for_path(source.name),
                size=source.stat().st_size,
                category=categories.get(relative, default_media_category(relative)),
            )
            created += 1
        corrected = 0
        renamed = 0
        for asset in MediaAsset.objects.all().iterator():
            updates = []
            mime_type = mime_for_path(asset.file.name)
            if mime_type != "application/octet-stream" and asset.mime_type != mime_type:
                asset.mime_type = mime_type
                updates.append("mime_type")
                corrected += 1
            desired = titles.get(asset.file.name)
            desired_category = categories.get(
                asset.file.name, default_media_category(asset.file.name)
            )
            if asset.category in ("", "初始素材"):
                asset.category = desired_category
                updates.append("category")
            legacy_placeholder_title = (
                asset.file.name == "original/images/paper-placeholder.svg"
                and asset.title in paper_titles
            )
            if (
                desired
                and asset.title != desired
                and (is_default_title(asset, desired) or legacy_placeholder_title)
            ):
                asset.title = desired[:200]
                updates.append("title")
                renamed += 1
            if updates:
                asset.save(update_fields=updates)
        group = Group.objects.filter(name="编辑人员").first()
        if group:
            group.permissions.add(
                *Permission.objects.filter(
                    content_type__app_label="cms", codename="delete_mediaasset"
                )
            )
        self.stdout.write(
            f"素材库新增 {created} 个文件；修正类型 {corrected} 个；更新名称 {renamed} 个；"
            f"替换旧头像 {repaired} 条，删除旧示例图 {deleted} 张。"
        )
