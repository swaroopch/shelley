#!/usr/bin/env bash
# Minimal exe.dev first-boot loader. The downloaded installer performs all checks.
set -euo pipefail

readonly url='https://raw.githubusercontent.com/swaroopch/shelley/custom/scripts/provision-exe-vm.sh'
tmp="$(mktemp "${TMPDIR:-/tmp}/shelley-provision.XXXXXXXX")"
cleanup() { rm -f -- "$tmp"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

curl --fail --silent --show-error --location --output "$tmp" "$url"
bash "$tmp" --first-boot
