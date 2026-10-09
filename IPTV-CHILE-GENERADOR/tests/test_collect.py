from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_ROOT = REPO_ROOT / "IPTV-CHILE-GENERADOR"
sys.path.insert(0, str(GENERATOR_ROOT / "scripts"))

import collect


class CollectTests(unittest.TestCase):
    def test_non_retryable_http_error_is_reported_without_nameerror(self):
        error = HTTPError("https://example.test/list.m3u", 404, "Not Found", {}, None)
        with patch.object(collect, "urlopen", side_effect=error) as mocked:
            with self.assertRaises(HTTPError) as raised:
                collect.read_source({"url": "https://example.test/list.m3u"})
        self.assertEqual(raised.exception.code, 404)
        mocked.assert_called_once()

    def test_retryable_http_error_retries_with_backoff(self):
        error = HTTPError("https://example.test/list.m3u", 503, "Unavailable", {}, None)
        with patch.object(collect, "urlopen", side_effect=error) as mocked:
            with patch("time.sleep") as sleep:
                with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
                    collect.read_source({"url": "https://example.test/list.m3u"})
        self.assertEqual(mocked.call_count, collect.RETRIES)
        self.assertEqual(sleep.call_count, collect.RETRIES - 1)

    def test_prune_source_health_removes_removed_sources(self):
        previous = {
            "ACTIVE": {"checks": 1},
            "REMOVED": {"checks": 99},
        }
        result = collect.prune_source_health(previous, [{"name": "ACTIVE"}])
        self.assertEqual(result, {"ACTIVE": {"checks": 1}})

    def test_local_repository_sources_point_to_existing_files(self):
        config = json.loads(
            (GENERATOR_ROOT / "config" / "sources.json").read_text(encoding="utf-8-sig")
        )
        source_names = [str(source.get("name") or "").strip() for source in config["sources"]]
        self.assertEqual(len(source_names), len(set(source_names)))

        repo_prefix = "ByD4rking/Iptv-Chile-Master-CL/"
        checked = 0
        for source in config["sources"]:
            parsed = urlsplit(str(source.get("url") or ""))
            if parsed.hostname != "raw.githubusercontent.com":
                continue
            path = parsed.path.lstrip("/")
            if not path.startswith(repo_prefix):
                continue
            relative = path[len(repo_prefix):]
            if relative.startswith("refs/heads/main/"):
                relative = relative[len("refs/heads/main/"):]
            elif relative.startswith("main/"):
                relative = relative[len("main/"):]
            target = REPO_ROOT.joinpath(*relative.split("/"))
            self.assertTrue(
                target.is_file(),
                f"{source.get('name')} apunta a un archivo local inexistente: {relative}",
            )
            checked += 1

        self.assertGreater(checked, 0, "No se revisaron las fuentes raw del propio repositorio.")


if __name__ == "__main__":
    unittest.main()
