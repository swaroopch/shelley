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
  if [[ -f "$CASE/fail-read" ]]; then echo 'authentication failed' >&2; exit 1; fi
  if [[ -f "$CASE/default" ]]; then cat "$CASE/default"; fi
  ;;
write) cat > "$CASE/default"; touch "$CASE/written" ;;
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
