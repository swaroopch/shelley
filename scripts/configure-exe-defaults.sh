#!/usr/bin/env bash
# Run on the user's authenticated workstation, not inside an untrusted VM.
# Uses only the documented exe.dev defaults read/write commands.
set -euo pipefail

if [[ $# != 1 || "$1" != --apply ]]; then
  echo 'Usage: bash configure-exe-defaults.sh --apply' >&2
  echo 'Configures future exeuntu VMs; backs up and refuses to replace existing setup scripts.' >&2
  exit 2
fi
for tool in ssh curl bash cmp wc awk; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
# The lobby drops the final LF on read-back. Add a missing final line
# terminator for comparison only; preserve every other byte/blank line and
# keep the unmodified files for auditing. awk is available on macOS and Linux.
normalize_eof() {
  LC_ALL=C awk '{ print }' "$1"
}

umask 077
state="$HOME/.local/state/shelley-exe-defaults"
mkdir -p "$state"
backup=$(mktemp -d "$state/change.XXXXXX")

# Never interpret authentication/network errors as an empty default. Some
# lobby versions may report an unset key as an error; inspect it and use the
# documented manual activation only after confirming that no setup exists.
if ! ssh exe.dev defaults read dev.exe new.setup-script > "$backup/prior-setup.sh" 2> "$backup/read-error.txt"; then
  echo "Could not read the existing default; nothing changed. Inspect $backup/read-error.txt." >&2
  exit 1
fi
curl --fail --silent --show-error --location \
  https://raw.githubusercontent.com/swaroopch/shelley/custom/scripts/exe-first-boot.sh \
  -o "$backup/proposed-setup.sh"
if [[ ! -s "$backup/proposed-setup.sh" ]] || (( $(wc -c < "$backup/proposed-setup.sh") > 10240 )); then
  echo 'Downloaded setup script is empty or exceeds the 10 KiB limit; nothing changed.' >&2
  exit 1
fi
bash -n "$backup/proposed-setup.sh"
normalize_eof "$backup/prior-setup.sh" > "$backup/prior-normalized.sh"
normalize_eof "$backup/proposed-setup.sh" > "$backup/proposed-normalized.sh"
if cmp -s "$backup/prior-normalized.sh" "$backup/proposed-normalized.sh"; then
  echo 'Verified: this first-boot default is already configured; no changes made.'
  exit 0
fi
# A successful lobby read prints "(not set)" for an absent key. Recognize
# only that whole-output marker (apart from trailing newlines), not arbitrary
# nonempty output or a real script that happens to mention it. Keep the raw
# read in the backup, and never apply this rule to a failed SSH command.
if [[ -s "$backup/prior-setup.sh" && "$(< "$backup/prior-setup.sh")" != '(not set)' ]]; then
  echo "An existing setup script is backed up at $backup/prior-setup.sh." >&2
  echo 'Refusing to overwrite it. Review and compose both setup scripts before changing the default.' >&2
  exit 2
fi

# Explicit --apply is the user's authorization to write an empty default.
ssh exe.dev defaults write dev.exe new.setup-script < "$backup/proposed-setup.sh"
ssh exe.dev defaults read dev.exe new.setup-script > "$backup/confirmed-setup.sh"
normalize_eof "$backup/confirmed-setup.sh" > "$backup/confirmed-normalized.sh"
if ! cmp -s "$backup/proposed-normalized.sh" "$backup/confirmed-normalized.sh"; then
  echo "The account default was written, but read-back differs. Inspect $backup before creating a VM." >&2
  exit 1
fi
echo 'Verified: future exeuntu VMs will run the custom Shelley first-boot installer.'
echo "Account-default backup and verification: $backup"
