#!/usr/bin/env bash
# Provision a fresh exe.dev Ubuntu VM with the published custom Shelley build.
# Prefers the CI-built and CI-tested binary for custom (see
# .github/workflows/custom-prebuilt.yml), verified by SHA-256; builds and tests
# from source exactly as before whenever no verified prebuilt binary is available.
# This intentionally refuses existing checkouts and never changes Shelley data or units.
set -euo pipefail

usage() {
  echo 'usage: provision-exe-vm.sh --first-boot' >&2
  exit 2
}
[[ $# == 1 && "$1" == --first-boot ]] || usage
[[ -n "${HOME:-}" && "$HOME" == /* ]] || { echo 'HOME must be an absolute path' >&2; exit 1; }

readonly checkout="$HOME/.config/shelley/shelley-customization"
readonly state_dir="$HOME/.local/state/shelley-provision"
readonly marker="$state_dir/success"
readonly log="$state_dir/provision.log"
readonly tools_root="$HOME/.local/share/shelley-provision"
readonly tools_env="$state_dir/tools.env"
readonly dest='/usr/local/bin/shelley'
readonly backup_dir='/usr/local/lib/shelley-backups'
readonly origin_url='https://github.com/boldsoftware/shelley.git'
readonly fork_fetch='https://github.com/swaroopch/shelley.git'
readonly fork_push='https://github.int.exe.xyz/swaroopch/shelley.git'
# Published by CI: shelley-linux-amd64-<commit> plus <same>.sha256 (written last).
readonly prebuilt_url="${SHELLEY_PREBUILT_URL:-https://github.com/swaroopch/shelley/releases/download/custom-prebuilt}"
readonly prebuilt_asset='shelley-linux-amd64'
# How many first-parent commits of custom to search for the newest good build.
readonly prebuilt_depth=20

if [[ -f "$marker" ]]; then
  echo "Shelley is already provisioned: $(cat "$marker")"
  exit 0
fi
if [[ -e "$checkout" || -L "$checkout" ]]; then
  cat >&2 <<EOF
Refusing to modify the existing canonical checkout:
  $checkout
No files were removed or reset. Inspect it and $state_dir, then recover manually.
EOF
  exit 1
fi

mkdir -p "$state_dir"
chmod 700 "$state_dir"
touch "$log"
chmod 600 "$log"
# exe-setup.service already sends stdout to the journal; tee also keeps local recovery logs.
exec > >(tee -a "$log") 2>&1
printf 'incomplete %s\n' "$(date -u +%FT%TZ)" > "$state_dir/status"
SECONDS=0

echo 'Starting custom Shelley first-boot provisioning'
[[ "$(id -u)" != 0 ]] || { echo 'must run as a non-root user' >&2; exit 1; }
# exeuntu currently identifies as Ubuntu; reject other images rather than guessing.
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu ]] || { echo 'this installer supports exe.dev Ubuntu Linux only' >&2; exit 1; }

required=(git curl jq sha256sum systemctl sudo)
for command_name in "${required[@]}"; do
  command -v "$command_name" >/dev/null || { echo "missing required command: $command_name" >&2; exit 1; }
done
sudo -n true
if ! command -v tmux >/dev/null; then
  echo 'Installing required tmux package'
  sudo -n apt-get update
  sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y tmux
fi
command -v tmux >/dev/null || { echo 'tmux installation did not provide tmux' >&2; exit 1; }
sudo -n test -x "$dest" || { echo "expected exe.dev Shelley binary is missing: $dest" >&2; exit 1; }

mkdir -p "$HOME/.config/shelley"
echo 'Cloning official Shelley and selecting fork/custom'
git clone --origin origin "$origin_url" "$checkout"
git -C "$checkout" fetch origin --tags
git -C "$checkout" remote add fork "$fork_fetch"
git -C "$checkout" remote set-url --push fork "$fork_push"
git -C "$checkout" fetch fork --tags
git -C "$checkout" switch --create custom --track fork/custom
# GitHub-linked owner identity: AI assistance belongs in prose, not CLA trailers.
git -C "$checkout" config --local user.name 'Swaroop CH'
git -C "$checkout" config --local user.email 'swaroop@swaroopch.com'
head_commit="$(git -C "$checkout" rev-parse HEAD)"
remote_commit="$(git -C "$checkout" rev-parse refs/remotes/fork/custom)"
[[ "$head_commit" == "$remote_commit" ]] || { echo 'custom checkout is not the fetched fork/custom head' >&2; exit 1; }

work_dir=''
install_tmp=''
cleanup() {
  [[ -z "$install_tmp" ]] || sudo -n rm -f -- "$install_tmp"
  [[ -z "$work_dir" ]] || rm -rf -- "$work_dir"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

# Fast path: install the newest CI-published build on custom's first-parent
# history. CI publishes only after the same tests as the source path pass, and
# uploads the checksum after the binary, so a missing checksum means "no build".
# Any failure here returns 1 and falls back to building from source.
try_prebuilt() {
  if [[ "${SHELLEY_PREBUILT:-1}" == 0 ]]; then
    echo 'Prebuilt binary disabled by SHELLEY_PREBUILT=0'
    return 1
  fi
  if [[ "$(uname -m)" != x86_64 ]]; then
    echo "No prebuilt binary for $(uname -m)"
    return 1
  fi
  local -a candidates fetch=(curl --proto '=https' --fail --silent --show-error --location
    --connect-timeout 10 --retry 3 --retry-delay 2)
  local candidate name='' found='' expected actual
  mapfile -t candidates < <(git -C "$checkout" rev-list --first-parent --max-count="$prebuilt_depth" "$head_commit")
  [[ ${#candidates[@]} -gt 0 && "${candidates[0]}" == "$head_commit" ]] || {
    echo 'Could not list custom history for prebuilt lookup'
    return 1
  }
  work_dir="$(mktemp -d "$state_dir/prebuilt.XXXXXXXX")" || return 1
  for candidate in "${candidates[@]}"; do
    [[ "$candidate" =~ ^[0-9a-f]{40}$ ]] || return 1
    name="$prebuilt_asset-$candidate"
    if "${fetch[@]}" --max-time 60 --output "$work_dir/$name.sha256" "$prebuilt_url/$name.sha256" 2>/dev/null; then
      found="$candidate"
      break
    fi
    echo "No published prebuilt binary for $candidate"
  done
  [[ -n "$found" ]] || { echo "No prebuilt binary in the last ${#candidates[@]} custom commits"; return 1; }
  expected="$(awk 'NR == 1 { print $1 }' "$work_dir/$name.sha256")"
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || { echo "Malformed checksum file for $name"; return 1; }
  echo "Downloading $prebuilt_url/$name"
  "${fetch[@]}" --max-time 600 --output "$work_dir/$name" "$prebuilt_url/$name" || return 1
  actual="$(sha256sum "$work_dir/$name" | awk '{ print $1 }')" || return 1
  [[ "$actual" == "$expected" ]] || { echo "SHA-256 mismatch for $name: got $actual, want $expected"; return 1; }
  echo "SHA-256 verified: $actual"
  chmod 0755 "$work_dir/$name" || return 1
  "$work_dir/$name" version | jq -e --arg commit "$found" \
    '.customized == true and .commit == $commit' >/dev/null || {
      echo "Prebuilt binary is not customized at $found"
      return 1
    }
  built="$work_dir/$name"
  built_commit="$found"
}

built=''
built_commit=''
if try_prebuilt; then
  source_kind=prebuilt
  if [[ "$built_commit" != "$head_commit" ]]; then
    # Keep the canonical checkout at the exact source of the installed binary;
    # custom stays tracked, so a later manual upgrade sees the newer commits.
    echo "Newest prebuilt build is $built_commit; custom is at $head_commit (CI pending or failed)"
    git -C "$checkout" reset --quiet --hard "$built_commit"
    [[ "$(git -C "$checkout" rev-parse HEAD)" == "$built_commit" ]] || { echo 'checkout reset failed' >&2; exit 1; }
  fi
  echo "Using verified prebuilt binary for $built_commit"
else
  echo 'Falling back to building and testing custom from source'
  source_kind=source
  for command_name in make go uv uvx; do
    command -v "$command_name" >/dev/null || { echo "missing required command: $command_name" >&2; exit 1; }
  done
  mkdir -p "$tools_root"
  node_dir=''
  if command -v node >/dev/null && command -v npm >/dev/null &&
     [[ "$(node -p "process.versions.node.split('.')[0]")" == 24 ]]; then
    node_bin_dir="$(dirname "$(command -v node)")"
    npm_bin="$(command -v npm)"
    echo "Using Node $(node --version) from $node_bin_dir"
  else
    node_dir="$tools_root/node"
    [[ ! -e "$node_dir" ]] || { echo "refusing pre-existing managed Node path: $node_dir" >&2; exit 1; }
    echo "Installing managed Node 24.18.0 under $node_dir"
    uvx nodeenv -n 24.18.0 "$node_dir"
    node_bin_dir="$node_dir/bin"
    npm_bin="$node_bin_dir/npm"
    [[ -x "$node_bin_dir/node" && -x "$npm_bin" ]] || { echo 'managed Node installation failed' >&2; exit 1; }
  fi
  export PATH="$node_bin_dir:$PATH"
  [[ "$(node -p "process.versions.node.split('.')[0]")" == 24 ]] || { echo 'Node 24 is required' >&2; exit 1; }

  package_manager="$(node -p 'require(process.argv[1]).packageManager' "$checkout/ui/package.json")"
  [[ "$package_manager" =~ ^pnpm@[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "unsupported packageManager: $package_manager" >&2
    exit 1
  }
  pnpm_root="$tools_root/pnpm"
  [[ ! -e "$pnpm_root" ]] || { echo "refusing pre-existing managed pnpm path: $pnpm_root" >&2; exit 1; }
  mkdir -p "$pnpm_root"
  "$npm_bin" --prefix "$pnpm_root" install --no-audit --no-fund "$package_manager"
  pnpm_bin_dir="$pnpm_root/node_modules/.bin"
  [[ -x "$pnpm_bin_dir/pnpm" ]] || { echo 'pinned pnpm installation failed' >&2; exit 1; }
  export PATH="$pnpm_bin_dir:$PATH"
  export GOTOOLCHAIN=auto CI=true PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
  {
    echo '# Source this file to recover the first-boot build tool PATH.'
    # Keep the caller's ambient PATH after the two pinned tool directories.
    # shellcheck disable=SC2016
    printf 'export PATH=%q:%q:"$PATH"\n' "$pnpm_bin_dir" "$node_bin_dir"
    echo 'export GOTOOLCHAIN=auto'
  } > "$tools_env"
  chmod 600 "$tools_env"
  echo "Build tool recovery environment: $tools_env"
  echo "Node: $(node --version); pnpm: $(pnpm --version); Go: $(go version)"

  (
    cd "$checkout/ui"
    pnpm install --frozen-lockfile
    pnpm run type-check
    pnpm run type-check:vue
    pnpm run lint
    pnpm test
  )
  make -C "$checkout" build-custom
  (
    cd "$checkout"
    go test ./server -parallel 1
  )

  # Builds and tests may generate ignored files, but must not alter tracked source or the stamped HEAD.
  git -C "$checkout" diff --quiet
  git -C "$checkout" diff --cached --quiet
  [[ "$(git -C "$checkout" rev-parse HEAD)" == "$head_commit" ]] || {
    echo 'checkout HEAD changed during validation' >&2
    exit 1
  }

  built="$checkout/bin/shelley"
  built_commit="$head_commit"
fi

[[ -x "$built" ]] || { echo "custom build did not produce $built" >&2; exit 1; }
"$built" version | jq -e --arg commit "$built_commit" \
  '.customized == true and .commit == $commit' >/dev/null || {
    echo 'built binary is not customized at the checked-out commit' >&2
    exit 1
  }

echo "Validation passed; atomically installing $dest"
sudo -n install -d -m 0755 "$backup_dir"
backup="$(sudo -n mktemp "$backup_dir/shelley.XXXXXXXX")"
sudo -n cp --preserve=mode,ownership -- "$dest" "$backup"
install_tmp="$(sudo -n mktemp '/usr/local/bin/.shelley.new.XXXXXXXX')"
sudo -n cp -- "$built" "$install_tmp"
sudo -n chown --reference="$dest" "$install_tmp"
sudo -n chmod --reference="$dest" "$install_tmp"
sudo -n mv -- "$install_tmp" "$dest"
install_tmp=''
echo "Previous binary backed up at $backup"

# Do not alter the vendor units. An inactive service remains socket-activated.
sudo -n systemctl try-restart shelley.service
marker_tmp="$state_dir/.success.$$"
printf 'success commit=%s completed=%s source=%s\n' "$built_commit" "$(date -u +%FT%TZ)" "$source_kind" > "$marker_tmp"
mv "$marker_tmp" "$marker"
printf 'success %s\n' "$built_commit" > "$state_dir/status"
echo "Provisioning complete at commit $built_commit ($source_kind) in ${SECONDS}s"
