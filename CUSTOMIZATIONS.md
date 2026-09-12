# This fork's customization workflow

## Branches

- `origin/main` is official `boldsoftware/shelley`; `fork/main` is its
  fast-forward-only mirror on `swaroopch/shelley`.
- `file-name-completion` is the upstream-facing feature branch. It contains only
  the feature, tests, and [usage documentation](FILE_COMPLETION.md), not this
  fork's maintenance scripts or deployment notes. Use it as the head of a PR
  targeting `boldsoftware/shelley:main`.
- `custom` is the tested integration branch: upstream plus the feature branches
  listed in [.shelley-features](.shelley-features), plus fork-specific maintenance.
  It preserves merge history. **Never rebase or force-push `custom`.**

`origin` deliberately remains the official repository for Shelley's build
metadata. `fork` uses the exe.dev GitHub integration for pushes on this VM.

## Automatic integration (VM-side, not GitHub Actions)

The VM user timer is deliberate: the connected exe.dev repository integration
supports authenticated Git fetches and pushes, but an attempt to use its GitHub
Actions administration API returned HTTP 403. This design needs only repository
Git access, not an unsupported endpoint or a broader credential grant.

The `shelley-custom-sync` systemd **user timer** checks every 15 minutes after
its previous run finishes. It requires this Linux exe.dev VM, its user systemd
instance, installed tools, and its GitHub repository integration to remain
available; it does not run while the VM is stopped. The unit files, local state,
caches, and journal are VM-only. Losing the VM stops automation but does not
lose published branch history. The unit templates are in `scripts/systemd/`.

The job runs `scripts/sync-custom.py` in a separate checkout under
`~/.local/state/shelley-sync/`. It never changes the canonical checkout,
replaces `/usr/local/bin/shelley`, or restarts the running service.

Each run:

1. Fetches upstream and the fork; reads the enabled branches from `fork/custom`.
2. Starts a candidate at `fork/custom`, merges enabled features in manifest
   order, then upstream. Features go first so a reviewed upstream conflict
   resolution on a feature branch can be incorporated before merging upstream.
3. Runs integration-script tests, both UI type checks, lint, all UI unit tests,
   a customized build, serial Go tests, and the browser regressions listed in
   [.shelley-browser-tests](.shelley-browser-tests).
4. Checks that the remote inputs have not changed during validation, then
   atomically pushes the tested `custom` and fast-forward-only upstream mirror.

No changes means no build. A conflict, failed test, missing feature, dirty job
checkout, or concurrent remote change stops publication. The last tested remote
branch remains intact. An unchanged failing input is not repeatedly rebuilt;
fix the relevant branch, or use `--retry` when deliberately retrying a transient
failure. Failures and skip reasons are recorded in the user journal and the
state directory; **there is no automatic conflict resolution or deployment**.

Inspect or pause the job:

```sh
systemctl --user status shelley-custom-sync.timer shelley-custom-sync.service
journalctl --user -u shelley-custom-sync.service -n 100
systemctl --user disable --now shelley-custom-sync.timer
```

To run a check immediately: `systemctl --user start shelley-custom-sync.service`.
To retry unchanged failed inputs, run the unit's `ExecStart` command manually
with `--retry` appended (inspect it with `systemctl --user cat shelley-custom-sync.service`).

## Adding a feature

Develop in a separate worktree based on official main, not on `custom`, so the
branch does not inherit other features or fork-only maintenance. Push it to the
fork, then add its name to `.shelley-features` on `custom` and push that change.
Add relevant browser spec paths to `.shelley-browser-tests`. Future pushes to
enabled features are picked up automatically without changing the manifest.

Removing a manifest entry stops future merges; it does **not** undo already
merged code. Reverts, rebased feature history, upstream squash-merges, and
conflict resolution may need deliberate integration work. Resolve upstream
conflicts on the relevant feature branch (merge `origin/main` there), test, and
push; the next sync can incorporate that reviewed resolution. Do not open an
upstream PR from `custom` or merge `custom` back into a feature branch.

## Upgrading the installed build

The canonical checkout remains `~/.config/shelley/shelley-customization` on
`custom`. Only update it as part of an intentional upgrade:

```sh
git fetch origin main --tags
git fetch fork
git switch custom
git merge --ff-only fork/custom
make build-custom
```

Use `make build-custom`, not `make build`, so a binary self-update cannot erase
the customization. The generic Shelley customization skill's rebase recipe
must not be used for this merge-based fork; use the sync job plus fast-forward
above instead. Changes to the sync runner/validator in the canonical checkout
also update the installed timer's maintenance code and should be reviewed.

A preview must use a separate database, port, and `-socket none`. Installing a
new binary over the primary service still requires explicit approval. The
previous binary is backed up under `/usr/local/lib/shelley-backups/` on this VM.

## Disaster recovery (replacement exe.dev Linux VM)

1. Provision a replacement exe.dev VM. Reconnect its GitHub repository
   integration with read-write access to `swaroopch/shelley`, and configure the
   GitHub App installation to include that repository. Grant access again on
   the new VM: source-VM tokens cannot be recovered or copied, and credentials
   must never be committed. Do not request unrelated repository or account
   permissions.
2. Install Git, `make`, `tmux`, `uv`, Node 24, the Go version declared by
   `go.mod`, Corepack, and the Playwright Chromium OS dependencies. Install
   `uv` specifically as `~/.local/bin/uv`: the committed service has that
   literal `ExecStart` path and adds `~/.local/bin` to `PATH`. Verify that all
   tools are reachable with the service's committed `PATH` (inspect the unit
   template); an interactive shell's extra paths are not inherited by the timer.
3. Clone from official Shelley so `origin` remains official, then add the
   integration-backed fork remote and track the published branch:

   ```sh
   mkdir -p ~/.config/shelley && git clone https://github.com/boldsoftware/shelley.git ~/.config/shelley/shelley-customization
   cd ~/.config/shelley/shelley-customization
   git remote add fork https://github.int.exe.xyz/swaroopch/shelley.git
   git fetch fork --tags
   git switch -c custom --track fork/custom
   ```

   These are fresh-clone commands. If either checkout, remote, or branch already
   exists, inspect and reuse it; never delete it, reset it, or force-discard work
   merely to reproduce this layout.
4. Verify tool versions, activate the repository-pinned pnpm through Corepack,
   install locked UI dependencies, and install Chromium plus its Linux runtime
   dependencies:

   ```sh
   git --version; make --version; tmux -V; ~/.local/bin/uv --version
   awk '/^go / { print "required Go " $2; exit }' go.mod; go version
   node --version                            # Node must be v24.x
   mkdir -p "$HOME/.local/bin"
   corepack enable --install-directory "$HOME/.local/bin" pnpm
   export PATH="$HOME/.local/bin:$PATH"
   corepack prepare "$(node -p "require('./ui/package.json').packageManager")" --activate; pnpm --version
   cd ui && pnpm install --frozen-lockfile && pnpm exec playwright install --with-deps chromium
   cd ..
   ```
5. Restore the user units under their literal names. If unattended user units
   must survive logout, an administrator must first run
   `sudo loginctl enable-linger "$USER"`. Then start the service once; enable the
   timer only after that run succeeds:

   ```sh
   install -Dm644 scripts/systemd/shelley-custom-sync.service "$HOME/.config/systemd/user/shelley-custom-sync.service"
   install -Dm644 scripts/systemd/shelley-custom-sync.timer "$HOME/.config/systemd/user/shelley-custom-sync.timer"
   systemctl --user daemon-reload; systemctl --user start shelley-custom-sync.service
   systemctl --user status shelley-custom-sync.service
   systemctl --user enable --now shelley-custom-sync.timer
   ```
6. Verify repository wiring, local tests, the journal, and scheduling:

   ```sh
   git remote -v; git status --short --branch; git branch -vv
   ~/.local/bin/uv run --no-project scripts/test-sync-custom.py
   journalctl --user -u shelley-custom-sync.service -n 100
   systemctl --user status shelley-custom-sync.timer; systemctl --user list-timers shelley-custom-sync.timer
   ```

The sync checkout, state markers, dependency caches, and browser downloads are
rebuildable from Git and need no backup. Git does **not** contain existing
conversations, settings, secrets, or the deployed binary; preserve anything
needed from those categories in separate protected backup storage. Recovery of
this automation does not by itself restore or deploy the running Shelley app.

## Verification

Run `uv run --no-project scripts/test-sync-custom.py` for isolated Git fixtures
(no network and no sleeps). The production gate is `scripts/validate-custom.sh`;
its only argument is the separate candidate checkout. Serial Go execution is
intentional: the upstream reflection-cache test has failed under the default
parallel suite on this VM.
