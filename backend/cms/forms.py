# designed by mew
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import bleach
from django import forms
from django.core.exceptions import ValidationError
from PIL import Image

from .media_library import mime_for_path
from .models import ContentItem, MediaAsset
from .schema import SCHEMAS


def safe_url(value):
    if not value:
        return ""
    value = str(value).strip()
    if "\\" in value or any(ord(c) < 32 for c in value) or value.startswith("//"):
        raise ValidationError("请输入站内路径或有效的 https/http/mailto 链接。")
    if value.startswith(("/", "#")):
        return value
    u = urlsplit(value)
    if u.scheme in ("http", "https") and u.netloc:
        return value
    if u.scheme == "mailto" and "@" in u.path:
        return value
    raise ValidationError("不支持此链接协议。请使用 /站内路径、https:// 或 mailto:。")


def clean_rich(value):
    tags = [
        "p",
        "br",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "blockquote",
        "ul",
        "ol",
        "li",
        "a",
        "img",
        "figure",
        "figcaption",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "hr",
        "pre",
        "code",
        "div",
        "span",
        "details",
        "summary",
        "video",
        "source",
    ]
    attrs = {
        "a": ["href", "title", "target", "rel"],
        "img": ["src", "alt", "title", "width", "height", "loading"],
        "th": ["colspan", "rowspan"],
        "td": ["colspan", "rowspan"],
        "video": ["src", "poster", "controls", "muted", "loop", "playsinline"],
        "source": ["src", "type"],
    }
    result = bleach.clean(
        value or "", tags=tags, attributes=attrs, protocols=["http", "https", "mailto"], strip=True
    )
    return bleach.linkifier.Linker(
        callbacks=[
            bleach.callbacks.nofollow,
            lambda attrs, new: {**attrs, (None, "rel"): "noopener noreferrer nofollow"},
        ],
        skip_tags=["pre", "code"],
    ).linkify(result)


class LinksField(forms.Field):
    def to_python(self, value):
        if not value:
            return []
        try:
            items = json.loads(value) if isinstance(value, str) else value
        except (TypeError, ValueError):
            raise ValidationError("链接数据无效。")
        if not isinstance(items, list) or len(items) > 100:
            raise ValidationError("每个条目最多 100 个链接。")
        result = []
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError("链接格式无效。")
            url = safe_url(item.get("url", ""))
            if url:
                result.append({"label": str(item.get("label", "链接"))[:150], "url": url})
        return result


def schema_fields(kind, incoming=None):
    fields = {}
    for spec in SCHEMAS[kind]:
        name, typ = spec["name"], spec["type"]
        kw = {
            "label": spec["label"],
            "required": spec.get("required", False),
            "help_text": spec.get("help", ""),
            "initial": spec.get("default", ""),
        }
        if typ in ("reference", "references"):
            choices = [
                (p.key, str(p))
                for p in ContentItem.objects.filter(kind=spec["target"], is_deleted=False)
            ]
            choices += [
                (key, key)
                for key in (incoming or {}).get(spec["target"], [])
                if key not in {k for k, _ in choices}
            ]
            if typ == "reference":
                fields[name] = forms.ChoiceField(choices=[("", "---------")] + choices, **kw)
            else:
                fields[name] = forms.MultipleChoiceField(
                    choices=choices, widget=forms.SelectMultiple(attrs={"size": 8}), **kw
                )
        elif typ == "choice":
            fields[name] = forms.ChoiceField(choices=spec["choices"], **kw)
        elif typ in ("integer", "year"):
            fields[name] = forms.IntegerField(
                min_value=spec.get("min_value", 1900 if typ == "year" else 0),
                max_value=spec.get("max_value", 2200 if typ == "year" else 100000),
                **kw,
            )
        elif typ == "date":
            fields[name] = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **kw)
        elif typ == "boolean":
            fields[name] = forms.BooleanField(**{**kw, "required": False})
        elif typ == "links":
            fields[name] = LinksField(**kw)
        elif typ == "email":
            fields[name] = forms.EmailField(**kw)
        elif typ == "slug":
            fields[name] = forms.SlugField(max_length=100, **kw)
        else:
            fields[name] = forms.CharField(**kw)
    return fields


def validate_payload(kind, payload, instance=None, incoming=None, *, restoring=False):
    """Validate and sanitize both visual edits and portable content snapshots."""
    form_type = type("PayloadValidation", (forms.Form,), schema_fields(kind, incoming))
    form = form_type(payload)
    if not form.is_valid():
        raise ValidationError(form.errors.as_json())
    result = dict(payload)
    for spec in SCHEMAS[kind]:
        key, typ = spec["name"], spec["type"]
        value = form.cleaned_data.get(key)
        if typ in ("url", "asset"):
            value = safe_url(value)
        if typ == "rich":
            value = clean_rich(value)
        if typ == "date":
            value = value.isoformat() if value else ""
        result[key] = value if value is not None else ""
    if kind in ("person", "project") and not (result.get("name_en") or result.get("name_zh")):
        raise ValidationError("至少填写一种语言的名称。")
    if kind in ("news", "group", "page", "navigation", "direction") and not (
        result.get("title_en") or result.get("title_zh")
    ):
        raise ValidationError("至少填写一种语言的标题。")
    if kind == "photo":
        for field in ("date", "album", "caption_zh", "caption_en"):
            result.pop(field, None)
    if kind == "person":
        result.pop("imagePosition", None)
        result.pop("portraitInset", None)
    if kind in ("page", "project"):
        slug = result["slug"]
        if slug in (
            "admin",
            "api",
            "media",
            "static",
            "assets",
            "login",
            "register",
            "index",
            "edit",
        ):
            raise ValidationError("此页面短名为系统保留名称。")
        qs = ContentItem.objects.filter(kind=kind, is_deleted=False)
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        if not restoring and any(
            p.payload.get("slug") == slug
            or (p.live and p.live["data"].get("slug") == slug)
            or slug in p.payload.get("aliases", [])
            or (p.live and slug in p.live["data"].get("aliases", []))
            for p in qs
        ):
            raise ValidationError("此网址短名已被使用。")
        if (
            instance
            and instance.kind == "page"
            and instance.key in ("research", "people", "projects", "news", "publications", "join")
            and slug != instance.key
        ):
            raise ValidationError("基础页面的网址不能修改；可修改标题和正文。")
    if (
        not restoring
        and kind in ("site", "home")
        and ContentItem.objects.filter(kind=kind)
        .exclude(pk=instance.pk if instance else None)
        .exists()
    ):
        raise ValidationError("此配置只能有一条，请修改现有配置。")
    if not restoring and kind == "section" and result.get("component") != "content":
        qs = ContentItem.objects.filter(kind="section", is_deleted=False).exclude(
            pk=instance.pk if instance else None
        )
        if any(item.payload.get("component") == result["component"] for item in qs):
            raise ValidationError("此首页栏目已经存在；可修改显示顺序或恢复原有栏目。")
    if kind == "publication":
        result["year"] = str(result["year"])
        result["conferenceYear"] = str(result.get("conferenceYear") or "")
        publication_date = result.get("publishedDate", "")
        if publication_date and not re.fullmatch(
            r"\d{4}(?:-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?)?", publication_date
        ):
            raise ValidationError("正式发表日期格式应为 YYYY、YYYY-MM 或 YYYY-MM-DD。")
        if len(publication_date) == 10:
            try:
                date.fromisoformat(publication_date)
            except ValueError as error:
                raise ValidationError("正式发表日期不存在，请核对日历日期。") from error
        if publication_date and publication_date[:4] != result["year"]:
            raise ValidationError("展示年份应与正式发表日期一致；会议届别可以另填。")
        if result.get("doi") and not re.fullmatch(r"10\.\d{4,9}/\S+", result["doi"]):
            raise ValidationError("DOI 应以 10. 开头，请勿粘贴完整网址。")
        if result.get("category") == "Granted Patents":
            result["ccfRating"] = ""
            result["track"] = ""
        elif result.get("track"):
            result["ccfRating"] = "unranked"
        if not result.get("venue_key") and not result.get("venueShort"):
            raise ValidationError("请选择会议期刊目录，或填写自定义简称。")
        if (
            not result.get("venue_key")
            and not result.get("ccfRating")
            and result.get("category") != "Granted Patents"
        ):
            result["ccfRating"] = "unranked"
    return result


def validate_upload(upload):
    ext = Path(upload.name).suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico", ".mp4", ".pdf"}
    if ext not in allowed:
        raise ValidationError("仅支持 JPG、PNG、WebP、GIF、ICO、MP4、PDF。")
    if upload.size > 50 * 1024 * 1024:
        raise ValidationError("单文件不能超过 50 MB。视频请先压缩。")
    head = upload.read(32)
    upload.seek(0)
    if ext == ".pdf":
        if not head.startswith(b"%PDF-"):
            raise ValidationError("文件不是有效 PDF。")
    elif ext == ".mp4":
        if b"ftyp" not in head:
            raise ValidationError("文件不是有效 MP4。")
    else:
        try:
            im = Image.open(upload)
            if im.width * im.height > 36_000_000:
                raise ValueError()
            im.verify()
            upload.seek(0)
            if im.format not in ("JPEG", "PNG", "WEBP", "GIF", "ICO"):
                raise ValueError()
        except Exception:
            raise ValidationError("图片已损坏，或格式与扩展名不符。")
    upload.seek(0)
    return mime_for_path(upload.name)


class MediaForm(forms.ModelForm):
    class Meta:
        model = MediaAsset
        fields = ["title", "file", "alt_zh", "alt_en", "credit", "category"]

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if hasattr(upload, "content_type"):
            self.instance.mime_type = validate_upload(upload)
            self.instance.size = upload.size
        return upload
