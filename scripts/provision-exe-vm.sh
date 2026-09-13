#!/usr/bin/env bash
# Provision a fresh exe.dev Ubuntu VM with the published custom Shelley build.
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

echo 'Starting custom Shelley first-boot provisioning'
[[ "$(id -u)" != 0 ]] || { echo 'must run as a non-root user' >&2; exit 1; }
# exeuntu currently identifies as Ubuntu; reject other images rather than guessing.
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu ]] || { echo 'this installer supports exe.dev Ubuntu Linux only' >&2; exit 1; }

required=(git make go uv uvx curl jq systemctl sudo)
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
[[ -x "$built" ]] || { echo 'custom build did not produce bin/shelley' >&2; exit 1; }
"$built" version | jq -e --arg commit "$head_commit" \
  '.customized == true and .commit == $commit' >/dev/null || {
    echo 'built binary is not customized at the checked-out commit' >&2
    exit 1
  }

install_tmp=''
cleanup_install_tmp() {
  [[ -z "$install_tmp" ]] || sudo -n rm -f -- "$install_tmp"
}
trap cleanup_install_tmp EXIT
trap 'exit 1' HUP INT TERM

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
printf 'success commit=%s completed=%s\n' "$head_commit" "$(date -u +%FT%TZ)" > "$marker_tmp"
mv "$marker_tmp" "$marker"
printf 'success %s\n' "$head_commit" > "$state_dir/status"
echo "Provisioning complete at commit $head_commit"
