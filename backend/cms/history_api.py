# designed by mew
"""Cross-record, persisted editorial history for authorized website editors."""

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .editor_api import EDITABLE_KINDS, SINGLETON_KEYS, editor_endpoint
from .models import KINDS, Revision
from .schema import SCHEMAS
from .services import PUBLIC_ACTIONS

PAGE_SIZE = 20


def actor_name(revision):
    return revision.snapshot.get("actorName") or (
        revision.actor.get_full_name() or revision.actor.username if revision.actor else "系统"
    )


def title(data, fallback):
    return str(
        next(
            (
                data.get(key)
                for key in ("title_zh", "name_zh", "title", "title_en", "name_en")
                if data.get(key)
            ),
            fallback,
        )
    )


def state(snapshot):
    if snapshot.get("deleted"):
        return "回收站"
    live = snapshot.get("live")
    if live is None:
        return "草稿 / 未上线"
    return "已发布"


def changes(revision, previous):
    current = revision.snapshot
    baseline = previous.snapshot if previous else {}
    before = (baseline.get("live") or {}).get("data", {})
    after = (current.get("live") or {}).get("data", {})
    before_order = (baseline.get("live") or {}).get("order")
    after_order = (current.get("live") or {}).get("order")
    result = [
        {
            "field": field["name"],
            "label": field["label"],
            "before": before.get(field["name"]),
            "after": after.get(field["name"]),
        }
        for field in SCHEMAS[revision.item.kind]
        if before.get(field["name"]) != after.get(field["name"])
    ]
    if before_order != after_order:
        result.append(
            {"field": "$order", "label": "排列位置", "before": before_order, "after": after_order}
        )
    if baseline.get("deleted", False) != current.get("deleted", False):
        result.append(
            {
                "field": "$deleted",
                "label": "回收站状态",
                "before": baseline.get("deleted", False),
                "after": current.get("deleted", False),
            }
        )
    if not previous or state(baseline) != state(current):
        result.append(
            {
                "field": "$state",
                "label": "发布状态",
                "before": state(baseline) if previous else "尚未创建",
                "after": state(current),
            }
        )
    return result


@require_GET
@editor_endpoint
def history(request):
    kinds = [
        (kind, label)
        for kind, label in KINDS
        if kind in EDITABLE_KINDS and request.user.has_perm(f"cms.change_{kind}")
    ]
    allowed = {kind for kind, _ in kinds}
    queryset = (
        Revision.objects.filter(item__kind__in=allowed, action__in=PUBLIC_ACTIONS)
        .exclude(action="从网站备份恢复", snapshot__live=None)
        .select_related("item", "actor")
        .order_by("-pk")
    )
    for singleton_kind, key in SINGLETON_KEYS.items():
        queryset = queryset.exclude(Q(item__kind=singleton_kind) & ~Q(item__key=key))
    kind = request.GET.get("kind", "")
    if kind:
        queryset = queryset.filter(item__kind=kind) if kind in allowed else queryset.none()
    query = request.GET.get("q", "").strip()[:150]
    if query:
        match = Q(item__key__icontains=query) | Q(action__icontains=query)
        for field in ("title_zh", "name_zh", "title", "title_en", "name_en"):
            match |= Q(**{f"snapshot__payload__{field}__icontains": query})
        queryset = queryset.filter(match)
    actor = request.GET.get("actor", "").strip()[:150]
    if actor:
        queryset = queryset.filter(
            Q(snapshot__actorName__icontains=actor)
            | Q(actor__username__icontains=actor)
            | Q(actor__first_name__icontains=actor)
            | Q(actor__last_name__icontains=actor)
        )
    page_value = request.GET.get("page", "1")
    try:
        page = max(1, min(10000, int(page_value))) if len(page_value) <= 8 else 1
    except ValueError:
        page = 1
    start = (page - 1) * PAGE_SIZE
    revisions = list(queryset[start : start + PAGE_SIZE + 1])
    items = []
    for revision in revisions[:PAGE_SIZE]:
        previous = (
            Revision.objects.filter(
                item_id=revision.item_id,
                pk__lt=revision.pk,
                action__in=(*PUBLIC_ACTIONS, "初始内容迁入", "补入论文摘要和配图"),
            )
            .order_by("-pk")
            .first()
        )
        items.append(
            {
                "id": revision.pk,
                "kind": revision.item.kind,
                "key": revision.item.key,
                "title": title(revision.snapshot.get("payload", {}), revision.item.key),
                "action": revision.action,
                "actor": actor_name(revision),
                "created": revision.created_at.isoformat(),
                "changes": changes(revision, previous),
                "canLocate": not revision.item.is_deleted,
            }
        )
    return JsonResponse(
        {
            "items": items,
            "page": page,
            "hasMore": len(revisions) > PAGE_SIZE,
            "pageSize": PAGE_SIZE,
            "kinds": [{"key": kind, "label": label} for kind, label in kinds],
        }
    )
