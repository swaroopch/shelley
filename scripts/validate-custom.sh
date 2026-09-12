#!/usr/bin/env bash
# Run only in the sync job's disposable checkout. Never installs or restarts Shelley.
set -euo pipefail
if [[ $# != 1 || ! -d "$1/.git" ]]; then
  echo 'usage: validate-custom.sh ABSOLUTE_SYNC_CHECKOUT' >&2
  exit 2
fi
cd "$1"
export CI=true
uv run --no-project scripts/test-sync-custom.py
make ui
(
  cd ui
  pnpm run type-check
  pnpm run type-check:vue
  pnpm run lint
  pnpm test
)
make build-custom
go test -parallel 1 ./...
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
    pnpm exec playwright install chromium
    pnpm exec playwright test "${browser_specs[@]}"
  )
fi
