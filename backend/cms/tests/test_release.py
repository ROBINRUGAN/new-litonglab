# designed by mew
"""Guard publication-file bindings and portable recovery, not external metadata claims."""

import hashlib
import importlib.util
import json
import sqlite3
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase as DjangoTestCase
from django.test import override_settings

from cms.forms import validate_payload

ROOT = settings.BASE_DIR


class PublicationDataTests(DjangoTestCase):
    def test_seed_pdf_links_resolve_to_distinct_pdf_files(self):
        papers = json.loads((ROOT / "content/seed/publications.json").read_text())
        self.assertTrue(papers)
        self.assertEqual(len({paper["id"] for paper in papers}), len(papers))
        public = ROOT / "frontend/public"
        if not public.is_dir():
            public = settings.FRONTEND_DIR
        hashes = {}
        for paper in papers:
            for link in paper["links"]:
                url = urlsplit(link["url"])
                if url.scheme or url.netloc or not url.path.lower().endswith(".pdf"):
                    continue
                with self.subTest(paper=paper["id"], url=link["url"]):
                    file = (public / unquote(url.path).lstrip("/")).resolve()
                    self.assertTrue(file.is_relative_to(public.resolve()), file)
                    self.assertTrue(file.is_file(), file)
                    with file.open("rb") as source:
                        self.assertEqual(source.read(5), b"%PDF-", file)
                        source.seek(0)
                        digest = hashlib.sha256()
                        while chunk := source.read(1024 * 1024):
                            digest.update(chunk)
                    checksum = digest.hexdigest()
                    self.assertEqual(
                        hashes.setdefault(checksum, paper["id"]),
                        paper["id"],
                        "Different papers must not share the same PDF contents",
                    )
        self.assertTrue(hashes, "The seed must retain its local publication PDFs")

    def test_chinese_grades_and_corrected_publication_metadata(self):
        papers = json.loads((ROOT / "content/seed/publications.json").read_text())
        grades = {
            "软件学报": "A",
            "电子学报": "A",
            "计算机学报": "A",
            "计算机研究与发展": "A",
            "计算机科学": "B",
            "计算机工程与科学": "C",
            "大数据": "C",
        }
        for paper in papers:
            if paper["venueShort"] in grades:
                self.assertEqual(paper["ccfRating"], grades[paper["venueShort"]])
                self.assertIn("2019", paper["ccfEdition"])
            if paper.get("track"):
                self.assertEqual(paper["ccfRating"], "unranked")
        index = {p["id"]: p for p in papers}
        for key, (year, venue, rating) in {
            29: ("2022", "WCNC", "C"),
            37: ("2011", "ATC", "unranked"),
            43: ("2025", "TON", "A"),
            46: ("2023", "TON", "A"),
            55: ("2018", "IEEE Network", "unranked"),
            56: ("2018", "IJCS", "unranked"),
            64: ("2024", "软件学报", "A"),
            68: ("2021", "计算机学报", "A"),
        }.items():
            with self.subTest(paper=f"pub-{key}"):
                paper = index[f"pub-{key}"]
                self.assertEqual(
                    (str(paper["year"]), paper["venueShort"], paper["ccfRating"]),
                    (year, venue, rating),
                )

    def test_corrected_clex_and_actshare_pdf_bindings(self):
        papers = json.loads((ROOT / "content/seed/publications.json").read_text())
        index = {paper["id"]: paper for paper in papers}
        public = ROOT / "frontend/public"
        if not public.is_dir():
            public = settings.FRONTEND_DIR
        for key, title, pdf, checksum_prefix in (
            ("pub-2", "CLEX:", "/papers/pub-2-6b3d6bcdb0.pdf", "6b3d6bcdb0"),
            ("pub-3", "ActShare:", "/papers/pub-3-52ec6299bd.pdf", "52ec6299bd"),
        ):
            with self.subTest(paper=key):
                self.assertIn(title, index[key]["title"])
                self.assertIn(pdf, [urlsplit(link["url"]).path for link in index[key]["links"]])
                checksum = hashlib.sha256((public / pdf.lstrip("/")).read_bytes()).hexdigest()
                self.assertTrue(checksum.startswith(checksum_prefix))

    def test_impossible_publication_date_rejected(self):
        with self.assertRaises(ValidationError):
            validate_payload(
                "publication",
                {
                    "title": "Test",
                    "authors": "Author",
                    "year": "2026",
                    "category": "Journal Papers",
                    "venueShort": "TEST",
                    "publishedDate": "2026-02-31",
                },
            )


class BackupTests(TestCase):
    def test_backup_restores_database_and_media_and_refuses_overwrite(self):
        spec = importlib.util.spec_from_file_location(
            "restore_backup", ROOT / "scripts/restore_backup.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with TemporaryDirectory() as work:
            base = Path(work)
            database = base / "lab.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE sample (title TEXT)")
                connection.execute("INSERT INTO sample VALUES ('实验室')")
            media = base / "media"
            media.mkdir()
            content = b"backup fixture" * 100_000 + b"last partial chunk"
            (media / "example.txt").write_bytes(content)
            with override_settings(
                DATA_DIR=base,
                MEDIA_ROOT=media,
                DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database}},
            ):
                call_command("backup_site", output=str(base / "backups"), stdout=StringIO())
            archive = next((base / "backups").glob("*.zip"))
            self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
            restored = base / "restored"
            module.restore(archive, restored)
            self.assertEqual((restored / "media/example.txt").read_bytes(), content)
            with sqlite3.connect(restored / "lab.sqlite3") as connection:
                self.assertEqual(
                    connection.execute("SELECT title FROM sample").fetchone()[0], "实验室"
                )
            with self.assertRaises(ValueError):
                module.restore(archive, restored)
