# designed by mew
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from cms.models import ContentItem, Revision
from cms.services import record_revision


class AccountAndHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_superuser(
            "manager", password="Manager-Account-728!", first_name="管理员"
        )
        cls.editor = get_user_model().objects.create_user(
            "editor", password="Editor-Account-582!", first_name="编辑同学", is_staff=True
        )
        cls.editor.user_permissions.add(
            Permission.objects.get(codename="change_news", content_type__app_label="cms")
        )

    def setUp(self):
        self.client.force_login(self.manager)
        self.item = ContentItem.objects.create(
            kind="news",
            key="news-history",
            payload={"title_zh": "原消息", "date": "2026-09-22"},
            live={"data": {"title_zh": "原消息", "date": "2026-09-22"}, "order": 100},
            updated_by=self.editor,
        )
        record_revision(self.item, self.editor, "发布")

    def edit_user(self, user, data, method="patch"):
        return getattr(self.client, method)(
            f"/api/manage/users/{user.pk}/", json.dumps(data), content_type="application/json"
        )

    def test_manager_can_edit_reset_disable_and_reenable_team_account(self):
        response = self.edit_user(
            self.editor,
            {
                "username": "renamed-editor",
                "name": "新名字",
                "newPassword": "Updated-Password-583!",
                "confirmPassword": "Updated-Password-583!",
                "active": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.editor.refresh_from_db()
        self.assertEqual(self.editor.get_full_name(), "新名字")
        self.assertEqual(self.editor.username, "renamed-editor")
        self.assertTrue(self.editor.check_password("Updated-Password-583!"))
        self.assertFalse(self.editor.is_active)
        other = Client()
        other.force_login(self.editor)
        self.assertIsNone(other.get("/api/editor/session/").json()["user"])
        self.assertEqual(self.edit_user(self.editor, {"active": True}, "post").status_code, 200)
        self.editor.refresh_from_db()
        self.assertTrue(self.editor.has_perm("cms.publish_content"))
        self.assertTrue(ContentItem.objects.filter(pk=self.item.pk).exists())
        self.assertEqual(self.item.revisions.get().snapshot["actorName"], "编辑同学")

    def test_weak_duplicate_and_invalid_account_edits_are_atomic(self):
        original = self.editor.username
        response = self.edit_user(
            self.editor,
            {"username": "temporary-name", "newPassword": "weak", "confirmPassword": "weak"},
        )
        self.assertEqual(response.status_code, 400)
        self.editor.refresh_from_db()
        self.assertEqual(self.editor.username, original)
        self.assertEqual(
            self.edit_user(self.editor, {"username": self.manager.username}).status_code, 400
        )
        self.assertEqual(self.edit_user(self.editor, {"active": "false"}).status_code, 400)
        self.assertEqual(
            self.edit_user(
                self.editor, {"newPassword": "New-Password-583!", "confirmPassword": "different"}
            ).status_code,
            400,
        )

    def test_current_and_last_manager_cannot_be_deleted_disabled_or_demoted(self):
        self.assertEqual(
            self.client.delete(f"/api/manage/users/{self.manager.pk}/").status_code, 400
        )
        self.assertEqual(self.edit_user(self.manager, {"active": False}).status_code, 400)
        self.assertEqual(self.edit_user(self.manager, {"manager": False}).status_code, 400)
        self.assertTrue(get_user_model().objects.filter(is_superuser=True, is_active=True).exists())
        self.assertTrue(self.client.get("/api/manage/users/").json()["users"][0]["current"])
        response = self.edit_user(
            self.manager,
            {
                "username": "new-manager",
                "name": "新管理员",
                "newPassword": "Replacement-Manager-842!",
                "confirmPassword": "Replacement-Manager-842!",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(self.client.get("/api/editor/session/").json()["user"]["manager"])
        self.assertEqual(get_user_model().objects.get(pk=self.manager.pk).username, "new-manager")

    def test_deleting_account_preserves_content_and_historical_actor_names(self):
        # Simulate a revision written before names were retained in snapshots.
        revision = self.item.revisions.get()
        revision.snapshot.pop("actorName")
        revision.save()
        response = self.client.delete(f"/api/manage/users/{self.editor.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(get_user_model().objects.filter(pk=self.editor.pk).exists())
        self.item.refresh_from_db()
        self.assertIsNone(self.item.updated_by)
        revision.refresh_from_db()
        self.assertIsNone(revision.actor)
        self.assertEqual(revision.snapshot["actorName"], "编辑同学")
        self.assertEqual(
            self.client.get("/api/manage/history/").json()["items"][0]["actor"], "编辑同学"
        )
        self.assertEqual(
            self.client.get(f"/api/editor/items/news/{self.item.key}/history/").json()["versions"][
                0
            ]["actor"],
            "编辑同学",
        )

    def test_editor_cannot_edit_or_delete_accounts(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.edit_user(self.manager, {"name": "not allowed"}).status_code, 403)
        self.assertEqual(
            self.client.delete(f"/api/manage/users/{self.manager.pk}/").status_code, 403
        )
        self.assertEqual(self.edit_user(self.editor, {"manager": True}).status_code, 403)

    def test_history_reports_persisted_diffs_published_changes_and_filters(self):
        self.item.payload = {**self.item.payload, "title_zh": "草稿标题"}
        self.item.sort_order = 10
        self.item.save()
        record_revision(self.item, self.editor, "页面编辑：保存草稿")
        self.item.live = {"data": dict(self.item.payload), "order": 10}
        self.item.save()
        record_revision(self.item, self.manager, "发布")
        response = self.client.get("/api/manage/history/?q=草稿标题&kind=news&actor=管理员").json()
        self.assertEqual(len(response["items"]), 1)
        changes = {row["field"]: row for row in response["items"][0]["changes"]}
        self.assertEqual(changes["title_zh"]["before"], "原消息")
        self.assertEqual(changes["title_zh"]["after"], "草稿标题")
        self.assertEqual(changes["$order"]["before"], 100)
        self.assertEqual(changes["$order"]["after"], 10)
        self.assertNotIn("$state", changes)
        self.assertFalse(
            any(
                row["action"] == "页面编辑：保存草稿"
                for row in self.client.get("/api/manage/history/").json()["items"]
            )
        )
        self.assertNotIn("password", json.dumps(response))
        self.assertEqual(self.client.get("/api/manage/history/?actor=不存在").json()["items"], [])

    def test_history_pagination_and_kind_permissions_do_not_expose_other_content(self):
        for number in range(24):
            self.item.payload["title_zh"] = f"消息 {number}"
            self.item.live = {"data": dict(self.item.payload), "order": 100}
            record_revision(self.item, self.editor, "发布")
        secret = ContentItem.objects.create(
            kind="project", key="private-project", payload={"name_zh": "仅项目编辑可见"}
        )
        record_revision(secret, self.manager, "保存草稿")
        self.client.force_login(self.editor)
        first = self.client.get("/api/manage/history/").json()
        second = self.client.get("/api/manage/history/?page=2").json()
        self.assertEqual(len(first["items"]), 20)
        self.assertTrue(first["hasMore"])
        self.assertEqual(len(second["items"]), 5)
        self.assertFalse(second["hasMore"])
        self.assertEqual({row["kind"] for row in first["items"]}, {"news"})
        self.assertEqual(self.client.get("/api/manage/history/?kind=project").json()["items"], [])
        self.assertEqual(Client().get("/api/manage/history/").status_code, 403)
        self.assertEqual(Revision.objects.filter(item=secret).count(), 1)
