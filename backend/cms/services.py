# designed by mew
from copy import deepcopy

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .forms import validate_payload
from .models import ContentItem, Revision
from .schema import SCHEMAS

PROTECTED = {
    "site": {"general"},
    "home": {"home"},
    "page": {"research", "people", "projects", "news", "publications", "join"},
}
PUBLIC_ACTIONS = ("发布", "下线", "移入回收站", "从网站备份恢复")


def record_revision(item, user, action):
    Revision.objects.create(
        item=item,
        actor=user,
        action=action,
        snapshot={
            "payload": deepcopy(item.payload),
            "live": deepcopy(item.live),
            "order": item.sort_order,
            "deleted": item.is_deleted,
            "actorName": user.get_full_name() or user.username if user else "系统",
        },
    )


def can_edit(user, item):
    return (
        user.is_active
        and user.is_staff
        and (user.is_superuser or user.has_perm(f"cms.change_{item.kind}"))
    )


def validate_publish(kind, payload):
    for spec in SCHEMAS[kind]:
        if spec["type"] not in ("reference", "references"):
            continue
        keys = payload.get(spec["name"]) or []
        if isinstance(keys, str):
            keys = [keys]
        for key in keys:
            target = ContentItem.objects.filter(
                kind=spec["target"], key=key, is_deleted=False, live__isnull=False
            ).first()
            if not target:
                raise ValidationError(f"{spec['label']}引用的内容尚未发布，请先发布关联条目。")


def live_dependents(item):
    for other in ContentItem.objects.filter(is_deleted=False, live__isnull=False).exclude(
        pk=item.pk
    ):
        for spec in SCHEMAS[other.kind]:
            if spec.get("target") != item.kind:
                continue
            value = other.live["data"].get(spec["name"])
            if value == item.key or (isinstance(value, list) and item.key in value):
                yield str(other)
                break


def publish(item, user):
    if not can_edit(user, item) or not user.has_perm("cms.publish_content"):
        raise PermissionDenied
    if item.is_deleted:
        raise ValidationError("请先从回收站恢复。")
    item.payload = validate_payload(item.kind, item.payload, item)
    validate_publish(item.kind, item.payload)
    old_slug = (item.live or {}).get("data", {}).get("slug")
    if old_slug and old_slug != item.payload.get("slug"):
        item.payload["aliases"] = list(dict.fromkeys(item.payload.get("aliases", []) + [old_slug]))
    item.live = {"data": deepcopy(item.payload), "order": item.sort_order}
    item.published_at = timezone.now()
    item.version += 1
    item.updated_by = user
    item.save()
    record_revision(item, user, "发布")


@transaction.atomic
def editorial_action(pk, user, action, revision_id=None):
    item = ContentItem.objects.select_for_update().get(pk=pk)
    was_published = item.live is not None
    if not can_edit(user, item):
        raise PermissionDenied
    if action == "publish":
        publish(item, user)
        return item
    if action in ("trash", "unpublish"):
        if item.key in PROTECTED.get(item.kind, set()):
            raise ValidationError("基础配置不能下线或删除；请编辑其内容。")
        if not user.has_perm("cms.publish_content"):
            raise PermissionDenied
        dependents = list(live_dependents(item))
        if dependents:
            raise ValidationError(
                "以下已发布内容仍引用此条目，请先解除关联并发布：" + "、".join(dependents[:5])
            )
        item.live = None
        if action == "trash":
            item.is_deleted = True
    elif action == "restore":
        item.is_deleted = False
    elif action == "revision":
        revision = item.revisions.get(pk=revision_id)
        item.payload = deepcopy(revision.snapshot["payload"])
        item.sort_order = revision.snapshot["order"]
        item.is_deleted = False
        # Restoring history creates a draft; it never silently changes the public site.
    else:
        raise ValidationError("未知操作。")
    item.version += 1
    item.updated_by = user
    item.save()
    if was_published and action in ("trash", "unpublish"):
        record_revision(item, user, {"trash": "移入回收站", "unpublish": "下线"}[action])
    return item


def public_site(preview=False):
    result = {
        kind: []
        for kind in (
            "publication",
            "person",
            "group",
            "photo",
            "project",
            "news",
            "direction",
            "venue",
            "page",
            "navigation",
            "section",
            "site",
            "home",
            "text",
        )
    }
    for item in ContentItem.objects.filter(is_deleted=False):
        snap = {"data": item.payload, "order": item.sort_order} if preview else item.live
        if snap is None:
            continue
        result[item.kind].append({"id": item.key, **deepcopy(snap["data"]), "order": snap["order"]})
    for rows in result.values():
        rows.sort(key=lambda x: (x["order"], x["id"]))
    venues = {p["id"]: p for p in result["venue"]}
    for pub in result["publication"]:
        venue = venues.get(pub.get("venue_key"))
        if venue:
            pub["venueShort"] = pub.get("venueShort") or venue["title"]
            pub["venueFull"] = pub.get("venueFull") or venue["full"]
            pub["ccfRating"] = pub.get("ccfRating") or venue["rating"]
            pub["ccfEdition"] = pub.get("ccfEdition") or venue.get("edition", "")
            pub["ccfSource"] = pub.get("ccfSource") or venue.get("source", "")
            pub["ratingNote"] = pub.get("ratingNote") or venue.get("note", "")
        if pub.get("track"):
            pub["ccfRating"] = "unranked"
        if pub.get("category") == "Granted Patents":
            pub["ccfRating"] = ""
        if not preview:
            for field in (
                "auditStatus",
                "auditNotes",
                "checkedAt",
                "verification",
                "venueEvidence",
            ):
                pub.pop(field, None)
    result["news"].sort(key=lambda x: (x.get("date", ""), -x["order"]), reverse=True)
    result["publication"].sort(key=lambda x: (str(x.get("year", "")), -x["order"]), reverse=True)
    return result
