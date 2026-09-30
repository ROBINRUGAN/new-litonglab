# designed by mew
import json

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .editor_api import editor_endpoint
from .forms import MediaForm
from .media_library import MEDIA_CATEGORIES, MIME_BY_SUFFIX, local_media_path, mime_for_path
from .models import ContentItem, MediaAsset
from .services import public_site


@require_GET
def site_data(request):
    preview = request.GET.get("preview") == "1"
    if preview and not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({"error": "预览需要登录后台"}, status=403)
    response = JsonResponse(
        {"schemaVersion": 1, "preview": preview, "content": public_site(preview)},
        json_dumps_params={"ensure_ascii": False},
    )
    response["Cache-Control"] = "no-store"
    return response


def media_references():
    return [
        json.dumps([payload, live], ensure_ascii=False)
        for payload, live in ContentItem.objects.values_list("payload", "live")
    ]


def media_is_used(url, references=None):
    return any(url in row for row in (references if references is not None else media_references()))


def media_item(asset, references=None):
    url = asset.file.url
    bundled = asset.file.name.startswith("original/")
    used = media_is_used(url, references)
    return {
        "id": asset.id,
        "title": asset.title,
        "url": url,
        "sourceUrl": "/" + asset.file.name.removeprefix("original/") if bundled else "",
        "type": mime_for_path(asset.file.name),
        "category": asset.category if asset.category in MEDIA_CATEGORIES else "other",
        "size": asset.size,
        "bundled": bundled,
        "inUse": used,
    }


@editor_endpoint
@require_GET
def media_list(request):
    q = request.GET.get("q", "")[:150]
    page = max(
        1,
        min(
            10000,
            int(request.GET.get("page", "1")) if request.GET.get("page", "1").isdigit() else 1,
        ),
    )
    items = MediaAsset.objects.filter(
        Q(title__icontains=q)
        | Q(file__icontains=q)
        | Q(alt_zh__icontains=q)
        | Q(alt_en__icontains=q)
    )
    media_type = request.GET.get("type")
    if media_type in ("image", "video", "pdf"):
        prefix = "application/pdf" if media_type == "pdf" else media_type + "/"
        suffixes = [suffix for suffix, mime in MIME_BY_SUFFIX.items() if mime.startswith(prefix)]
        file_filter = Q(pk__in=[])
        for suffix in suffixes:
            file_filter |= Q(file__iendswith=suffix)
        items = items.filter(file_filter)
    category = request.GET.get("category")
    if category in MEDIA_CATEGORIES:
        items = items.filter(category=category)
    if category == "group-photo":
        photos = ContentItem.objects.filter(kind="photo", is_deleted=False).order_by(
            "sort_order", "key"
        )
        positions = {}
        for photo in photos:
            if photo.payload.get("show_home") or photo.payload.get("show_people"):
                path = local_media_path(photo.payload.get("image"))
                if path and path not in positions:
                    positions[path] = len(positions)
        if positions:
            items = items.annotate(
                carousel_position=Case(
                    *(When(file=path, then=Value(index)) for path, index in positions.items()),
                    default=Value(len(positions)),
                    output_field=IntegerField(),
                )
            ).order_by("carousel_position", "-id")
    start = (page - 1) * 40
    references = media_references()
    return JsonResponse(
        {
            "items": [media_item(p, references) for p in items[start : start + 40]],
            "more": items.count() > start + 40,
            "page": page,
        }
    )


@editor_endpoint
@require_POST
def media_upload(request):
    if not request.user.has_perm("cms.add_mediaasset"):
        raise PermissionDenied
    file = request.FILES.get("file")
    category = request.POST.get("category") or "other"
    if category not in MEDIA_CATEGORIES:
        raise ValidationError("请选择有效的素材分类。")
    form = MediaForm(
        {
            "title": request.POST.get("title") or (file.name if file else ""),
            "category": category,
        },
        request.FILES,
    )
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    obj = form.save(commit=False)
    obj.uploaded_by = request.user
    obj.save()
    return JsonResponse(media_item(obj), status=201)


@editor_endpoint
@require_http_methods(["PATCH", "DELETE"])
def media_detail(request, asset_id):
    asset = MediaAsset.objects.filter(pk=asset_id).first()
    if asset is None:
        raise Http404
    if request.method == "PATCH":
        if not request.user.has_perm("cms.change_mediaasset"):
            raise PermissionDenied
        try:
            data = json.loads(request.body)
        except (ValueError, UnicodeError) as error:
            raise ValidationError("素材名称无效。") from error
        if not isinstance(data, dict) or not set(data).intersection({"title", "category"}):
            raise ValidationError("请选择要修改的素材信息。")
        updates = []
        if "title" in data:
            title = data["title"]
            if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
                raise ValidationError("素材名称应为 1–200 个字符。")
            asset.title = title.strip()
            updates.append("title")
        if "category" in data:
            if not isinstance(data["category"], str) or data["category"] not in MEDIA_CATEGORIES:
                raise ValidationError("请选择有效的素材分类。")
            asset.category = data["category"]
            updates.append("category")
        asset.save(update_fields=updates)
        return JsonResponse(media_item(asset))
    if not request.user.has_perm("cms.delete_mediaasset"):
        raise PermissionDenied
    if asset.file.name.startswith("original/"):
        raise ValidationError("随网站发布的内置素材不能删除。")
    if media_is_used(asset.file.url):
        raise ValidationError("素材正在被草稿或官网使用，请先替换引用并发布。")
    storage, name = asset.file.storage, asset.file.name
    asset.delete()
    storage.delete(name)
    return HttpResponse(status=204)


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
@xframe_options_sameorigin
def frontend(request, path=""):
    root = settings.FRONTEND_DIR.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise Http404
    if target.is_file():
        return FileResponse(target.open("rb"))
    shell = root / "index.html"
    if not shell.exists():
        return HttpResponse("请先运行 npm run build 构建官网。", status=503)
    return FileResponse(shell.open("rb"), content_type="text/html")
