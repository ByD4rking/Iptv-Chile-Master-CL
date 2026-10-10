from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "generador.yml"


class WorkflowProtectionTests(unittest.TestCase):
    def test_generator_workflow_never_rewrites_or_commits_god_playlist(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn(
            "python IPTV-CHILE-GENERADOR/scripts/aplicar_reconexion_god.py",
            workflow,
            "El workflow no debe reescribir la lista GOD histórica.",
        )
        for line in workflow.splitlines():
            if "git add " in line:
                self.assertNotIn(
                    "IPTV-CHILE-MAESTRA_GOD.m3u",
                    line,
                    "GOD no debe entrar en commits automáticos del generador.",
                )

    def test_generator_workflow_hashes_god_before_and_after_generation(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "sha256sum IPTV-CHILE-MAESTRA_GOD.m3u > /tmp/generador-guard/god.sha256",
            workflow,
        )
        self.assertIn(
            "sha256sum -c /tmp/generador-guard/god.sha256",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
