import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "IPTV-CHILE-GENERADOR" / "scripts"))

import generate


class GeneratePublicationTests(unittest.TestCase):
    def test_playback_valid_endpoint_is_published_even_if_status_probe_says_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            channels_file = base / "channels.json"
            status_file = base / "status.json"
            quality_file = base / "quality.json"
            output_file = base / "output.m3u"
            manifest_file = base / "manifest.json"

            url = "https://example.test/tvo-san-vicente/index.m3u8"
            channels = [{
                "id": "channel-1",
                "name": "TVO San Vicente",
                "group": "Chile",
                "logo": "",
                "sources": [{"url": url, "priority": 100}],
            }]
            channels_file.write_text(json.dumps(channels), encoding="utf-8")
            from atomic import file_sha256
            channels_sha = file_sha256(channels_file)

            status_file.write_text(json.dumps({
                "channels_sha256": channels_sha,
                "results": [{"url": url, "online": False, "response_time_ms": None}],
            }), encoding="utf-8")
            quality_file.write_text(json.dumps({
                "channels_sha256": channels_sha,
                "results": [{
                    "url": url,
                    "playback_checked": True,
                    "playback_ok": True,
                    "quarantined": False,
                    "endpoint_checks": 3,
                    "endpoint_successes": 3,
                    "endpoint_consecutive_failures": 0,
                    "height": 720,
                    "bitrate": 1500000,
                }],
            }), encoding="utf-8")

            with patch.multiple(
                generate,
                CHANNELS_FILE=channels_file,
                STATUS_FILE=status_file,
                QUALITY_FILE=quality_file,
                OUTPUT_FILE=output_file,
                MANIFEST_FILE=manifest_file,
            ):
                generate.main()

            playlist = output_file.read_text(encoding="utf-8")
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            self.assertIn(url, playlist)
            self.assertIn("TVO San Vicente", playlist)
            self.assertEqual(manifest["generated_channels"], 1)
            self.assertEqual(manifest["output_urls"], 1)


if __name__ == "__main__":
    unittest.main()
