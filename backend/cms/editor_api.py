# designed by mew
"""Authenticated, versioned editing for the website's own Vue canvas."""

import json
import re
from copy import deepcopy
from functools import wraps

from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .forms import validate_payload
from .models import KINDS, ContentItem
from .schema import SCHEMAS, payload_differs
from .services import (
    can_edit,
    editorial_action,
    public_site,
    publish,
    validate_publish,
)

EDITABLE_KINDS = {
    "publication",
    "news",
    "person",
    "project",
    "photo",
    "group",
    "venue",
    "direction",
    "home",
    "page",
    "site",
}
SINGLETON_KEYS = {"home": "home", "page": "join", "site": "general"}
EDITOR_FIELDS = {
    "home": {"featured_projects", "featured_publications", "carousel_seconds", "join_image"},
    "page": {
        "title_zh",
        "title_en",
        "description_zh",
        "description_en",
        "body_zh",
        "body_en",
        "image",
    },
    "site": {"email", "address_zh", "address_en"},
}


def editable_fields(kind):
    return [
        field
        for field in SCHEMAS[kind]
        if kind not in EDITOR_FIELDS or field["name"] in EDITOR_FIELDS[kind]
    ]


def editable_items(allowed):
    return [
        item
        for item in ContentItem.objects.filter(kind__in=allowed)
        if item.kind not in SINGLETON_KEYS or item.key == SINGLETON_KEYS[item.kind]
    ]


class EditConflict(Exception):
    pass


def body(request):
    if len(request.body) > 5 * 1024 * 1024:
        raise ValidationError("一次保存的内容过大，请分批保存。")
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeError) as error:
        raise ValidationError("请求格式无效。") from error
    if not isinstance(data, dict):
        raise ValidationError("请求格式无效。")
    return data


def errors(error):
    messages = []
    for message in error.messages:
        try:
            fields = json.loads(message)
            messages.extend(
                f"{key}: {entry['message']}" for key, entries in fields.items() for entry in entries
            )
        except (ValueError, TypeError, AttributeError):
            messages.append(message)
    return messages


def editor_endpoint(function):
    @wraps(function)
    @never_cache
    def wrapped(request, *args, **kwargs):
        if (
            not request.user.is_authenticated
            or not request.user.is_active
            or not request.user.is_staff
        ):
            return JsonResponse({"errors": ["请登录编辑账号。"]}, status=403)
        try:
            return function(request, *args, **kwargs)
        except PermissionDenied:
            return JsonResponse({"errors": ["该账号没有此操作的权限。"]}, status=403)
        except ContentItem.DoesNotExist:
            return JsonResponse({"errors": ["条目不存在，请重新加载。"]}, status=404)
        except EditConflict as error:
            return JsonResponse({"errors": [str(error)]}, status=409)
        except ValidationError as error:
            return JsonResponse({"errors": errors(error)}, status=400)

    return wrapped


def serialize(item):
    return {
        "id": item.key,
        "kind": item.kind,
        "version": item.version,
        "order": item.sort_order,
        "data": item.payload,
        "deleted": item.is_deleted,
        "state": item.state,
        "published": item.live is not None,
        "liveData": deepcopy(item.live["data"]) if item.live else None,
        "liveOrder": item.live.get("order") if item.live else None,
        "hasDraft": item.live is None
        or payload_differs(item.kind, item.live["data"], item.payload)
        or item.live.get("order") != item.sort_order,
    }


def snapshot(user):
    kinds = [
        (kind, label)
        for kind, label in KINDS
        if kind in EDITABLE_KINDS and user.has_perm(f"cms.change_{kind}")
    ]
    allowed = {kind for kind, _ in kinds}
    return {
        "user": {
            "name": user.get_full_name() or user.username,
            "manager": user.is_superuser,
            "canPublish": user.has_perm("cms.publish_content"),
        },
        "kinds": [
            {
                "key": kind,
                "label": label,
                "canAdd": kind not in SINGLETON_KEYS and user.has_perm(f"cms.add_{kind}"),
            }
            for kind, label in kinds
        ],
        "schemas": {kind: editable_fields(kind) for kind in allowed},
        "records": [serialize(item) for item in editable_items(allowed)],
        "content": public_site(True),
    }


@require_GET
@never_cache
def session(request):
    token = get_token(request)
    if not (request.user.is_authenticated and request.user.is_active and request.user.is_staff):
        return JsonResponse({"user": None, "csrfToken": token})
    return JsonResponse({**snapshot(request.user), "csrfToken": token})


@require_POST
@never_cache
def sign_in(request):
    try:
        data = body(request)
    except ValidationError as error:
        return JsonResponse({"errors": errors(error)}, status=400)
    form = AuthenticationForm(request, data=data)
    if not form.is_valid():
        return JsonResponse(
            {
                "errors": [
                    "用户名或密码不正确，或账号暂时被锁定。请重试；连续失败请 15 分钟后再试。"
                ]
            },
            status=400,
        )
    user = form.get_user()
    if not user.is_staff:
        return JsonResponse({"errors": ["此账号没有网站编辑权限。"]}, status=403)
    login(request, user)
    return JsonResponse({**snapshot(user), "csrfToken": get_token(request)})


@require_POST
@editor_endpoint
def sign_out(request):
    logout(request)
    return JsonResponse({"user": None, "csrfToken": get_token(request)})


@require_POST
@editor_endpoint
def save_changes(request):
    data = body(request)
    rows = data.get("items")
    action = data.get("action")
    if action not in ("draft", "publish") or not isinstance(rows, list) or not 0 < len(rows) <= 100:
        raise ValidationError("请选择 1–100 条需要保存的内容。")
    if action == "publish" and not request.user.has_perm("cms.publish_content"):
        raise PermissionDenied
    with transaction.atomic():
        incoming, seen, staged = {}, set(), []
        for row in rows:
            if not isinstance(row, dict):
                raise ValidationError("内容格式无效。")
            kind, key = row.get("kind"), row.get("id")
            if (
                not isinstance(kind, str)
                or kind not in EDITABLE_KINDS
                or not isinstance(key, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", key)
            ):
                raise ValidationError("内容类型或编号无效。")
            if (kind, key) in seen:
                raise ValidationError("保存列表包含重复条目。")
            seen.add((kind, key))
            incoming.setdefault(kind, []).append(key)
            item = ContentItem.objects.select_for_update().filter(kind=kind, key=key).first()
            if kind in SINGLETON_KEYS and (key != SINGLETON_KEYS[kind] or not item):
                raise PermissionDenied
            permission = "change" if item else "add"
            if not request.user.has_perm(f"cms.{permission}_{kind}"):
                raise PermissionDenied
            if row.get("version") != (item.version if item else None):
                raise EditConflict(
                    "有条目已被其他人更新。本次未保存，请保留当前修改并重新加载最新版本。"
                )
            if item and item.is_deleted:
                raise ValidationError("请先从回收站恢复该条目。")
            if not isinstance(row.get("data"), dict):
                raise ValidationError("条目字段无效。")
            if kind in EDITOR_FIELDS and any(
                field["name"] not in EDITOR_FIELDS[kind]
                and field["name"] in row["data"]
                and row["data"][field["name"]] != item.payload.get(field["name"])
                for field in SCHEMAS[kind]
            ):
                raise ValidationError("此页面的固定文案不属于日常维护范围。")
            order = row.get("order", 100)
            if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= 100000:
                raise ValidationError("显示顺序应为 0–100000 的整数。")
            staged.append((item or ContentItem(kind=kind, key=key), row))
        for item, row in staged:
            # Internal IDs, aliases and state cannot be written via payload fields.
            payload = {
                **item.payload,
                **{
                    field["name"]: row["data"].get(field["name"], field.get("default", ""))
                    for field in editable_fields(item.kind)
                },
            }
            item.payload = validate_payload(item.kind, payload, item, incoming)
            item.sort_order = row.get("order", 100)
            item.updated_by = request.user
            item.version += 1
            item.save()
        if action == "publish":
            pending = [item for item, _ in staged]
            while pending:
                ready = []
                last_error = None
                for item in pending:
                    try:
                        validate_publish(item.kind, item.payload)
                    except ValidationError as error:
                        last_error = error
                        continue
                    publish(item, request.user)
                    ready.append(item)
                if not ready:
                    raise last_error or ValidationError("关联内容无法发布。")
                pending = [item for item in pending if item not in ready]
    return JsonResponse(snapshot(request.user))


@require_POST
@editor_endpoint
def item_action(request, kind, key):
    if kind not in EDITABLE_KINDS or kind in SINGLETON_KEYS:
        raise PermissionDenied
    data = body(request)
    with transaction.atomic():
        item = ContentItem.objects.select_for_update().get(kind=kind, key=key)
        if not can_edit(request.user, item):
            raise PermissionDenied
        if data.get("version") != item.version:
            raise EditConflict("条目已更新，请重新加载后操作。")
        if data.get("action") not in ("trash", "restore", "unpublish", "revision"):
            raise ValidationError("操作无效。")
        revision = data.get("revision")
        if data["action"] == "revision" and (
            not isinstance(revision, int) or not item.revisions.filter(pk=revision).exists()
        ):
            raise ValidationError("历史版本不存在。")
        editorial_action(item.pk, request.user, data["action"], revision)
    return JsonResponse(snapshot(request.user))


@require_GET
@editor_endpoint
def history(request, kind, key):
    if kind not in EDITABLE_KINDS or (kind in SINGLETON_KEYS and key != SINGLETON_KEYS[kind]):
        raise PermissionDenied
    item = ContentItem.objects.get(kind=kind, key=key)
    if not can_edit(request.user, item):
        raise PermissionDenied
    return JsonResponse(
        {
            "versions": [
                {
                    "id": r.pk,
                    "action": r.action,
                    "date": r.created_at.isoformat(),
                    "actor": r.snapshot.get("actorName")
                    or (r.actor.get_full_name() or r.actor.username if r.actor else "系统"),
                    "data": deepcopy(r.snapshot["payload"]),
                }
                for r in item.revisions.filter(action__in=("发布", "初始内容迁入")).select_related(
                    "actor"
                )[:50]
            ]
        }
    )
