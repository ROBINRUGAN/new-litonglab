# designed by mew
import json
from copy import deepcopy
from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from cms.models import ContentItem


class VisualEditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("seed_site", stdout=StringIO())
        cls.editor = get_user_model().objects.create_user(
            "visual-test", password="Visual-Password-573!", is_staff=True
        )
        cls.editor.groups.add(Group.objects.get(name="编辑人员"))

    def setUp(self):
        self.client.force_login(self.editor)

    def row(self, item, **fields):
        return {
            "id": item.key,
            "kind": item.kind,
            "version": item.version,
            "order": item.sort_order,
            "data": {**deepcopy(item.payload), **fields},
        }

    def save(self, rows, action="draft"):
        return self.client.post(
            "/api/editor/changes/",
            json.dumps({"items": rows, "action": action}),
            content_type="application/json",
        )

    def test_anonymous_login_csrf_and_fixed_scope(self):
        client = Client(enforce_csrf_checks=True)
        initial = client.get("/api/editor/session/").json()
        self.assertIsNone(initial["user"])
        self.assertNotIn("records", initial)
        self.assertEqual(
            client.post(
                "/api/editor/login/",
                data=json.dumps({"username": "visual-test", "password": "Visual-Password-573!"}),
                content_type="application/json",
            ).status_code,
            403,
        )
        response = client.post(
            "/api/editor/login/",
            data=json.dumps({"username": "visual-test", "password": "Visual-Password-573!"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=initial["csrfToken"],
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            {k["key"] for k in data["kinds"]},
            {
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
            },
        )
        self.assertEqual(
            {f["name"] for f in data["schemas"]["home"]},
            {"featured_projects", "featured_publications", "carousel_seconds", "join_image"},
        )
        self.assertEqual(
            {f["name"] for f in data["schemas"]["page"]},
            {
                "title_zh",
                "title_en",
                "description_zh",
                "description_en",
                "body_zh",
                "body_en",
                "image",
            },
        )
        self.assertEqual(
            {f["name"] for f in data["schemas"]["site"]}, {"email", "address_zh", "address_en"}
        )
        self.assertEqual([r["id"] for r in data["records"] if r["kind"] == "site"], ["general"])
        self.assertEqual([r["id"] for r in data["records"] if r["kind"] == "page"], ["join"])
        self.assertNotIn("imagePosition", {f["name"] for f in data["schemas"]["person"]})
        self.assertTrue(
            {"abstract_zh", "abstract_en", "image", "imageCaption_zh", "imageCaption_en"}
            <= {field["name"] for field in data["schemas"]["publication"]}
        )
        self.assertEqual(Client().get("/api/editor/items/news/news-1/history/").status_code, 403)

    def test_fixed_text_cannot_be_changed_through_visual_editor(self):
        item = ContentItem.objects.get(kind="home", key="home")
        self.assertEqual(self.save([self.row(item, title_en="Not permitted")]).status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/editor/items/home/home/action/",
                json.dumps({"version": item.version, "action": "unpublish"}),
                content_type="application/json",
            ).status_code,
            403,
        )

    def test_maintain_directions_home_selections_join_image_and_more_than_five_photos(self):
        direction = ContentItem.objects.get(kind="direction", key="network")
        row = self.row(direction, title_zh="新增研究方向")
        row.update(id="new-direction", version=None)
        self.assertEqual(self.save([row], "publish").status_code, 200)
        self.assertTrue(ContentItem.objects.get(kind="direction", key="new-direction").live)
        home = ContentItem.objects.get(kind="home", key="home")
        original_title = home.payload["title_en"]
        self.assertEqual(
            self.save(
                [
                    self.row(
                        home,
                        featured_projects=["blender", "find"],
                        featured_publications=["pub-6", "pub-4"],
                    )
                ],
                "publish",
            ).status_code,
            200,
        )
        home.refresh_from_db()
        self.assertEqual(home.live["data"]["featured_projects"], ["blender", "find"])
        self.assertEqual(home.live["data"]["title_en"], original_title)
        join = ContentItem.objects.get(kind="page", key="join")
        self.assertEqual(
            self.save(
                [self.row(join, image="/images/group_photo_2025.webp")], "publish"
            ).status_code,
            200,
        )
        join.refresh_from_db()
        self.assertEqual(join.live["data"]["image"], "/images/group_photo_2025.webp")
        photo = ContentItem.objects.filter(kind="photo").first()
        row = self.row(photo, title_zh="新合照")
        row.update(id="sixth-photo", version=None)
        self.assertEqual(self.save([row], "publish").status_code, 200)
        self.assertEqual(len(self.client.get("/api/site/").json()["content"]["photo"]), 6)
        other_page = ContentItem.objects.get(kind="page", key="research")
        self.assertEqual(
            self.save([self.row(other_page, image="/images/test.webp")]).status_code, 403
        )

    def test_draft_then_publish_preserves_public_content_until_publish(self):
        item = ContentItem.objects.filter(kind="news").first()
        revision_count = item.revisions.count()
        original = item.live["data"]["title_zh"]
        response = self.save([self.row(item, title_zh="页面中的新消息")])
        self.assertEqual(response.status_code, 200, response.content)
        item.refresh_from_db()
        self.assertEqual(item.live["data"]["title_zh"], original)
        self.assertEqual(item.payload["title_zh"], "页面中的新消息")
        self.assertEqual(item.revisions.count(), revision_count)
        self.assertEqual(self.save([self.row(item)], "publish").status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.live["data"]["title_zh"], "页面中的新消息")
        self.assertEqual(item.revisions.count(), revision_count + 1)

    def test_join_text_and_contact_edits_publish_without_changing_page_identity(self):
        join = ContentItem.objects.get(kind="page", key="join")
        site = ContentItem.objects.get(kind="site", key="general")
        before = deepcopy(join.live["data"])
        fields = {
            "title_zh": "加入我们的团队",
            "description_en": "Research opportunities",
            "body_zh": "<p>欢迎申请。</p>",
            "body_en": "<p>Applications are welcome.</p>",
        }
        self.assertEqual(self.save([self.row(join, **fields)]).status_code, 200)
        join.refresh_from_db()
        self.assertEqual(join.live["data"], before)
        self.assertEqual(
            self.save(
                [
                    self.row(join),
                    self.row(site, email="recruit@example.org", address_en="New address"),
                ],
                "publish",
            ).status_code,
            200,
        )
        public = self.client.get("/api/site/").json()["content"]
        published = next(row for row in public["page"] if row["id"] == "join")
        for field, value in fields.items():
            self.assertEqual(published[field], value)
        self.assertEqual(published["slug"], before["slug"])
        self.assertEqual(public["site"][0]["email"], "recruit@example.org")
        self.assertEqual(public["site"][0]["address_en"], "New address")
        join.refresh_from_db()
        site.refresh_from_db()
        self.assertEqual(self.save([self.row(join, slug="another-page")]).status_code, 400)
        self.assertEqual(
            self.save([self.row(site, logo="/images/other-logo.webp")]).status_code, 400
        )

    def test_carousel_flags_and_order_remain_private_until_publish(self):
        photos = list(ContentItem.objects.filter(kind="photo").order_by("sort_order", "key"))
        first, last = photos[0], photos[-1]
        before = self.client.get("/api/site/").json()["content"]["photo"]
        first_row = self.row(first, show_home=False, show_people=True)
        last_row = self.row(last)
        first_row["order"], last_row["order"] = last.sort_order, first.sort_order
        self.assertEqual(self.save([first_row, last_row]).status_code, 200)
        self.assertEqual(self.client.get("/api/site/").json()["content"]["photo"], before)
        first.refresh_from_db()
        last.refresh_from_db()
        self.assertEqual(self.save([self.row(first), self.row(last)], "publish").status_code, 200)
        after = self.client.get("/api/site/").json()["content"]["photo"]
        self.assertEqual(after[0]["id"], last.key)
        self.assertFalse(next(row for row in after if row["id"] == first.key)["show_home"])
        self.assertTrue(next(row for row in after if row["id"] == first.key)["show_people"])

    def test_stale_batch_is_atomic_and_does_not_overwrite(self):
        first, second = list(ContentItem.objects.filter(kind="news")[:2])
        rows = [self.row(first, title_zh="must not persist"), self.row(second)]
        second.version += 1
        second.save()
        self.assertEqual(self.save(rows).status_code, 409)
        first.refresh_from_db()
        self.assertNotEqual(first.payload["title_zh"], "must not persist")

    def test_new_member_and_group_publish_together_in_reverse_order(self):
        person = ContentItem.objects.filter(kind="person").first()
        member = {
            **self.row(person, name_zh="新增成员", group="visual-new-group"),
            "id": "visual-new-person",
            "version": None,
        }
        group = {
            "kind": "group",
            "id": "visual-new-group",
            "version": None,
            "order": 99,
            "data": {"title_zh": "新分组", "layout": "cards"},
        }
        response = self.save([member, group], "publish")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNotNone(ContentItem.objects.get(key="visual-new-person").live)
        self.assertIsNotNone(ContentItem.objects.get(key="visual-new-group").live)

    def test_unpublished_reference_rolls_back_whole_publish(self):
        item = ContentItem.objects.filter(kind="person").first()
        ContentItem.objects.create(
            kind="group",
            key="unpublished-visual-group",
            payload={"title_zh": "草稿组", "layout": "cards"},
        )
        original = item.payload["group"]
        response = self.save([self.row(item, group="unpublished-visual-group")], "publish")
        self.assertEqual(response.status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.payload["group"], original)

    def test_history_restore_and_recycle_keep_permission_and_version_checks(self):
        item = ContentItem.objects.filter(kind="news").first()
        initial = item.payload["title_zh"]
        version = item.revisions.first().pk
        self.save([self.row(item, title_zh="已发布的新标题")], "publish")
        item.refresh_from_db()
        response = self.client.post(
            f"/api/editor/items/news/{item.key}/action/",
            json.dumps({"action": "revision", "revision": version, "version": item.version}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        item.refresh_from_db()
        self.assertEqual(item.payload["title_zh"], initial)
        self.assertEqual(item.live["data"]["title_zh"], "已发布的新标题")
        self.assertEqual(
            self.client.get(f"/api/editor/items/news/{item.key}/history/").status_code, 200
        )
        self.assertEqual(self.client.get("/api/manage/users/").status_code, 403)

    def test_api_rejects_invalid_urls_and_ignores_payload_identity_override(self):
        item = ContentItem.objects.filter(kind="news").first()
        response = self.save([self.row(item, links=[{"label": "bad", "url": "javascript:bad()"}])])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.save([self.row(item, id="evil", kind="home")]).status_code, 200)
        item.refresh_from_db()
        self.assertNotIn("id", item.payload)
        self.assertNotIn("kind", item.payload)
