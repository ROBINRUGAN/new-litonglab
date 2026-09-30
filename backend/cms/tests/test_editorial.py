# designed by mew
import json
from copy import deepcopy
from importlib import import_module
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from PIL import Image

from cms.forms import clean_rich, safe_url, validate_payload
from cms.models import KINDS, ContentItem, MediaAsset
from cms.services import editorial_action, public_site, publish


class EditorialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("seed_site", stdout=StringIO())
        cls.editor = get_user_model().objects.create_user(
            "test-editor", password="LocalTestPassword-582!", is_staff=True
        )
        cls.editor.groups.add(Group.objects.get(name="编辑人员"))
        cls.reader = get_user_model().objects.create_user("test-reader", is_staff=True)

    def setUp(self):
        self.client.force_login(self.editor)

    def test_all_content_types_pass_the_shared_schema_validation(self):
        for kind, _ in KINDS:
            item = ContentItem.objects.filter(kind=kind).first()
            with self.subTest(kind=kind):
                self.assertIsInstance(validate_payload(kind, item.payload, item), dict)

    def test_old_photo_fields_are_removed_without_publishing_a_draft(self):
        item = ContentItem.objects.filter(kind="photo").first()
        legacy = {
            "date": "2026-03-01",
            "album": "旧相册",
            "caption_zh": "旧说明",
            "caption_en": "Old caption",
        }
        item.payload = {**item.payload, **legacy, "show_home": False}
        item.live = {**item.live, "data": {**item.live["data"], **legacy}}
        item.save()
        before_version, before_order = item.version, item.sort_order
        cleaned = validate_payload("photo", item.payload, item, restoring=True)
        self.assertFalse(set(legacy) & set(cleaned))
        migrate = import_module(
            "cms.migrations.0002_remove_unused_photo_fields"
        ).remove_unused_photo_fields
        editor = SimpleNamespace(connection=connection)
        migrate(apps, editor)
        item.refresh_from_db()
        self.assertFalse(set(legacy) & set(item.payload))
        self.assertFalse(set(legacy) & set(item.live["data"]))
        self.assertFalse(item.payload["show_home"])
        self.assertTrue(item.live["data"]["show_home"])
        self.assertEqual(item.sort_order, before_order)
        self.assertEqual(item.version, before_version + 1)
        migrate(apps, editor)
        item.refresh_from_db()
        self.assertEqual(item.version, before_version + 1)

    def test_editor_can_publish_but_not_manage_accounts(self):
        self.assertEqual(self.client.get("/api/manage/users/").status_code, 403)
        item = ContentItem.objects.filter(kind="news").first()
        item.payload["title_zh"] = "已经发布的新消息"
        publish(item, self.editor)
        self.assertEqual(
            self.client.get("/api/site/").json()["content"]["news"][0]["title_zh"],
            "已经发布的新消息",
        )
        with self.assertRaises(PermissionDenied):
            publish(item, self.reader)

    def test_anonymous_cannot_preview_or_write(self):
        anonymous = Client(enforce_csrf_checks=True)
        self.assertEqual(anonymous.get("/api/site/?preview=1").status_code, 403)
        self.assertEqual(anonymous.post("/api/media/upload/").status_code, 403)
        self.assertIsNone(anonymous.get("/api/editor/session/").json()["user"])
        self.assertEqual(anonymous.post("/api/register/").status_code, 404)

    def test_authenticated_upload_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.editor)
        self.assertEqual(client.post("/api/media/upload/").status_code, 403)

    def test_draft_history_and_trash(self):
        item = ContentItem.objects.filter(kind="news").first()
        original = deepcopy(item.payload)
        old_revision = item.revisions.first()
        item.payload["title_en"] = "Draft only"
        item.save()
        self.assertNotEqual(public_site()["news"][0]["title_en"], "Draft only")
        self.assertEqual(public_site(True)["news"][0]["title_en"], "Draft only")
        publish(item, self.editor)
        editorial_action(item.pk, self.editor, "revision", old_revision.pk)
        item.refresh_from_db()
        self.assertEqual(item.payload, original)
        self.assertEqual(item.live["data"]["title_en"], "Draft only")
        editorial_action(item.pk, self.editor, "trash")
        self.assertFalse(any(p["id"] == item.key for p in public_site()["news"]))
        editorial_action(item.pk, self.editor, "restore")
        item.refresh_from_db()
        self.assertIsNone(item.live)
        publish(item, self.editor)
        self.assertEqual(public_site()["news"][0]["title_en"], original["title_en"])

    def test_api_saves_and_publishes_and_rejects_stale_edit(self):
        item = ContentItem.objects.filter(kind="news").first()
        row = {
            "kind": item.kind,
            "id": item.key,
            "order": item.sort_order,
            "version": item.version,
            "data": {**item.payload, "title_zh": "通过页面发布"},
        }
        data = json.dumps({"items": [row], "action": "publish"})
        response = self.client.post("/api/editor/changes/", data, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        item.refresh_from_db()
        self.assertEqual(item.live["data"]["title_zh"], "通过页面发布")
        self.assertEqual(
            self.client.post(
                "/api/editor/changes/", data, content_type="application/json"
            ).status_code,
            409,
        )

    def test_upload_valid_image_and_reject_disguised_file(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            stream = BytesIO()
            Image.new("RGB", (24, 24), "blue").save(stream, format="PNG")
            response = self.client.post(
                "/api/media/upload/",
                {
                    "title": "新照片",
                    "file": SimpleUploadedFile(
                        "photo.png", stream.getvalue(), content_type="image/png"
                    ),
                },
            )
            self.assertEqual(response.status_code, 201)
            self.assertTrue(response.json()["url"].startswith("/media/uploads/"))
            webp = BytesIO()
            Image.new("RGB", (24, 24), "teal").save(webp, format="WEBP")
            response = self.client.post(
                "/api/media/upload/",
                {
                    "file": SimpleUploadedFile(
                        "photo.webp", webp.getvalue(), content_type="application/octet-stream"
                    )
                },
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["type"], "image/webp")
            response = self.client.post(
                "/api/media/upload/",
                {
                    "file": SimpleUploadedFile(
                        "fake.jpg", b"<script>alert(1)</script>", content_type="image/jpeg"
                    )
                },
            )
            self.assertEqual(response.status_code, 400)

    def test_uploaded_media_can_be_renamed_and_deleted_only_when_unused(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            stream = BytesIO()
            Image.new("RGB", (24, 24), "blue").save(stream, format="PNG")
            uploaded = self.client.post(
                "/api/media/upload/",
                {
                    "category": "person-photo",
                    "file": SimpleUploadedFile(
                        "photo.png", stream.getvalue(), content_type="image/png"
                    ),
                },
            ).json()
            url = uploaded["url"]
            self.assertEqual(uploaded["category"], "person-photo")
            self.assertTrue(
                any(
                    row["id"] == uploaded["id"]
                    for row in self.client.get(
                        "/api/media/?type=image&category=person-photo"
                    ).json()["items"]
                )
            )
            moved = self.client.patch(
                f"/api/media/{uploaded['id']}/",
                json.dumps({"category": "group-photo"}),
                content_type="application/json",
            )
            self.assertEqual(moved.status_code, 200)
            self.assertEqual(moved.json()["category"], "group-photo")
            renamed = self.client.patch(
                f"/api/media/{uploaded['id']}/",
                json.dumps({"title": "实验室新合照"}),
                content_type="application/json",
            )
            self.assertEqual(renamed.status_code, 200)
            self.assertEqual(renamed.json()["title"], "实验室新合照")
            self.assertEqual(renamed.json()["url"], url)
            self.assertTrue(
                any(
                    row["title"] == "实验室新合照"
                    for row in self.client.get("/api/media/?q=实验室新合照").json()["items"]
                )
            )
            photo = ContentItem.objects.filter(kind="photo").first()
            photo.payload["image"] = url
            photo.save()
            self.assertEqual(self.client.delete(f"/api/media/{uploaded['id']}/").status_code, 400)
            photo.payload["image"] = "/images/group_photo_2025.webp"
            photo.save()
            self.assertEqual(self.client.delete(f"/api/media/{uploaded['id']}/").status_code, 204)
            self.assertFalse(MediaAsset.objects.filter(pk=uploaded["id"]).exists())
            self.assertFalse((Path(media) / url.removeprefix("/media/")).exists())

    def test_new_public_images_are_registered_without_duplication(self):
        with TemporaryDirectory() as root:
            public = Path(root) / "frontend/public/images/papers"
            public.mkdir(parents=True)
            Image.new("RGB", (12, 12), "teal").save(public / "pub-new.webp", format="WEBP")
            (public.parent / "person-placeholder.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>'
            )
            with override_settings(BASE_DIR=Path(root), MEDIA_ROOT=Path(root) / "media"):
                call_command("sync_public_media", stdout=StringIO())
                call_command("sync_public_media", stdout=StringIO())
                assets = MediaAsset.objects.filter(
                    file__in=[
                        "original/images/papers/pub-new.webp",
                        "original/images/person-placeholder.svg",
                    ]
                )
                self.assertEqual(assets.count(), 2)
                self.assertTrue(
                    assets.filter(file__iendswith=".webp", mime_type="image/webp").exists()
                )
                self.assertEqual(assets.get(file__iendswith=".webp").category, "paper-figure")
                self.assertTrue(
                    any(
                        row["id"] == assets.get(file__iendswith=".webp").id
                        for row in self.client.get("/api/media/?type=image").json()["items"]
                    )
                )
                self.assertFalse(
                    any(
                        row["id"] == assets.get(file__iendswith=".webp").id
                        for row in self.client.get("/api/media/?type=pdf").json()["items"]
                    )
                )
                self.assertTrue(
                    any(
                        row["id"] == assets.get(file__iendswith=".webp").id
                        for row in self.client.get(
                            "/api/media/?type=image&category=paper-figure"
                        ).json()["items"]
                    )
                )
                self.assertTrue(
                    assets.filter(
                        file="original/images/person-placeholder.svg", title="灰色头像占位图"
                    ).exists()
                )
                self.assertEqual(
                    self.client.delete(f"/api/media/{assets.first().id}/").status_code, 400
                )

    def test_media_sync_names_papers_and_corrects_old_webp_types(self):
        with TemporaryDirectory() as root:
            public = Path(root) / "frontend/public"
            (public / "images/papers").mkdir(parents=True)
            (public / "papers").mkdir()
            (public / "images/paper-placeholder.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>'
            )
            Image.new("RGB", (12, 12), "teal").save(
                public / "images/papers/pub-test.webp", format="WEBP"
            )
            (public / "papers/pub-test.pdf").write_bytes(b"%PDF-1.4\n")
            paper = ContentItem.objects.get(kind="publication", key="pub-1")
            paper.payload["title"] = "A Test Paper"
            paper.payload["image"] = "/images/papers/pub-test.webp"
            paper.payload["imageCaption_en"] = "Figure 1: System architecture."
            paper.payload["links"] = [{"label": "PDF", "url": "/papers/pub-test.pdf"}]
            paper.save()
            with override_settings(BASE_DIR=Path(root), MEDIA_ROOT=Path(root) / "media"):
                call_command("sync_public_media", stdout=StringIO())
                image = MediaAsset.objects.get(file="original/images/papers/pub-test.webp")
                pdf = MediaAsset.objects.get(file="original/papers/pub-test.pdf")
                placeholder = MediaAsset.objects.get(file="original/images/paper-placeholder.svg")
                self.assertEqual(image.title, "【架构图】A Test Paper")
                self.assertEqual(image.mime_type, "image/webp")
                self.assertEqual(pdf.title, "A Test Paper")

                image.title = "A Test Paper"
                image.mime_type = "application/octet-stream"
                image.save(update_fields=["title", "mime_type"])
                placeholder.title = "A Test Paper"
                placeholder.save(update_fields=["title"])
                call_command("sync_public_media", stdout=StringIO())
                image.refresh_from_db()
                placeholder.refresh_from_db()
                self.assertEqual(image.title, "【架构图】A Test Paper")
                self.assertEqual(image.mime_type, "image/webp")
                self.assertEqual(placeholder.title, "论文配图占位图")

                image.title = "编辑手动命名"
                image.save(update_fields=["title"])
                call_command("sync_public_media", stdout=StringIO())
                image.refresh_from_db()
                self.assertEqual(image.title, "编辑手动命名")

    def test_sync_replaces_and_removes_legacy_student_placeholders(self):
        with TemporaryDirectory() as root:
            public = Path(root) / "frontend/public/images"
            public.mkdir(parents=True)
            (public / "person-placeholder.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>'
            )
            media = Path(root) / "media"
            old = media / "original/images/people/le-xie.jpg"
            old.parent.mkdir(parents=True)
            old.write_bytes(b"old placeholder")
            MediaAsset.objects.create(
                title="旧示例照片",
                file="original/images/people/le-xie.jpg",
                mime_type="image/jpeg",
                size=old.stat().st_size,
                category="初始素材",
            )
            person = ContentItem.objects.get(kind="person", key="le-xie")
            person.payload["image"] = "/images/people/le-xie.jpg"
            person.live["data"]["image"] = "/images/people/le-xie.jpg"
            person.save(update_fields=["payload", "live"])
            with override_settings(BASE_DIR=Path(root), MEDIA_ROOT=media):
                call_command("sync_public_media", stdout=StringIO())
            person.refresh_from_db()
            self.assertEqual(person.payload["image"], "/images/person-placeholder.svg")
            self.assertEqual(person.live["data"]["image"], "/images/person-placeholder.svg")
            self.assertFalse(old.exists())
            self.assertFalse(
                MediaAsset.objects.filter(file="original/images/people/le-xie.jpg").exists()
            )

    def test_normalizing_photo_layout_preserves_a_new_uploaded_faculty_photo(self):
        from cms.management.commands.sync_public_media import normalize_person_photos

        person = ContentItem.objects.get(kind="person", key="tong-li")
        for data in (person.payload, person.live["data"]):
            data.update(
                image="/media/uploads/new-portrait.webp", portraitInset=10, imagePosition="50% 20%"
            )
        person.save()
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            normalize_person_photos([person])
        person.refresh_from_db()
        for data in (person.payload, person.live["data"]):
            self.assertEqual(data["image"], "/media/uploads/new-portrait.webp")
            self.assertNotIn("portraitInset", data)
            self.assertNotIn("imagePosition", data)

    def test_sanitization_and_safe_links(self):
        html = clean_rich(
            '<p onclick="bad()">Hello<img src="x" onerror="bad()"><a href="javascript:bad()">link</a><iframe src="https://x"></iframe></p>'
        )
        for forbidden in ("onclick", "onerror", "javascript:", "<iframe"):
            self.assertNotIn(forbidden, html)
        for link in (
            "javascript:alert(1)",
            "//evil.example",
            "data:text/html,bad",
            "/\\evil.example",
        ):
            with self.assertRaises(ValidationError):
                safe_url(link)

    def test_publication_track_and_venue(self):
        paper = ContentItem.objects.get(kind="publication", key="pub-1")
        data = {**paper.payload, "track": "Poster", "ccfRating": "A"}
        self.assertEqual(validate_payload("publication", data, paper)["ccfRating"], "unranked")
        for track in ("Short Paper", "Workshop"):
            data["track"] = track
            self.assertEqual(validate_payload("publication", data, paper)["ccfRating"], "unranked")
        self.assertEqual(public_site()["publication"][0]["venueShort"], "SIGCOMM")

    def test_references_must_be_published_and_cannot_be_orphaned(self):
        project = ContentItem.objects.get(kind="project", key="tack")
        with self.assertRaises(ValidationError):
            editorial_action(project.pk, self.editor, "trash")
        group = ContentItem.objects.create(
            kind="group", key="future", payload={"title_en": "Future", "layout": "cards"}
        )
        person = ContentItem.objects.get(kind="person", key="le-xie")
        person.payload["group"] = group.key
        with self.assertRaises(ValidationError):
            publish(person, self.editor)

    def test_project_rename_preserves_old_url(self):
        project = ContentItem.objects.get(kind="project", key="tack")
        project.payload["slug"] = "tack-new"
        publish(project, self.editor)
        self.assertIn("tack", project.live["data"]["aliases"])
        other = ContentItem.objects.get(kind="project", key="art")
        with self.assertRaises(ValidationError):
            validate_payload("project", {**other.payload, "slug": "tack"}, other)

    def test_initial_migration_is_idempotent_and_complete(self):
        item = ContentItem.objects.filter(kind="news").first()
        item.payload["title_en"] = "Do not overwrite"
        item.save()
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("seed_site", stdout=StringIO())
        item.refresh_from_db()
        self.assertEqual(item.payload["title_en"], "Do not overwrite")
        self.assertEqual(ContentItem.objects.filter(kind="publication").count(), 84)
        self.assertEqual(ContentItem.objects.filter(kind="person").count(), 15)

    def test_paper_poster_backfill_preserves_editor_fields(self):
        paper = ContentItem.objects.get(kind="publication", key="pub-1")
        paper.payload["abstract_en"] = "Editor's own abstract"
        paper.payload["image"] = "/media/uploads/custom.webp"
        paper.live["data"].pop("abstract_en")
        paper.live["data"]["image"] = "/assets/protocols.webp"
        paper.save()
        call_command("hydrate_publication_pages", stdout=StringIO())
        paper.refresh_from_db()
        self.assertEqual(paper.payload["abstract_en"], "Editor's own abstract")
        self.assertEqual(paper.payload["image"], "/media/uploads/custom.webp")
        self.assertTrue(paper.live["data"]["abstract_en"])
        self.assertEqual(paper.live["data"]["image"], "/images/papers/pub-1.webp")
        version = paper.version
        paper.live["data"]["abstract_en"] = ""
        paper.save()
        call_command("hydrate_publication_pages", stdout=StringIO())
        paper.refresh_from_db()
        self.assertEqual(paper.version, version)
        self.assertEqual(paper.live["data"]["abstract_en"], "")
