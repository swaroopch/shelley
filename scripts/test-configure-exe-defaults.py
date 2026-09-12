#!/usr/bin/env python3
"""Offline tests for account-default activation; never contacts exe.dev."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("configure-exe-defaults.sh").resolve()
LOADER = "#!/bin/bash\nset -euo pipefail\nprintf 'first boot\\n'\n"


class ConfigureDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.root / "loader").write_text(LOADER)
        self.env = {**os.environ, "HOME": str(self.root), "CASE": str(self.root),
                    "PATH": str(self.bin) + os.pathsep + os.environ["PATH"]}
        self.command("ssh", '''#!/bin/bash
set -euo pipefail
printf '%s\\n' "$*" >> "$CASE/ssh.calls"
[[ "$1" == exe.dev && "$2" == defaults && "$4" == dev.exe && "$5" == new.setup-script ]]
case "$3" in
read)
  if [[ -f "$CASE/fail-read" ]]; then printf '(not set)\\n'; echo 'authentication failed' >&2; exit 1; fi
  if [[ -f "$CASE/default" ]]; then
    if [[ -f "$CASE/trim-final-newline" ]]; then
      printf '%s' "$(< "$CASE/default")"
    else
      cat "$CASE/default"
    fi
  fi
  ;;
write)
  cat > "$CASE/default"
  if [[ -f "$CASE/corrupt-write" ]]; then printf 'echo unexpected-command\\n' >> "$CASE/default"; fi
  touch "$CASE/written"
  ;;
*) exit 99 ;;
esac
''')
        self.command("curl", '''#!/bin/bash
set -euo pipefail
[[ ! -f "$CASE/fail-curl" ]] || exit 22
while [[ $# -gt 0 ]]; do
  if [[ "$1" == -o ]]; then cp "$CASE/loader" "$2"; exit 0; fi
  shift
done
exit 99
''')

    def command(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def run_helper(self, *args):
        return subprocess.run(["bash", str(SCRIPT), *args], env=self.env,
                              text=True, capture_output=True, check=False)

    def test_explicit_apply_required(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "ssh.calls").exists())

    def test_empty_default_is_set_and_verified(self):
        result = self.run_helper("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "default").read_text(), LOADER)
        self.assertIn("Verified:", result.stdout)
        self.assertEqual((self.root / "ssh.calls").read_text().count("defaults write"), 1)

    def test_not_set_marker_is_set_and_verified_with_raw_backup(self):
        previous = "(not set)\n"
        (self.root / "default").write_text(previous)
        result = self.run_helper("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "default").read_text(), LOADER)
        self.assertIn("Verified:", result.stdout)
        self.assertEqual((self.root / "ssh.calls").read_text().count("defaults write"), 1)
        backups = list((self.root / ".local/state/shelley-exe-defaults").glob("*/prior-setup.sh"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), previous)

    def test_marker_with_other_content_is_not_treated_as_unset(self):
        for previous in (
            '#!/bin/bash\necho "(not set)"\n',
            "warning: an unexpected response\n(not set)\n",
            "(not set) but not the exact marker\n",
        ):
            with self.subTest(previous=previous):
                (self.root / "default").write_text(previous)
                result = self.run_helper("--apply")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual((self.root / "default").read_text(), previous)
                self.assertFalse((self.root / "written").exists())

    def test_existing_default_is_backed_up_and_not_overwritten(self):
        previous = "#!/bin/bash\necho keep-my-old-setup\n"
        (self.root / "default").write_text(previous)
        result = self.run_helper("--apply")
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.root / "default").read_text(), previous)
        self.assertFalse((self.root / "written").exists())
        backups = list((self.root / ".local/state/shelley-exe-defaults").glob("*/prior-setup.sh"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), previous)
        self.assertNotIn("keep-my-old-setup", result.stdout + result.stderr)

    def test_existing_identical_default_is_noop(self):
        (self.root / "default").write_text(LOADER)
        result = self.run_helper("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already configured", result.stdout)
        self.assertFalse((self.root / "written").exists())

    def test_existing_default_without_final_newline_is_verified_without_write(self):
        previous = LOADER.rstrip("\n")
        (self.root / "default").write_text(previous)
        result = self.run_helper("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verified:", result.stdout)
        self.assertIn("no changes made", result.stdout)
        self.assertFalse((self.root / "written").exists())
        self.assertEqual((self.root / "default").read_text(), previous)

    def test_readback_without_final_newline_is_verified(self):
        (self.root / "trim-final-newline").touch()
        result = self.run_helper("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verified:", result.stdout)
        self.assertEqual((self.root / "ssh.calls").read_text().count("defaults write"), 1)
        backups = list((self.root / ".local/state/shelley-exe-defaults").glob("*/confirmed-setup.sh"))
        self.assertEqual(backups[0].read_text(), LOADER.rstrip("\n"))

    def test_other_whitespace_and_content_differences_are_not_ignored(self):
        for previous in (
            LOADER + "\n",  # Additional blank lines are not stripped.
            LOADER.replace("set -euo", "set  -euo"),
            LOADER.replace("first boot", "different behavior"),
            LOADER.replace("\n", "\r\n"),
        ):
            with self.subTest(previous=previous):
                (self.root / "default").write_bytes(previous.encode())
                result = self.run_helper("--apply")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((self.root / "written").exists())
                self.assertEqual((self.root / "default").read_bytes(), previous.encode())

    def test_changed_readback_still_fails_verification(self):
        (self.root / "corrupt-write").touch()
        result = self.run_helper("--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("read-back differs", result.stderr)
        self.assertTrue((self.root / "written").exists())
        self.assertNotIn("Verified:", result.stdout)

    def test_read_error_is_not_treated_as_empty_default(self):
        (self.root / "fail-read").touch()
        result = self.run_helper("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "written").exists())

    def test_download_or_syntax_failure_cannot_write_default(self):
        (self.root / "fail-curl").touch()
        result = self.run_helper("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "written").exists())
        (self.root / "fail-curl").unlink()
        (self.root / "loader").write_text("#!/bin/bash\nif broken\n")
        result = self.run_helper("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "written").exists())


if __name__ == "__main__":
    unittest.main()
