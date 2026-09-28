#!/usr/bin/env python3
"""Offline regression tests for the isolated Go validation environment."""

from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch


MAIN = runpy.run_path(str(Path(__file__).with_name("run-go-tests.py")))["main"]


class GoTestEnvironmentTests(unittest.TestCase):
    def test_isolation_caches_exit_status_and_cleanup(self) -> None:
        caches = {"GOCACHE": "/cache/build", "GOMODCACHE": "/cache/mod", "GOPATH": "/cache/go"}
        for status in (0, 17):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as owner_home:
                guidance = Path(owner_home) / ".agents" / "AGENTS.md"
                guidance.parent.mkdir()
                guidance.write_text("Owner's private guidance\n")
                test_homes = []

                def run_tests(args, *, env):
                    self.assertEqual(args, ["go", "test", "-parallel", "1", "./..."])
                    home = Path(env["HOME"])
                    test_homes.append(home)
                    self.assertTrue(home.is_dir())
                    self.assertNotEqual(str(home), owner_home)
                    self.assertFalse((home / ".agents").exists())
                    self.assertEqual({key: env[key] for key in caches}, caches)
                    self.assertEqual(env["PATH"], os.environ["PATH"])
                    (home / "test-artifact").write_text("removed after validation\n")
                    return status

                with (
                    patch.dict(os.environ, {"HOME": owner_home}),
                    patch("subprocess.check_output", return_value=json.dumps(caches)) as go_env,
                    patch("subprocess.call", side_effect=run_tests),
                ):
                    self.assertEqual(MAIN(), status)
                go_env.assert_called_once_with(
                    ["go", "env", "-json", "GOCACHE", "GOMODCACHE", "GOPATH"], text=True
                )
                self.assertEqual(len(test_homes), 1)
                self.assertFalse(test_homes[0].exists())
                self.assertTrue(guidance.exists())

    def test_go_environment_failure_propagates(self) -> None:
        with (
            patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(9, "go")),
            patch("subprocess.call") as run_tests,
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                MAIN()
        run_tests.assert_not_called()


if __name__ == "__main__":
    unittest.main()
