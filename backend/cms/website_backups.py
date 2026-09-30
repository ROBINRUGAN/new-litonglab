# designed by mew
"""Portable website snapshots; online restore never replaces the running database.

Accounts and sessions deliberately remain local. Restored assets receive a fresh
directory, so copying files cannot overwrite a live file before the DB commits.
"""

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import zipfile
from collections import Counter
from copy import deepcopy
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .forms import validate_payload, validate_upload
from .models import KINDS, ContentItem, MediaAsset, Revision
from .schema import SCHEMAS
from .services import record_revision

FORMAT = "litonglab-website-v1"
MAX_UPLOAD_BYTES = 512 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
SCOPE = [
    "全部网站内容、草稿、已发布版本、回收站和修改历史",
    "素材库及全部已上传图片、视频和 PDF",
    "不包含账号、密码、登录会话、程序代码和服务器配置",
]
KEY = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


def fingerprint():
    """Detect edits made after the administrator reviewed the restore preview."""
    data = {
        "items": list(
            ContentItem.objects.order_by("pk").values_list("pk", "version", "updated_at")
        ),
        "assets": list(MediaAsset.objects.order_by("pk").values_list("pk", "file", "size")),
        "revisions": list(Revision.objects.order_by("pk").values_list("pk", flat=True)),
    }
    return hashlib.sha256(json.dumps(data, default=str).encode()).hexdigest()


def safe_directory(path):
    directory = Path(path).resolve()
    if directory.is_relative_to(Path(settings.MEDIA_ROOT).resolve()):
        raise ValidationError("备份和还原临时目录不能位于公开素材目录。")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def snapshot():
    with transaction.atomic():
        items = list(ContentItem.objects.select_related("updated_by").order_by("pk"))
        identities = {item.pk: [item.kind, item.key] for item in items}
        return {
            "format": FORMAT,
            "createdAt": timezone.now().isoformat(),
            "records": [
                {
                    "kind": item.kind,
                    "id": item.key,
                    "data": item.payload,
                    "live": item.live,
                    "order": item.sort_order,
                    "version": item.version,
                    "deleted": item.is_deleted,
                    "publishedAt": item.published_at.isoformat() if item.published_at else None,
                }
                for item in items
            ],
            "revisions": [
                {
                    "item": identities[revision.item_id],
                    "snapshot": revision.snapshot,
                    "action": revision.action,
                    "actor": revision.actor.username if revision.actor else None,
                    "createdAt": revision.created_at.isoformat(),
                }
                for revision in Revision.objects.select_related("actor").order_by("pk")
            ],
            "media": [
                {
                    "file": asset.file.name,
                    "title": asset.title,
                    "alt_zh": asset.alt_zh,
                    "alt_en": asset.alt_en,
                    "credit": asset.credit,
                    "category": asset.category,
                    "mime_type": asset.mime_type,
                    "size": asset.size,
                }
                for asset in MediaAsset.objects.order_by("pk")
            ],
        }


def create_backup(directory):
    directory = safe_directory(directory)
    data = snapshot()
    media_root = Path(settings.MEDIA_ROOT).resolve()
    # Retain every library file and historical reference. Old restore directories
    # deliberately remain on disk but must not grow each subsequent backup.
    names = {asset["file"] for asset in data["media"]}

    def references(value):
        if isinstance(value, str):
            names.update(
                re.findall(
                    r"(?<![\w:/])" + re.escape(settings.MEDIA_URL) + r"([^\s\"'<>?#]+)", value
                )
            )
        elif isinstance(value, list):
            for child in value:
                references(child)
        elif isinstance(value, dict):
            for child in value.values():
                references(child)

    references(data["records"])
    references(data["revisions"])
    files = []
    for name in sorted(names):
        path = media_root / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(media_root):
            raise ValidationError("素材文件缺失或包含外部链接，备份已取消。")
        files.append(("media/" + name, path))
    content = json.dumps(data, ensure_ascii=False).encode()
    hashes = {"content.json": hashlib.sha256(content).hexdigest()}
    name = "website-" + timezone.now().strftime("%Y%m%dT%H%M%S%fZ") + ".zip"
    target = directory / name
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with (
            os.fdopen(descriptor, "wb") as output,
            zipfile.ZipFile(
                output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
            ) as archive,
        ):
            archive.writestr("content.json", content)
            for key, path in files:
                # Hash the exact bytes placed in the archive (files may grow while uploading).
                digest = hashlib.sha256()
                with path.open("rb") as source, archive.open(key, "w") as destination:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        destination.write(chunk)
                hashes[key] = digest.hexdigest()
            archive.writestr("manifest.json", json.dumps({"format": FORMAT, "files": hashes}))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def valid_order(value):
    if type(value) is not int or not 0 <= value <= 100000:
        raise ValidationError("备份中的显示顺序无效。")
    return value


def valid_date(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("备份中的日期无效。")
    parsed = parse_datetime(value)
    if parsed is None or timezone.is_naive(parsed):
        raise ValidationError("备份中的日期无效。")
    return parsed


def validate_content(data):
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValidationError("请选择从本管理界面下载的网站备份 ZIP。")
    valid_date(data.get("createdAt"))
    rows = data.get("records")
    revisions = data.get("revisions")
    assets = data.get("media")
    if not isinstance(rows, list) or not 0 < len(rows) <= 10000:
        raise ValidationError("备份内容数量无效。")
    if not isinstance(revisions, list) or len(revisions) > 100000:
        raise ValidationError("备份历史记录数量无效。")
    if not isinstance(assets, list) or len(assets) > 10000:
        raise ValidationError("备份素材数量无效。")
    identities, incoming = {}, {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError("备份条目格式无效。")
        kind, key = row.get("kind"), row.get("id")
        if (
            not isinstance(kind, str)
            or kind not in SCHEMAS
            or not isinstance(key, str)
            or not KEY.fullmatch(key)
        ):
            raise ValidationError("备份条目类型或编号无效。")
        identity = (kind, key)
        if identity in identities:
            raise ValidationError("备份包含重复条目。")
        identities[identity] = row
        incoming.setdefault(kind, []).append(key)
        valid_order(row.get("order"))
        if type(row.get("version")) is not int or row["version"] < 1:
            raise ValidationError("备份条目版本无效。")
        if type(row.get("deleted")) is not bool:
            raise ValidationError("备份条目状态无效。")
        valid_date(row.get("publishedAt"))
    for kind in ("home", "site"):
        if len(incoming.get(kind, [])) > 1:
            raise ValidationError("备份中包含重复站点配置。")

    def payload(kind, key, values, *, current=False, published=False):
        if not isinstance(values, dict):
            raise ValidationError("备份条目字段无效。")
        clean = validate_payload(
            kind, values, ContentItem(kind=kind, key=key), incoming, restoring=True
        )
        # Validate against this snapshot, not against rows that happen to exist now.
        if current:
            for spec in SCHEMAS[kind]:
                if spec["type"] not in ("reference", "references"):
                    continue
                keys = clean.get(spec["name"]) or []
                if isinstance(keys, str):
                    keys = [keys]
                for target in keys:
                    record = identities.get((spec["target"], target))
                    if not record or (published and (record["deleted"] or not record.get("live"))):
                        raise ValidationError("备份包含缺失或未发布的关联内容。")
        return clean

    slugs, components = set(), set()
    for row in rows:
        kind, key = row["kind"], row["id"]
        row["data"] = payload(kind, key, row.get("data"), current=not row["deleted"])
        live = row.get("live")
        if live is not None:
            if not isinstance(live, dict) or row["deleted"]:
                raise ValidationError("备份已发布状态无效。")
            valid_order(live.get("order"))
            row["live"] = {
                "data": payload(kind, key, live.get("data"), current=True, published=True),
                "order": live["order"],
            }
        if kind in ("page", "project") and not row["deleted"]:
            urls = set()
            for values in [row["data"], live["data"] if live else {}]:
                urls.update([values.get("slug"), *values.get("aliases", [])])
            for slug in urls - {None, ""}:
                if (kind, slug) in slugs:
                    raise ValidationError("备份包含重复网址。")
                slugs.add((kind, slug))
        if kind == "section" and not row["deleted"]:
            component = row["data"].get("component")
            if component != "content":
                if component in components:
                    raise ValidationError("备份包含重复首页栏目。")
                components.add(component)
    for revision in revisions:
        if (
            not isinstance(revision, dict)
            or not isinstance(revision.get("item"), list)
            or len(revision["item"]) != 2
        ):
            raise ValidationError("备份历史条目无效。")
        if any(not isinstance(value, str) for value in revision["item"]):
            raise ValidationError("备份历史条目无效。")
        identity = tuple(revision["item"])
        history = revision.get("snapshot")
        if identity not in identities or not isinstance(history, dict):
            raise ValidationError("备份历史条目不存在。")
        if "actorName" in history and (
            not isinstance(history["actorName"], str) or len(history["actorName"]) > 400
        ):
            raise ValidationError("备份历史操作者姓名无效。")
        history["payload"] = payload(*identity, history.get("payload"))
        valid_order(history.get("order"))
        if type(history.get("deleted")) is not bool:
            raise ValidationError("备份历史状态无效。")
        if history.get("live") is not None:
            if not isinstance(history["live"], dict):
                raise ValidationError("备份历史已发布状态无效。")
            history["live"]["data"] = payload(*identity, history["live"].get("data"))
            valid_order(history["live"].get("order"))
        if not isinstance(revision.get("action"), str) or len(revision["action"]) > 50:
            raise ValidationError("备份历史操作无效。")
        if revision.get("actor") is not None and not isinstance(revision["actor"], str):
            raise ValidationError("备份历史用户无效。")
        valid_date(revision.get("createdAt"))
    return data


def validate_archive(path, destination):
    """Fully validate and stage untrusted ZIP input before showing a preview."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = {item.filename for item in infos}
            if len(infos) != len(names) or len(infos) > 10002:
                raise ValidationError("备份包含重复文件或文件数量过多。")
            if not {"manifest.json", "content.json"}.issubset(names):
                raise ValidationError("缺少备份校验清单或内容文件。")
            total = sum(item.file_size for item in infos)
            if total > MAX_EXPANDED_BYTES:
                raise ValidationError("备份解包后超过 1 GiB，请使用服务器灾备工具。")
            for info in infos:
                key = info.filename
                parts = PurePosixPath(key).parts
                if (
                    "\\" in key
                    or "\x00" in key
                    or key.startswith("/")
                    or any(part in (".", "..") for part in parts)
                    or key != PurePosixPath(key).as_posix()
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or info.is_dir()
                    or (
                        key not in ("manifest.json", "content.json")
                        and not key.startswith("media/")
                    )
                ):
                    raise ValidationError("备份包含不安全文件路径。")
            if (
                archive.getinfo("manifest.json").file_size > 4 * 1024 * 1024
                or archive.getinfo("content.json").file_size > 32 * 1024 * 1024
            ):
                raise ValidationError("备份内容索引过大。")
            manifest = json.loads(archive.read("manifest.json"))
            if (
                not isinstance(manifest, dict)
                or manifest.get("format") != FORMAT
                or not isinstance(manifest.get("files"), dict)
                or set(manifest["files"]) != names - {"manifest.json"}
            ):
                raise ValidationError("备份清单与文件不一致。")
            for key, expected in manifest["files"].items():
                target = destination / key
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with archive.open(key) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        output.write(chunk)
                if digest.hexdigest() != expected:
                    raise ValidationError("备份文件校验失败，文件可能已损坏。")
            data = validate_content(json.loads((destination / "content.json").read_text()))
            seen = set()
            for asset in data["media"]:
                if not isinstance(asset, dict) or not isinstance(asset.get("file"), str):
                    raise ValidationError("备份素材格式无效。")
                key = "media/" + asset["file"]
                if key not in names or key in seen:
                    raise ValidationError("备份素材文件缺失或重复。")
                seen.add(key)
                for field, limit in {
                    "title": 200,
                    "alt_zh": 300,
                    "alt_en": 300,
                    "credit": 300,
                    "category": 100,
                }.items():
                    if not isinstance(asset.get(field), str) or len(asset[field]) > limit:
                        raise ValidationError("备份素材说明无效。")
            # Validate the bytes as real images / MP4 / PDF, including unregistered files.
            from django.core.files import File

            media_types = {}
            for key in names - {"manifest.json", "content.json"}:
                with (destination / key).open("rb") as stream:
                    media_types[key] = validate_upload(File(stream, name=key))
            for asset in data["media"]:
                asset["mime_type"] = media_types["media/" + asset["file"]]
                asset["size"] = (destination / "media" / asset["file"]).stat().st_size
            (destination / "content.json").write_text(json.dumps(data, ensure_ascii=False))
            counts = Counter(row["kind"] for row in data["records"])
            return {
                "createdAt": data["createdAt"],
                "contentCount": len(data["records"]),
                "revisionCount": len(data["revisions"]),
                "mediaCount": len(names) - 2,
                "totalBytes": total,
                "counts": [
                    {"kind": kind, "label": label, "count": counts[kind]}
                    for kind, label in KINDS
                    if counts[kind]
                ],
            }
    except (
        zipfile.BadZipFile,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as error:
        raise ValidationError("备份文件格式无效或内容已损坏。") from error


def restore_snapshot(directory, user, expected_fingerprint):
    from .editor_api import EditConflict

    data = json.loads((directory / "content.json").read_text())
    media_root = Path(settings.MEDIA_ROOT)
    relative = "restored/" + secrets.token_hex(24)
    destination = media_root / relative
    prefix = settings.MEDIA_URL
    files = {
        path.relative_to(directory / "media").as_posix(): relative
        + "/"
        + hashlib.sha256(path.relative_to(directory / "media").as_posix().encode()).hexdigest()[:24]
        + path.suffix.lower()
        for path in (directory / "media").rglob("*")
        if path.is_file()
    }
    paths = {prefix + old: prefix + new for old, new in files.items()}
    # Seed assets also have public /assets and /papers URLs. Keep their exact
    # backup bytes available even if a later code release changes those files.
    paths.update(
        {
            "/" + old.removeprefix("original/"): prefix + new
            for old, new in files.items()
            if old.startswith("original/")
        }
    )
    # Rich HTML and links may append query strings/fragments to a media URL.
    pattern = (
        re.compile(
            r"(?<![\w:/])(?:"
            + "|".join(re.escape(key) for key in sorted(paths, key=len, reverse=True))
            + r")(?=$|[?#\s\"'<>)])"
        )
        if paths
        else None
    )

    def remap(value):
        if isinstance(value, str) and pattern:
            return pattern.sub(lambda match: paths[match.group()], value)
        if isinstance(value, list):
            return [remap(item) for item in value]
        if isinstance(value, dict):
            return {key: remap(item) for key, item in value.items()}
        return value

    material = remap(deepcopy(data))
    # A fresh directory can be removed on rollback without touching live assets.
    owned_directory = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.mkdir()
        owned_directory = True
        for old, new in files.items():
            shutil.copyfile(directory / "media" / old, media_root / new)
        with transaction.atomic():
            if fingerprint() != expected_fingerprint:
                raise EditConflict("预览后网站已被修改，请重新上传备份并确认，避免覆盖最新修改。")
            current_versions = {
                (item.kind, item.key): item.version for item in ContentItem.objects.all()
            }
            ContentItem.objects.all().delete()
            MediaAsset.objects.all().delete()
            identities = {}
            for row in material["records"]:
                item = ContentItem.objects.create(
                    kind=row["kind"],
                    key=row["id"],
                    payload=row["data"],
                    live=row["live"],
                    sort_order=row["order"],
                    is_deleted=row["deleted"],
                    updated_by=user,
                    version=max(row["version"], current_versions.get((row["kind"], row["id"]), 0))
                    + 1,
                    published_at=valid_date(row["publishedAt"]),
                )
                identities[(item.kind, item.key)] = item
            users = dict(get_user_model().objects.values_list("username", "pk"))
            for row in material["revisions"]:
                revision = Revision.objects.create(
                    item=identities[tuple(row["item"])],
                    snapshot=row["snapshot"],
                    action=row["action"],
                    actor_id=users.get(row["actor"]),
                )
                Revision.objects.filter(pk=revision.pk).update(
                    created_at=valid_date(row["createdAt"])
                )
            for item in identities.values():
                record_revision(item, user, "从网站备份恢复")
            for row in material["media"]:
                path = files[row["file"]]
                MediaAsset.objects.create(
                    file=path,
                    title=row["title"],
                    alt_zh=row["alt_zh"],
                    alt_en=row["alt_en"],
                    credit=row["credit"],
                    category=row["category"],
                    mime_type=row["mime_type"],
                    size=(media_root / path).stat().st_size,
                    uploaded_by=user,
                )
    except Exception:
        if owned_directory:
            shutil.rmtree(destination, ignore_errors=True)
        raise
