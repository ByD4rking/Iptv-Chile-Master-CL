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

    def test_retry_reanchors_and_rechecks_god_hash(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        retry_start = workflow.index("git reset --hard origin/main")
        retry_end = workflow.index("python -m compileall -q IPTV-CHILE-GENERADOR/scripts", retry_start)
        retry_setup = workflow[retry_start:retry_end]
        self.assertIn(
            "sha256sum IPTV-CHILE-MAESTRA_GOD.m3u > /tmp/generador-guard/god.sha256",
            retry_setup,
            "Cada reintento debe anclar el hash de GOD a la nueva base remota.",
        )
        retry_checks_end = workflow.index("while IFS= read -r line;", retry_end)
        retry_checks = workflow[retry_end:retry_checks_end]
        self.assertIn(
            "sha256sum -c /tmp/generador-guard/god.sha256",
            retry_checks,
            "Cada regeneración debe comprobar que GOD no cambió.",
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
