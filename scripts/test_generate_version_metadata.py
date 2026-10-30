"""Offline regression tests for headless-shell release selection."""

import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "version_metadata", Path(__file__).with_name("generate-version-metadata.py")
)
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)

NEWEST = "headless-shell/v157.0.8103.27"
OLDER = "headless-shell/v156.0.8078.48.p1"
AMD64 = "headless-shell-linux-amd64.tar.gz"
ARM64 = "headless-shell-linux-arm64.tar.gz"


class HeadlessShellSelectionTest(unittest.TestCase):
    def select(self, releases):
        with (
            patch.object(
                metadata.subprocess, "check_output", return_value="\n".join(releases)
            ),
            patch.object(metadata, "release_assets", side_effect=releases.__getitem__),
        ):
            return metadata.get_headless_shells()

    def test_newest_release_replaces_previous_pin(self):
        tag, builds = self.select(
            {NEWEST: [AMD64, ARM64], OLDER: [AMD64, ARM64]}
        )
        self.assertEqual(tag, NEWEST)
        self.assertEqual(
            builds,
            {
                platform: {
                    "version": "Chromium 157.0.8103.27",
                    "url": f"{metadata.RELEASES_URL}/{NEWEST}/{asset}",
                }
                for platform, asset in (("linux_amd64", AMD64), ("linux_arm64", ARM64))
            },
        )

    def test_each_platform_uses_its_newest_available_build(self):
        tag, builds = self.select({NEWEST: [AMD64], OLDER: [AMD64, ARM64]})
        self.assertEqual(tag, NEWEST)
        self.assertEqual(builds["linux_amd64"]["version"], "Chromium 157.0.8103.27")
        self.assertEqual(builds["linux_arm64"]["version"], "Chromium 156.0.8078.48.p1")
        self.assertEqual(
            builds["linux_arm64"]["url"], f"{metadata.RELEASES_URL}/{OLDER}/{ARM64}"
        )

    def test_release_without_builds_is_skipped(self):
        tag, _ = self.select({NEWEST: [], OLDER: [AMD64, ARM64]})
        self.assertEqual(tag, OLDER)

    def test_missing_platform_is_an_error(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as raised:
                self.select({NEWEST: [AMD64]})
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("linux_arm64", errors.getvalue())

    def test_no_tags_is_an_error(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as raised:
                self.select({})
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("no headless-shell/v* tags found", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
