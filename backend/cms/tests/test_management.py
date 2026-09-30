# designed by mew
import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import resolve
from PIL import Image

from cms.models import ContentItem, MediaAsset
from cms.services import record_revision
from cms.views import frontend
from cms.website_backups import FORMAT, fingerprint, restore_snapshot


class ManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_superuser(
            "manager", password="Current-Password-481!"
        )
        cls.editor = get_user_model().objects.create_user(
            "editor", password="Editor-Password-481!", is_staff=True
        )

    def setUp(self):
        self.work = TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.settings_override = override_settings(
            DATA_DIR=self.root, MEDIA_ROOT=self.root / "media", FRONTEND_DIR=self.root / "frontend"
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        (self.root / "frontend").mkdir()
        (self.root / "frontend/index.html").write_text('<main id="app">Vue management shell</main>')
        self.client.force_login(self.manager)
        image = self.root / "media/uploads/photo.png"
        image.parent.mkdir(parents=True)
        Image.new("RGB", (12, 12), "blue").save(image)
        self.asset = MediaAsset.objects.create(
            title="原照片",
            file="uploads/photo.png",
            mime_type="image/png",
            size=image.stat().st_size,
            uploaded_by=self.manager,
        )
        self.item = ContentItem.objects.create(
            kind="news",
            key="test-news",
            payload={
                "title_zh": "新草稿",
                "date": "2026-09-22",
                "image": "/media/uploads/photo.png",
                "body_zh": '<p>正文<img src="/media/uploads/photo.png"></p>',
            },
            live={
                "data": {
                    "title_zh": "已发布消息",
                    "date": "2026-09-22",
                    "image": "/media/uploads/photo.png",
                },
                "order": 20,
            },
            sort_order=10,
        )
        record_revision(self.item, self.manager, "备份前草稿")

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def backup(self):
        response = self.client.get("/api/manage/backups/download/")
        self.assertEqual(response.status_code, 200)
        result = b"".join(response.streaming_content)
        response.close()
        return result

    def preview(self, content):
        return self.client.post(
            "/api/manage/restore/",
            {"file": SimpleUploadedFile("website.zip", content, content_type="application/zip")},
        )

    def rewritten_archive(self, contents, mutate):
        with zipfile.ZipFile(BytesIO(contents)) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        mutate(entries)
        entries["manifest.json"] = json.dumps(
            {
                "format": FORMAT,
                "files": {
                    key: hashlib.sha256(value).hexdigest()
                    for key, value in entries.items()
                    if key != "manifest.json"
                },
            }
        ).encode()
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for key, value in entries.items():
                archive.writestr(key, value)
        return output.getvalue()

    def test_old_admin_routes_only_return_the_vue_shell(self):
        for url in ("/admin/", "/admin/login/", "/admin/auth/user/", "/admin/content-transfer/"):
            self.assertIs(resolve(url).func, frontend)
            response = Client().get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Vue management shell", b"".join(response.streaming_content))

    def test_group_media_pagination_follows_carousel_order(self):
        for index in range(43):
            MediaAsset.objects.create(
                title=f"合照 {index}",
                file=f"original/images/group-{index}.webp",
                category="group-photo",
                size=1,
            )
        for index, order in [(0, 20), (1, 10), (2, 30)]:
            ContentItem.objects.create(
                kind="photo",
                key=f"photo-{index}",
                sort_order=order,
                payload={
                    "image": f"/images/group-{index}.webp",
                    "show_home": index != 2,
                    "show_people": index != 2,
                },
            )
        response = self.client.get("/api/media/?type=image&category=group-photo").json()
        self.assertEqual([row["title"] for row in response["items"][:2]], ["合照 1", "合照 0"])
        self.assertTrue(response["more"])
        second = self.client.get("/api/media/?type=image&category=group-photo&page=2").json()
        self.assertEqual(len(second["items"]), 3)
        self.assertFalse(second["more"])

    def test_password_checks_old_password_and_keeps_current_session(self):
        url = "/api/manage/password/"
        bad = self.post(
            url,
            {
                "oldPassword": "wrong",
                "newPassword": "Replacement-Password-672!",
                "confirmPassword": "Replacement-Password-672!",
            },
        )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(
            self.post(
                url,
                {
                    "oldPassword": "Current-Password-481!",
                    "newPassword": "short",
                    "confirmPassword": "short",
                },
            ).status_code,
            400,
        )
        response = self.post(
            url,
            {
                "oldPassword": "Current-Password-481!",
                "newPassword": "Replacement-Password-672!",
                "confirmPassword": "Replacement-Password-672!",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("csrfToken", response.json())
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.check_password("Current-Password-481!"))
        self.assertTrue(self.manager.check_password("Replacement-Password-672!"))
        self.assertTrue(self.client.get("/api/editor/session/").json()["user"]["manager"])

    def test_manager_creates_validated_editor_with_publication_permission(self):
        data = {
            "username": "new-editor",
            "name": "新同学",
            "password": "New-Account-Password-782!",
            "confirmPassword": "New-Account-Password-782!",
        }
        response = self.post("/api/manage/users/", data)
        self.assertEqual(response.status_code, 201, response.content)
        user = get_user_model().objects.get(username="new-editor")
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.has_perm("cms.publish_content"))
        self.assertTrue(user.has_perm("cms.add_news"))
        self.assertTrue(user.check_password(data["password"]))
        self.assertEqual(self.post("/api/manage/users/", data).status_code, 400)
        self.assertEqual(
            self.post(
                "/api/manage/users/",
                {**data, "username": "weak", "password": "short", "confirmPassword": "short"},
            ).status_code,
            400,
        )
        self.assertFalse(get_user_model().objects.filter(username="weak").exists())
        self.assertNotIn("password", self.client.get("/api/manage/users/").content.decode())

    def test_editor_cannot_manage_accounts_or_backups_but_can_change_own_password(self):
        self.client.force_login(self.editor)
        metadata = self.client.get("/api/manage/backups/").json()
        self.assertFalse(metadata["canBackup"])
        self.assertFalse(metadata["canRestore"])
        for url in ("/api/manage/users/", "/api/manage/backups/download/"):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.post("/api/manage/users/", {}).status_code, 403)
        self.assertEqual(self.post("/api/manage/restore/", {}).status_code, 403)
        self.assertEqual(
            self.post(
                "/api/manage/password/",
                {
                    "oldPassword": "Editor-Password-481!",
                    "newPassword": "Changed-Editor-Password-294!",
                    "confirmPassword": "Changed-Editor-Password-294!",
                },
            ).status_code,
            200,
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        self.assertEqual(client.post("/api/manage/password/", {}).status_code, 403)
        self.assertEqual(Client().get("/api/manage/backups/").status_code, 403)
        self.assertEqual(Client().post("/api/register/").status_code, 404)

    def test_backup_preview_and_restore_preserve_states_media_history_and_accounts(self):
        archive = self.backup()
        with zipfile.ZipFile(BytesIO(archive)) as source:
            self.assertEqual(
                set(source.namelist()), {"content.json", "manifest.json", "media/uploads/photo.png"}
            )
            exported = json.loads(source.read("content.json"))
            self.assertNotIn("users", exported)
        original_password = get_user_model().objects.get(pk=self.manager.pk).password
        self.item.payload["title_zh"] = "备份后修改"
        self.item.version += 1
        self.item.save()
        before = fingerprint()
        response = self.preview(archive)
        self.assertEqual(response.status_code, 200, response.content)
        preview = response.json()
        self.assertEqual(preview["summary"]["contentCount"], 1)
        self.assertEqual(preview["summary"]["mediaCount"], 1)
        self.assertEqual(fingerprint(), before, "Preview must never mutate content")
        self.assertEqual(
            self.post("/api/manage/restore/", {"token": preview["token"]}).status_code, 400
        )
        response = self.post("/api/manage/restore/", {"token": preview["token"], "confirm": True})
        self.assertEqual(response.status_code, 200, response.content)
        restored = ContentItem.objects.get(kind="news", key="test-news")
        self.assertEqual(restored.payload["title_zh"], "新草稿")
        self.assertEqual(restored.live["data"]["title_zh"], "已发布消息")
        self.assertGreater(restored.version, self.item.version)
        self.assertEqual(restored.revisions.count(), 2)
        image = restored.payload["image"]
        self.assertTrue(image.startswith("/media/restored/"))
        self.assertTrue((self.root / image.removeprefix("/")).is_file())
        self.assertEqual(MediaAsset.objects.get().file.url, image)
        self.assertIn(image, restored.payload["body_zh"])
        self.assertEqual(
            get_user_model().objects.get(pk=self.manager.pk).password, original_password
        )
        self.assertIsNotNone(self.client.get("/api/editor/session/").json()["user"])
        self.assertEqual(self.client.get(response.json()["safetyBackup"]).status_code, 200)
        self.assertEqual(
            self.post(
                "/api/manage/restore/", {"token": preview["token"], "confirm": True}
            ).status_code,
            400,
        )

    def test_restore_rejects_stale_preview_without_mutating_content(self):
        preview = self.preview(self.backup()).json()
        self.item.payload["title_zh"] = "同事最新修改"
        self.item.version += 1
        self.item.save()
        before = fingerprint()
        response = self.post("/api/manage/restore/", {"token": preview["token"], "confirm": True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(fingerprint(), before)

    def test_corrupt_unsafe_and_invalid_backup_are_rejected_before_any_write(self):
        archive = self.backup()
        before = fingerprint()
        unsafe = self.rewritten_archive(
            archive, lambda entries: entries.update({"media/../../escape.png": b"bad"})
        )
        self.assertEqual(self.preview(unsafe).status_code, 400)
        self.assertFalse((self.root / "escape.png").exists())

        def broken_link(entries):
            data = json.loads(entries["content.json"])
            data["records"][0]["data"]["image"] = "javascript:alert(1)"
            entries["content.json"] = json.dumps(data).encode()

        self.assertEqual(
            self.preview(self.rewritten_archive(archive, broken_link)).status_code, 400
        )
        self.assertEqual(self.preview(b"not a zip").status_code, 400)

        def fake_image(entries):
            entries["media/uploads/photo.png"] = b"<script>bad()</script>"

        self.assertEqual(self.preview(self.rewritten_archive(archive, fake_image)).status_code, 400)
        with zipfile.ZipFile(BytesIO(archive)) as source:
            entries = {name: source.read(name) for name in source.namelist()}
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as target:
            for name, value in entries.items():
                target.writestr(name, value + b"corrupt" if name == "content.json" else value)
        self.assertEqual(self.preview(output.getvalue()).status_code, 400)
        self.assertEqual(fingerprint(), before)
        self.assertTrue((self.root / "media/uploads/photo.png").is_file())

    def test_failed_restore_rolls_back_database_and_does_not_overwrite_live_files(self):
        preview = self.preview(self.backup()).json()
        before = fingerprint()
        original = (self.root / "media/uploads/photo.png").read_bytes()
        with patch(
            "cms.website_backups.record_revision", side_effect=ValidationError("simulated failure")
        ):
            response = self.post(
                "/api/manage/restore/", {"token": preview["token"], "confirm": True}
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(fingerprint(), before)
        self.assertEqual((self.root / "media/uploads/photo.png").read_bytes(), original)
        self.assertFalse((self.root / "media/restored" / preview["token"]).exists())

    def test_expired_preview_and_download_path_traversal_are_rejected(self):
        preview = self.preview(self.backup()).json()
        metadata_path = self.root / "restore-previews" / preview["token"] / "preview.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["expires"] = 0
        metadata_path.write_text(json.dumps(metadata))
        before = fingerprint()
        self.assertEqual(
            self.post(
                "/api/manage/restore/", {"token": preview["token"], "confirm": True}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/api/manage/backups/download/?name=../../lab.sqlite3").status_code, 400
        )
        self.assertEqual(fingerprint(), before)

    def test_restore_directory_collision_never_removes_existing_live_assets(self):
        preview = self.preview(self.backup()).json()
        directory = self.root / "restore-previews" / preview["token"]
        existing = self.root / "media/restored" / ("a" * 48)
        existing.mkdir(parents=True)
        (existing / "already-published.png").write_bytes(b"committed content")
        before = fingerprint()
        with patch("cms.website_backups.secrets.token_hex", return_value="a" * 48):
            with self.assertRaises(FileExistsError):
                restore_snapshot(directory, self.manager, before)
        self.assertEqual((existing / "already-published.png").read_bytes(), b"committed content")
        self.assertEqual(fingerprint(), before)

    def test_repeated_restore_keeps_backup_media_count_and_file_paths_bounded(self):
        for _ in range(3):
            preview = self.preview(self.backup()).json()
            self.assertEqual(preview["summary"]["mediaCount"], 1)
            result = self.post("/api/manage/restore/", {"token": preview["token"], "confirm": True})
            self.assertEqual(result.status_code, 200, result.content)
            self.assertLess(len(MediaAsset.objects.get().file.name), 100)
            self.assertIsNotNone(self.client.get("/api/editor/session/").json()["user"])

    def test_published_baseline_is_available_for_editor_change_summary(self):
        result = self.client.get("/api/editor/session/").json()
        row = next(row for row in result["records"] if row["id"] == self.item.key)
        self.assertEqual(row["liveData"], self.item.live["data"])
        self.assertEqual(row["liveOrder"], 20)
        self.assertEqual(row["data"], self.item.payload)

    def test_empty_optional_fields_do_not_create_a_phantom_draft(self):
        item = ContentItem.objects.create(
            kind="publication",
            key="empty-optional-paper",
            payload={"title": "Example Paper", "abstract_zh": "", "imageCaption_zh": ""},
            live={"data": {"title": "Example Paper"}, "order": 10},
            sort_order=10,
        )
        records = self.client.get("/api/editor/session/").json()["records"]
        row = next(record for record in records if record["id"] == item.key)
        self.assertFalse(row["hasDraft"])
        self.assertEqual(row["state"], "已发布")

        item.payload["abstract_zh"] = "新增摘要"
        item.save(update_fields=["payload"])
        records = self.client.get("/api/editor/session/").json()["records"]
        row = next(record for record in records if record["id"] == item.key)
        self.assertTrue(row["hasDraft"])
