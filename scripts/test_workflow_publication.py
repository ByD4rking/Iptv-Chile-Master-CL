"""Regresión: los escritores de playlists deben publicar en una cola común."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkflowPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.updater = (ROOT / ".github/workflows/actualizar.yml").read_text(encoding="utf-8-sig")
        cls.pluto = (ROOT / ".github/workflows/pluto.yml").read_text(encoding="utf-8-sig")

    def test_updater_and_pluto_share_one_publication_group(self):
        self.assertIn("  group: iptv-maintenance", self.updater)
        self.assertIn("  group: iptv-maintenance", self.pluto)

    def test_updater_checks_out_current_main_not_workflow_run_sha(self):
        self.assertIn("          ref: main", self.updater)

    def test_pluto_checks_out_current_main_after_waiting_in_queue(self):
        self.assertIn("          ref: main", self.pluto)


if __name__ == "__main__":
    unittest.main()
