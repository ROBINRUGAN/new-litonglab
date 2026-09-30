# designed by mew
"""Media types and display names shared by upload, seed and library sync."""

import re
from pathlib import Path
from urllib.parse import urlsplit

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".pdf": "application/pdf",
}

MEDIA_CATEGORIES = {
    "group-photo": "合照照片",
    "person-photo": "个人照片",
    "paper-figure": "论文配图",
    "project-figure": "项目配图",
    "other": "其他素材",
}

CONTENT_IMAGE_CATEGORIES = {
    "photo": "group-photo",
    "person": "person-photo",
    "publication": "paper-figure",
    "project": "project-figure",
}

STATIC_TITLES = {
    "assets/campus-hero.jpg": "中国人民大学校园 · 首页背景",
    "assets/campus-gate.jpg": "中国人民大学校园 · 校门",
    "assets/campus-film.mp4": "中国人民大学校园 · 首页视频",
    "assets/protocols.webp": "研究方向 · 传输协议",
    "assets/systems.webp": "研究方向 · 网络系统",
    "assets/intelligence.webp": "研究方向 · 网络智能",
    "assets/favicon.ico": "LitongLab 网站图标",
    "icons/litonglab-logo-long.png": "LitongLab 标志",
    "images/paper-placeholder.svg": "论文配图占位图",
    "images/person-placeholder.svg": "灰色头像占位图",
}

ARCHITECTURE_CAPTION = re.compile(
    r"architecture|framework|overview|workflow|system|scheme|model|架构|框架|系统|流程",
    re.IGNORECASE,
)


def mime_for_path(path):
    return MIME_BY_SUFFIX.get(Path(path).suffix.lower(), "application/octet-stream")


def local_media_path(url):
    if not isinstance(url, str):
        return None
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return None
    if parsed.path.startswith("/media/"):
        return parsed.path.removeprefix("/media/")
    return "original/" + parsed.path.lstrip("/")


def default_media_category(path):
    relative = str(path).removeprefix("original/")
    if relative.startswith("images/group_photo_"):
        return "group-photo"
    if relative in (
        "images/litong-portrait.webp",
        "images/person-placeholder.svg",
    ) or relative.startswith("images/people/"):
        return "person-photo"
    if relative == "images/paper-placeholder.svg" or relative.startswith("images/papers/"):
        return "paper-figure"
    if relative.startswith("images/project_"):
        return "project-figure"
    return "other"


def referenced_media_categories(items):
    categories = {}
    for item in items:
        category = CONTENT_IMAGE_CATEGORIES.get(item.kind)
        if not category:
            continue
        path = local_media_path(item.payload.get("image"))
        if path:
            categories[path] = category
    return categories


def media_titles(items):
    """Return names based on current editorial references, without touching files."""
    titles = {"original/" + path: title for path, title in STATIC_TITLES.items()}
    for item in items:
        data = item.payload
        if item.kind == "publication":
            paper = str(data.get("title") or "").strip()
            if not paper:
                continue
            image = data.get("image")
            if isinstance(image, str) and "placeholder" not in image:
                caption = str(data.get("imageCaption_en") or data.get("imageCaption_zh") or "")
                label = "架构图" if ARCHITECTURE_CAPTION.search(caption) else "论文配图"
                path = local_media_path(image)
                if path:
                    titles[path] = f"【{label}】{paper}"
            for link in data.get("links", []):
                if not isinstance(link, dict):
                    continue
                path = local_media_path(link.get("url"))
                if path and Path(path).suffix.lower() == ".pdf":
                    titles[path] = paper
            continue
        image = data.get("image")
        path = local_media_path(image)
        if not path or "placeholder" in path:
            continue
        if item.kind == "photo":
            title = data.get("title_zh") or data.get("title_en")
            label = "团队合照"
        elif item.kind == "project":
            title = data.get("name_zh") or data.get("name_en")
            label = "项目配图"
        elif item.kind == "person":
            title = data.get("name_zh") or data.get("name_en")
            label = "成员照片"
        else:
            continue
        if title:
            titles[path] = f"【{label}】{title}"
    for number in range(2, 7):
        titles.setdefault(
            f"original/images/project_transhub{number:02d}.webp",
            f"【项目配图】Transhub · {number}",
        )
    return titles
