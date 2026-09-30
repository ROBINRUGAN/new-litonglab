# designed by mew
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from .schema import payload_differs


def new_key():
    return uuid.uuid4().hex


KINDS = [
    ("publication", "论文与专利"),
    ("person", "成员与校友"),
    ("group", "成员分组"),
    ("photo", "照片与相册"),
    ("project", "研究项目"),
    ("news", "新闻动态"),
    ("direction", "研究方向"),
    ("venue", "会议期刊目录"),
    ("page", "页面内容"),
    ("navigation", "导航与页脚链接"),
    ("section", "首页栏目编排"),
    ("site", "站点与联系信息"),
    ("home", "首页与轮播设置"),
    ("text", "界面中英文文案"),
]


class ContentItem(models.Model):
    kind = models.CharField("内容类型", max_length=24, choices=KINDS, db_index=True)
    key = models.CharField("稳定编号", max_length=100, default=new_key)
    payload = models.JSONField("编辑稿", default=dict)
    live = models.JSONField("已发布快照", null=True, blank=True)
    sort_order = models.IntegerField(
        "显示顺序", default=100, help_text="数字越小越靠前；新闻和论文先按日期/年份排列。"
    )
    version = models.PositiveIntegerField(default=1)
    is_deleted = models.BooleanField("在回收站", default=False)
    updated_at = models.DateTimeField("最后修改", auto_now=True)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["sort_order", "-updated_at"]
        constraints = [models.UniqueConstraint(fields=["kind", "key"], name="unique_content_key")]
        permissions = [
            ("publish_content", "发布、下线和回收内容"),
            ("import_content", "导入内容备份"),
        ]
        verbose_name = "内容条目"
        verbose_name_plural = "全部内容"

    def __str__(self):
        return str(
            self.payload.get("title_zh")
            or self.payload.get("name_zh")
            or self.payload.get("title")
            or self.payload.get("title_en")
            or self.payload.get("name_en")
            or self.payload.get("source")
            or self.key
        )[:100]

    @property
    def state(self):
        if self.is_deleted:
            return "回收站"
        if self.live is None:
            return "草稿 / 未上线"
        if (
            payload_differs(self.kind, self.live["data"], self.payload)
            or self.live.get("order") != self.sort_order
        ):
            return "已发布 · 有新草稿"
        return "已发布"


class Revision(models.Model):
    item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name="revisions")
    snapshot = models.JSONField()
    action = models.CharField(max_length=50)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


def media_path(instance, filename):
    return f"uploads/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class MediaAsset(models.Model):
    title = models.CharField("素材名称", max_length=200)
    file = models.FileField("上传文件", upload_to=media_path)
    alt_zh = models.CharField("图片说明（中文）", max_length=300, blank=True)
    alt_en = models.CharField("图片说明（英文）", max_length=300, blank=True)
    credit = models.CharField("来源 / 摄影者", max_length=300, blank=True)
    category = models.CharField("分类", max_length=100, blank=True)
    mime_type = models.CharField(max_length=100, editable=False)
    size = models.PositiveBigIntegerField(default=0, editable=False)
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, editable=False
    )

    class Meta:
        ordering = ["-id"]
        verbose_name = "素材"
        verbose_name_plural = "素材库"

    def __str__(self):
        return self.title


# Proxy models retain per-content-type permissions for the visual editor.
PROXIES = {}
for kind, label in KINDS:
    meta = type("Meta", (), {"proxy": True, "verbose_name": label, "verbose_name_plural": label})
    proxy = type(
        "".join(part.title() for part in kind.split("_")),
        (ContentItem,),
        {"__module__": __name__, "Meta": meta, "content_kind": kind},
    )
    globals()[proxy.__name__] = proxy
    PROXIES[kind] = proxy
