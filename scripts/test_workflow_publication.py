"""Regresión: principal y Pluto deben serializar sus publicaciones en main."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkflowPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.updater = (ROOT / ".github/workflows/actualizar.yml").read_text(encoding="utf-8-sig")
        cls.pluto = (ROOT / ".github/workflows/pluto.yml").read_text(encoding="utf-8-sig")

    def test_both_writers_share_one_non_cancelling_queued_group(self):
        for workflow in (self.updater, self.pluto):
            self.assertIn("  group: iptv-maintenance", workflow)
            self.assertIn("  queue: max", workflow)
            self.assertIn("  cancel-in-progress: false", workflow)

    def test_both_workflows_checkout_current_main(self):
        for workflow in (self.updater, self.pluto):
            self.assertIn("          ref: main", workflow)

    def test_pluto_runs_hourly_away_from_the_top_of_the_hour(self):
        self.assertIn('    - cron: "17 * * * *"', self.pluto)


if __name__ == "__main__":
    unittest.main()
