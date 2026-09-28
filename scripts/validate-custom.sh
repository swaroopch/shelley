#!/usr/bin/env bash
# Run only in the sync job's disposable checkout. Never installs or restarts Shelley.
set -euo pipefail
if [[ $# != 1 || ! -d "$1/.git" ]]; then
  echo 'usage: validate-custom.sh ABSOLUTE_SYNC_CHECKOUT' >&2
  exit 2
fi
cd "$1"
# Match a normal developer/test environment: upstream permission-preservation
# tests create 0640 files. The service's private state directory stays 0700.
umask 022
export CI=true
uv run --no-project scripts/test-sync-custom.py
uv run --no-project scripts/test-provision-exe-vm.py
uv run --no-project scripts/test-configure-exe-defaults.py
uv run --no-project scripts/test-run-go-tests.py
make ui
(
  cd ui
  pnpm run type-check
  pnpm run type-check:vue
  pnpm run lint
  pnpm test
)
make build-custom
# Go's chromedp tests need a browser on PATH too. Reuse the exact Chromium
# installed for Playwright rather than requiring a separate system package.
(cd ui && pnpm exec playwright install chromium)
chromium_path=$(cd ui && pnpm exec node -e 'process.stdout.write(require("@playwright/test").chromium.executablePath())')
[[ -x "$chromium_path" ]] || { echo "Chromium is not executable: $chromium_path" >&2; exit 1; }
export PATH="$(dirname "$chromium_path"):$PATH"
uv run --no-project scripts/run-go-tests.py
browser_specs=()
while IFS= read -r spec || [[ -n "$spec" ]]; do
  [[ -z "$spec" || "$spec" == \#* ]] && continue
  if [[ ! "$spec" =~ ^e2e/[a-zA-Z0-9_./-]+\.spec\.ts$ || "$spec" == *..* || ! -f "ui/$spec" ]]; then
    echo "Invalid browser test path: $spec" >&2
    exit 2
  fi
  browser_specs+=("$spec")
done < .shelley-browser-tests
if (( ${#browser_specs[@]} )); then
  (
    cd ui
    pnpm exec playwright test "${browser_specs[@]}"
  )
fi
