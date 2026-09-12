#!/usr/bin/env python3
"""Isolated tests for exe.dev first-boot provisioning (no network/system changes)."""

import os
import pathlib
import subprocess
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVISION = ROOT / "scripts/provision-exe-vm.sh"
LOADER = ROOT / "scripts/exe-first-boot.sh"
HASH = "0123456789abcdef0123456789abcdef01234567"

MOCK = r'''#!/usr/bin/env bash
set -euo pipefail
name="${0##*/}"
printf '%s' "$name" >> "$MOCK_LOG"
printf ' <%s>' "$@" >> "$MOCK_LOG"
printf '\n' >> "$MOCK_LOG"
case "$name" in
  id)
    [[ "${1:-}" == -u ]] && { echo 1000; exit; }
    ;;
  node)
    if [[ "${1:-}" == --version ]]; then echo v24.18.0
    elif [[ "${1:-}" == -p && "${2:-}" == *packageManager* ]]; then echo pnpm@10.34.0
    else echo 24
    fi
    ;;
  npm)
    prefix=''
    while (($#)); do
      [[ "$1" == --prefix ]] && { prefix="$2"; shift 2; continue; }
      shift
    done
    mkdir -p "$prefix/node_modules/.bin"
    cat > "$prefix/node_modules/.bin/pnpm" <<'PNPM'
#!/usr/bin/env bash
printf 'pnpm <%s>\n' "$*" >> "$MOCK_LOG"
exit "${MOCK_PNPM_FAIL:-0}"
PNPM
    chmod +x "$prefix/node_modules/.bin/pnpm"
    ;;
  git)
    if [[ "${1:-}" == clone ]]; then
      dest="${@: -1}"
      mkdir -p "$dest/.git" "$dest/ui"
      printf '{"packageManager":"pnpm@10.34.0"}\n' > "$dest/ui/package.json"
    elif [[ "$*" == *' diff --quiet'* || "$*" == *' diff --cached --quiet'* ]]; then
      exit "${MOCK_GIT_DIRTY:-0}"
    elif [[ "$*" == *'rev-parse'* ]]; then
      if [[ "${@: -1}" == HEAD && "${MOCK_HEAD_CHANGE:-0}" == 1 ]]; then
        count=0
        [[ ! -f "$MOCK_HEAD_COUNT" ]] || count="$(cat "$MOCK_HEAD_COUNT")"
        count=$((count + 1))
        echo "$count" > "$MOCK_HEAD_COUNT"
        if ((count > 1)); then printf 'f%.0s' {1..40}; echo; exit; fi
      fi
      echo "$MOCK_HASH"
    fi
    ;;
  make)
    root=''
    [[ "${1:-}" == -C ]] && root="$2"
    mkdir -p "$root/bin"
    cat > "$root/bin/shelley" <<BINARY
#!/usr/bin/env bash
printf '{"customized":true,"commit":"%s"}\n' '$MOCK_HASH'
BINARY
    chmod +x "$root/bin/shelley"
    ;;
  jq)
    cat >/dev/null
    exit "${MOCK_JQ_FAIL:-0}"
    ;;
  sudo)
    [[ "${1:-}" == -n ]] && shift
    if [[ "${1:-}" == mktemp ]]; then
      mkdir -p "$HOME/mock-priv"
      file="$HOME/mock-priv/$(basename "$2").$RANDOM"
      : > "$file"
      echo "$file"
    fi
    ;;
  curl)
    output=''
    while (($#)); do
      [[ "$1" == --output ]] && { output="$2"; shift 2; continue; }
      shift
    done
    if [[ -n "$output" ]]; then
      printf '#!/usr/bin/env bash\ntouch "$BODY_MARKER"\n' > "$output"
    fi
    exit "${MOCK_CURL_FAIL:-0}"
    ;;
esac
'''


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.home = self.base / "home"
        self.bin = self.base / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        dispatcher = self.bin / "mock"
        dispatcher.write_text(MOCK)
        dispatcher.chmod(0o755)
        for name in (
            "curl", "git", "go", "id", "jq", "make", "node", "npm",
            "sudo", "systemctl", "tmux", "uv", "uvx",
        ):
            (self.bin / name).symlink_to(dispatcher)
        self.log = self.base / "commands.log"
        self.log.write_text("")
        self.env = os.environ.copy()
        self.env.update({
            "HOME": str(self.home),
            "MOCK_HEAD_COUNT": str(self.base / "head-count"),
            "MOCK_HASH": HASH,
            "MOCK_LOG": str(self.log),
            "PATH": f"{self.bin}:/usr/bin:/bin",
        })

    def run_script(self, script, *args, **env):
        merged = self.env | {key: str(value) for key, value in env.items()}
        return subprocess.run(
            ["/bin/bash", str(script), *args], env=merged,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=10,
        )

    def commands(self):
        return self.log.read_text()

    def test_loader_download_failure_never_executes_partial_body(self):
        marker = self.base / "body-ran"
        download_dir = self.base / "downloads"
        download_dir.mkdir()
        result = self.run_script(
            LOADER, MOCK_CURL_FAIL=22, BODY_MARKER=marker, TMPDIR=download_dir
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists(), result.stdout)
        self.assertEqual([], list(download_dir.iterdir()))

    def test_main_requires_exact_explicit_argument(self):
        for args in ((), ("--wrong",), ("--first-boot", "extra")):
            result = self.run_script(PROVISION, *args)
            self.assertEqual(2, result.returncode, result.stdout)
            self.assertIn("usage:", result.stdout)
        self.assertEqual("", self.commands())

    def test_existing_checkout_is_refused_before_sudo(self):
        checkout = self.home / ".config/shelley/shelley-customization"
        checkout.mkdir(parents=True)
        result = self.run_script(PROVISION, "--first-boot")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to modify", result.stdout)
        self.assertIn("recover manually", result.stdout)
        self.assertNotIn("sudo", self.commands())
        self.assertFalse((self.home / ".local/state/shelley-provision").exists())

    def test_failed_binary_validation_never_starts_install(self):
        result = self.run_script(PROVISION, "--first-boot", MOCK_JQ_FAIL=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not customized", result.stdout)
        commands = self.commands()
        self.assertNotIn("install <-d>", commands)
        self.assertNotIn("mktemp </usr/local/lib/shelley-backups", commands)
        self.assertFalse((self.home / ".local/state/shelley-provision/success").exists())

    def test_head_change_never_starts_install(self):
        result = self.run_script(PROVISION, "--first-boot", MOCK_HEAD_CHANGE=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HEAD changed during validation", result.stdout)
        commands = self.commands()
        self.assertNotIn("install <-d>", commands)
        self.assertNotIn("mktemp </usr/local/lib/shelley-backups", commands)

    def test_tracked_source_change_never_starts_install(self):
        result = self.run_script(PROVISION, "--first-boot", MOCK_GIT_DIRTY=1)
        self.assertNotEqual(result.returncode, 0)
        commands = self.commands()
        self.assertIn("git <-C>", commands)
        self.assertIn("<diff> <--quiet>", commands)
        self.assertNotIn("install <-d>", commands)
        self.assertNotIn("mktemp </usr/local/lib/shelley-backups", commands)

    def test_happy_path_and_idempotent_success_marker(self):
        result = self.run_script(PROVISION, "--first-boot")
        self.assertEqual(0, result.returncode, result.stdout)
        marker = self.home / ".local/state/shelley-provision/success"
        self.assertIn(f"commit={HASH}", marker.read_text())
        commands = self.commands()
        self.assertIn("git <clone> <--origin> <origin>", commands)
        self.assertIn("<https://github.com/swaroopch/shelley.git>", commands)
        self.assertIn("<https://github.int.exe.xyz/swaroopch/shelley.git>", commands)
        self.assertIn("node <-p> <require(process.argv[1]).packageManager>", commands)
        self.assertIn("make <-C>", commands)
        self.assertIn("<build-custom>", commands)
        self.assertIn("go <test> <./server> <-parallel> <1>", commands)
        self.assertIn("sudo <-n> <systemctl> <try-restart> <shelley.service>", commands)
        self.assertNotIn("apt-get", commands)
        tools = self.home / ".local/state/shelley-provision/tools.env"
        self.assertIn("shelley-provision/pnpm", tools.read_text())

        self.log.write_text("")
        again = self.run_script(PROVISION, "--first-boot")
        self.assertEqual(0, again.returncode, again.stdout)
        self.assertIn("already provisioned", again.stdout)
        self.assertEqual("", self.commands())


if __name__ == "__main__":
    unittest.main()
