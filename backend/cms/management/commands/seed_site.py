# designed by mew
"""One-time, idempotent migration of the reviewed laboratory content."""

import hashlib
import html
import json
import shutil
from copy import deepcopy
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cms.forms import clean_rich, validate_payload
from cms.media_library import mime_for_path
from cms.models import KINDS, ContentItem, MediaAsset
from cms.schema import SCHEMAS
from cms.services import record_revision


class Command(BaseCommand):
    help = "初始化官网内容及编辑人员权限；已有条目不会被覆盖。"

    @transaction.atomic
    def handle(self, *args, **options):
        seed = settings.BASE_DIR / "content" / "seed"
        original = json.loads((seed / "site.json").read_text())
        for kind in ("publications", "people", "photos", "projects", "news"):
            original[kind] = json.loads((seed / f"{kind}.json").read_text())
        locales = json.loads((seed / "translations.json").read_text())
        interface = json.loads((seed / "interface.json").read_text())
        created_count = 0

        def translated(text, lang):
            return interface[lang].get(text, text)

        def bilingual(name, text):
            return {f"{name}_{lang}": translated(text, lang) for lang in ("en", "zh")}

        def paragraph(value):
            return "<p>" + html.escape(value).replace("\n", "<br>") + "</p>"

        def add(kind, key, data, order=100):
            nonlocal created_count
            if ContentItem.objects.filter(kind=kind, key=key).exists():
                return
            defaults = {
                s["name"]: s.get(
                    "default",
                    False
                    if s["type"] == "boolean"
                    else []
                    if s["type"] in ("links", "references")
                    else "",
                )
                for s in SCHEMAS[kind]
            }
            item = ContentItem(kind=kind, key=key, payload={**defaults, **data}, sort_order=order)
            item.payload = validate_payload(kind, item.payload, item)
            item.live = {"data": deepcopy(item.payload), "order": order}
            item.published_at = timezone.now()
            item.save()
            record_revision(item, None, "初始内容迁入")
            created_count += 1

        venues = {}
        for paper in original["publications"]:
            short = paper["venueShort"]
            if short not in venues or paper.get("ccfRating") in ("A", "B", "C"):
                venues[short] = paper
        venue_keys = {}
        for i, (short, paper) in enumerate(venues.items()):
            key = "venue-" + hashlib.sha256(short.encode()).hexdigest()[:16]
            venue_keys[short] = key
            add(
                "venue",
                key,
                {
                    "title": short,
                    "full": paper.get("venueFull") or short,
                    "rating": paper.get("ccfRating") or "unranked",
                    "edition": paper.get("ccfEdition", ""),
                    "source": paper.get("ccfSource", ""),
                    "note": paper.get("ratingNote", ""),
                },
                i * 10,
            )
        for i, paper in enumerate(original["publications"]):
            data = deepcopy(paper)
            data.pop("id")
            data["venue_key"] = venue_keys[paper["venueShort"]]
            data["source"] = (
                paper.get("source") or (paper.get("venueEvidence") or [original["source"]])[0]
            )
            add("publication", paper["id"], data, i * 10)

        group_keys = {
            "Principal investigator": "faculty",
            "PhD Students": "phd",
            "Master Students": "masters",
            "Alumni": "alumni",
        }
        for i, (title, key) in enumerate(group_keys.items()):
            add(
                "group",
                key,
                {**bilingual("title", title), "layout": "faculty" if key == "faculty" else "cards"},
                i * 10,
            )
        add(
            "person",
            "tong-li",
            {
                "name_en": "Tong Li",
                "name_zh": "李彤",
                "group": "faculty",
                **bilingual("role", "Full Professor · Renmin University of China"),
                "bio_en": "<p>Ph.D. from Tsinghua University. Previously Chief Engineer at Huawei.</p><p>DEKE Lab · Information School<br>Renmin University of China</p>",
                "bio_zh": "<p>清华大学博士，曾任华为首席工程师。</p><p>中国人民大学信息学院 · 数据工程与知识工程教育部重点实验室</p>",
                "image": "/images/litong-portrait.webp",
                "links": [
                    {"label": "Homepage", "url": "http://iir.ruc.edu.cn/~litong"},
                    {"label": "Email", "url": "mailto:tong.li@ruc.edu.cn"},
                ],
            },
            0,
        )
        for i, person in enumerate(original["people"]):
            key = person["name"].lower().replace(" ", "-")
            add(
                "person",
                key,
                {
                    "name_en": person["name"],
                    "name_zh": person["chinese"],
                    "group": group_keys[person["group"]],
                    "image": person["image"],
                    "placeholder": person.get("placeholder", False),
                    **{
                        f"bio_{lang}": paragraph(locales["people"][person["name"]][lang])
                        for lang in ("en", "zh")
                    },
                },
                (i + 1) * 10,
            )
        for i, photo in enumerate(original["photos"]):
            year, season = photo["title"].split()
            add(
                "photo",
                "cohort-" + photo["title"].lower().replace(" ", "-"),
                {
                    "title_en": photo["title"],
                    "title_zh": f"{year} 年" + ("春季" if season == "Spring" else "秋季"),
                    "image": photo["image"],
                    "show_home": True,
                    "show_people": True,
                },
                i * 10,
            )
        for i, project in enumerate(original["projects"]):
            add(
                "project",
                project["slug"],
                {
                    "slug": project["slug"],
                    **bilingual("name", project["name"]),
                    **bilingual("category", project["category"]),
                    **bilingual("summary", project["summary"]),
                    **{
                        f"body_{lang}": clean_rich(locales["projects"][project["slug"]][lang])
                        for lang in ("en", "zh")
                    },
                    "image": project["image"],
                    "links": project["links"],
                    "publications": project.get("publications", []),
                },
                i * 10,
            )
        for i, news in enumerate(original["news"]):
            add(
                "news",
                "news-" + news["date"] + "-" + str(i),
                {
                    "date": news["date"],
                    "category": news["category"],
                    "links": news["links"],
                    **{
                        f"title_{lang}": locales["news"][news["text"]][lang]
                        for lang in ("en", "zh")
                    },
                },
                i * 10,
            )
        directions = [
            (
                "network",
                "Network protocols",
                "protocols",
                "Congestion control, wireless transport, and wide-area loss recovery.",
                ["tack", "art"],
                ["Forewarned", "PRED"],
            ),
            (
                "systems",
                "Networked systems",
                "systems",
                "Reliable communication across devices, datacenters, and distributed databases.",
                ["blender", "find"],
                ["Performant Synchronization", "GeoLM"],
            ),
            (
                "ai",
                "Machine learning & networks",
                "intelligence",
                "Machine learning for networked systems and efficient computing infrastructure.",
                [],
                ["FENIX", "Pegasus", "TrafficFormer", "MemFerry"],
            ),
        ]
        for i, (key, title, image, description, projects, terms) in enumerate(directions):
            papers = [
                next((p["id"] for p in original["publications"] if term in p["title"]), "")
                for term in terms
            ]
            add(
                "direction",
                key,
                {
                    **bilingual("title", title),
                    **bilingual("description", description),
                    "image": "/assets/" + image + ".webp",
                    "projects": projects,
                    "publications": [p for p in papers if p],
                },
                i * 10,
            )
        pages = [
            (
                "research",
                "Research",
                "Computer networks, distributed systems, and machine learning.",
            ),
            ("publications", "Publications", "Our research in papers, systems, and ideas."),
            ("projects", "Projects", "From research ideas to working systems."),
            ("people", "Our people", "LitongLab · Renmin University of China"),
            ("news", "News", "The latest from LitongLab."),
            (
                "join",
                "Join us",
                "We’re looking for self-motivated students to work with us at RUC.",
            ),
        ]
        join_paragraphs = [
            "如果你有志解决业界真实的问题，做实用而有趣的研究，发表高水平文章，欢迎加入研究小组。",
            "只要自驱动力强，不惧零基础，同时优秀学生将获得大厂实习、独家内推机会。",
            "Please feel free to drop us an email with your CV. Also, feel free to contact us if you are interested in internship opportunities in our group.",
            "免试推荐的研究生需大三下参加中国人民大学信息学院夏令营选拔。",
        ]
        for i, (key, title, description) in enumerate(pages):
            data = {
                "slug": key,
                **bilingual("title", title),
                **bilingual("description", description),
            }
            if key == "news":
                data["image"] = "/assets/campus-gate.jpg"
            if key == "join":
                data["image"] = original["photos"][2]["image"]
                data.update(
                    {
                        f"body_{lang}": "<h2>"
                        + translated("Research opportunities", lang)
                        + "</h2>"
                        + "".join(paragraph(translated(p, lang)) for p in join_paragraphs)
                        for lang in ("en", "zh")
                    }
                )
            add("page", key, data, i * 10)
        for i, (key, title) in enumerate(
            [("home", "Home")] + [(k, "People" if k == "people" else t) for k, t, _ in pages]
        ):
            add(
                "navigation",
                key,
                {
                    **bilingual("title", title),
                    "url": "/" if key == "home" else "/" + key + "/",
                    "header": True,
                    "footer": key != "home",
                    "highlight": key == "join",
                },
                i * 10,
            )
        for i, key in enumerate(
            ["hero", "research", "projects", "publications", "people", "news", "join"]
        ):
            add("section", key, {"component": key}, i * 10)
        add(
            "site",
            "general",
            {
                "name_en": "LitongLab",
                "name_zh": "LitongLab",
                "logo": "/icons/litonglab-logo-long.png",
                "favicon": "/assets/favicon.ico",
                "email": "tong.li@ruc.edu.cn",
                "address_en": "Room 421, Information Building\nRenmin University of China\nNo. 59 Zhongguancun Street\nBeijing, China 100872",
                "address_zh": "北京市海淀区中关村大街 59 号\n中国人民大学 · 信息楼 421 室",
                "footer_en": "<p>Computer Networking Research Group<br>Renmin University of China</p>",
                "footer_zh": "<p>计算机网络研究小组<br>中国人民大学</p>",
                "university_url": "https://www.ruc.edu.cn/",
                **bilingual("university", "Renmin University of China"),
                "default_language": "en",
                "default_theme": "light",
                "enable_theme": True,
                **bilingual(
                    "seoDescription",
                    "Computer networks, distributed systems, and machine learning.",
                ),
            },
            0,
        )
        add(
            "home",
            "home",
            {
                "title_en": "Computer Networking\n& Intelligent Systems",
                "title_zh": "计算机网络\n与智能系统",
                **bilingual(
                    "description",
                    "LitongLab is a computer networking research group of Renmin University of China. We apply big data and machine learning technologies to improve the performance of networked systems.",
                ),
                "eyebrow_en": "RENMIN UNIVERSITY OF CHINA",
                "eyebrow_zh": "中国人民大学",
                "video": "/assets/campus-film.mp4",
                "poster": "/assets/campus-hero.jpg",
                "overlay": 100,
                "featured_projects": ["tack", "art", "transhub"],
                "featured_publications": ["pub-1", "pub-4", "pub-6"],
                "news_limit": 4,
                "carousel_seconds": 6,
                "join_image": original["photos"][1]["image"],
                **bilingual("join_title", "Join LitongLab"),
                **bilingual(
                    "join_description",
                    "We’re looking for self-motivated students to work with us at RUC.",
                ),
            },
            0,
        )
        for i, source in enumerate(sorted(set(interface["en"]) | set(interface["zh"]))):
            add(
                "text",
                "text-" + hashlib.sha256(source.encode()).hexdigest()[:24],
                {
                    "source": source,
                    **{f"value_{lang}": translated(source, lang) for lang in ("en", "zh")},
                },
                i * 10,
            )
        editor_group, _ = Group.objects.get_or_create(name="编辑人员")
        codes = [f"{action}_{kind}" for kind, _ in KINDS for action in ("add", "change", "view")]
        codes += [
            "add_mediaasset",
            "change_mediaasset",
            "delete_mediaasset",
            "view_mediaasset",
            "publish_content",
        ]
        editor_group.permissions.set(
            Permission.objects.filter(content_type__app_label="cms", codename__in=codes)
        )
        public = settings.BASE_DIR / "frontend" / "public"
        if not public.exists():
            public = settings.FRONTEND_DIR
        credits = {
            "/assets/campus-hero.jpg": "https://www.ruc.edu.cn/template/1/out/imgs/zgc-img4.jpg",
            "/assets/campus-gate.jpg": "https://www.ruc.edu.cn/template/1/out/imgs/zgc-img10.jpg",
            "/assets/campus-film.mp4": "校园照片与实验室合影剪辑",
            **{
                f"/assets/{name}.webp": "实验室网站研究方向插图"
                for name in ("protocols", "systems", "intelligence")
            },
            **{
                person["image"]: person["imageSource"]
                for person in original["people"]
                if person.get("imageSource")
            },
            **{
                link["url"].split("#")[0]: paper["source"]
                for paper in original["publications"]
                for link in paper.get("links", [])
                if link["url"].startswith("/papers/") and paper.get("source")
            },
        }
        for source in public.rglob("*"):
            if not source.is_file() or source.suffix.lower() not in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
                ".ico",
                ".mp4",
                ".pdf",
            ):
                continue
            relative = "original/" + str(source.relative_to(public))
            if MediaAsset.objects.filter(file=relative).exists():
                continue
            target = Path(settings.MEDIA_ROOT) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            MediaAsset.objects.create(
                title=source.stem,
                file=relative,
                mime_type=mime_for_path(source.name),
                size=source.stat().st_size,
                category="初始素材",
                credit=credits.get("/" + str(source.relative_to(public)), original["source"]),
            )
        self.stdout.write(
            self.style.SUCCESS(f"初始化完成：新增 {created_count} 条内容。已有内容保持不变。")
        )
