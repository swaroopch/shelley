# This fork's customization workflow

## Branches

- `origin/main` is official `boldsoftware/shelley`; `fork/main` is its
  fast-forward-only mirror on `swaroopch/shelley`.
- `file-name-completion` is the upstream-facing feature branch. It contains only
  the feature, tests, and [usage documentation](FILE_COMPLETION.md), not this
  fork's maintenance scripts or deployment notes. Use it as the head of a PR
  targeting `boldsoftware/shelley:main`.
  The prepared PR description, including an implementation-independent
  recreation prompt, is tracked in [FILE_COMPLETION_PR.md](FILE_COMPLETION_PR.md).
  The VM's GitHub integration permits Git pushes but rejects PR-creation API
  POSTs as read-only (HTTP 403). The owner submitted the feature as
  [upstream PR #280](https://github.com/boldsoftware/shelley/pull/280).
  Keep this submission record on `custom`, not on the upstream feature branch.
- `mobile-keyboard-input` is a separate upstream-based branch for the Android
  keyboard covering the composer. It opts into native layout-viewport resizing
  instead of adding JS keyboard-height guesses or a second resize mechanism.
  Its implementation, regression tests, and physical-device checklist live on
  that branch in `MOBILE_KEYBOARD_INPUT.md`. The owner confirmed on Android
  Chrome that the keyboard leaves the full input visible and approved the fix.
  It is enabled in `.shelley-features`; the integration gate covers keyboard
  viewport policy/layout, desktop composer alignment, and file completion
  together. New-VM first-boot builds consume the tested integration branch.
  Updating the existing main service still requires separate deployment approval.
  A predictable-only preview runs in tmux `shelley-keyboard-preview` on port
  8012 with a separate temporary database. Recreate it from this branch using
  `make build-custom` and `bin/shelley -predictable-only -db /tmp/shelley-keyboard-preview.db serve -port 8012 -socket none`
  (choose a fresh DB path if that path already exists). Integration and
  deployment remain separate steps; do not infer installation from a Git merge.
- `custom` is the tested integration branch: upstream plus the feature branches
  listed in [.shelley-features](.shelley-features), plus fork-specific maintenance.
  It preserves merge history. **Never rebase or force-push `custom`.**

`origin` deliberately remains the official repository for Shelley's build
metadata. `fork` uses the exe.dev GitHub integration for pushes on this VM.

## Git identity and CLA attribution

Use the owner's GitHub-linked identity for this fork's commits:

```sh
git config --local user.name 'Swaroop CH'
git config --local user.email '42988+swaroopch@users.noreply.github.com'
```

These repository-local settings are shared by its worktrees. The first-boot
installer sets them on new clones; reapply them when recovering a checkout.
The numeric GitHub account ID and login were verified from the public profile.
Do not override this identity with `Shelley` or append a fictitious Shelley
`Co-authored-by` identity. Acknowledge AI assistance in ordinary commit prose.
This agent environment can inject a Shelley co-author trailer into ordinary
commits even when the author config is correct. Inspect the final commit
metadata before publishing upstream; if needed, recreate the unpublished
commit with `git commit-tree`, preserving its tree and parents but correcting
its message/identity. Repo-local config alone does not prevent injected trailers.
CLA acceptance/signing is the owner's action, not an agent's.

PR #280's CLA bot could not resolve the original `shelley@localhost` author
and `shelley@exe.dev` co-author addresses. The metadata-only correction recreates
the three feature commits with the identity above, retaining every tree and
upstream parent, removing the unresolvable co-author trailers, and preserving
AI-assistance disclosure in prose:

| Original commit | Corrected commit |
| --- | --- |
| `76d6a62` | `8078c46` |
| `2b3395e` | `dc8fbc3` |
| `be3cade` | `058df5e` |

Publish this correction only to `file-name-completion`, using an explicit
`--force-with-lease=refs/heads/file-name-completion:be3cade10faa0478e51dc120788c85a647135d5a`.
Never force-push or rewrite `custom`. The original commits remain recoverable
from its preserved integration history. Subsequent integration can merge the
corrected feature history normally; verify that this introduces no source diff.
If the branch has moved, stop and inspect rather than weakening the lease or
overwriting another contributor's work. A byte-identical tree does not imply
CLA acceptance: inspect the PR bot's new result after pushing.

## Path reference convention

Keep **JSON-escaped double quotes**, not Markdown backticks, around paths
inserted by `@` completion. This is the user's agreed preference for both
files and folders: it clearly delimits spaces and consistently escapes quotes,
backslashes, and unusual characters. Folder paths retain their trailing `/`.
These are prompt-text references, not attachments, automatic reads, or a
promise of shell-safe quoting. Do not change to backticks just for presentation.
The implementation and tests live on `file-name-completion`; restoring `custom`
restores this convention without any additional VM settings.

## New VMs: first-boot installation

**Decision:** use exe.dev's documented account default `dev.exe new.setup-script`
with the standard exeuntu image, rather than maintain a custom image or grant
repository write access to every VM. The hook installs the current public
`custom` branch once, after building and testing it. It does not create another
branch-sync writer or enable an ongoing binary-upgrade timer. Existing VMs
still require explicit upgrade approval; first-boot installation on new VMs is
pre-authorized by enabling this account default.

The implementation is tracked here:

- `scripts/exe-first-boot.sh`: small first-boot loader (under exe.dev's 10 KiB
  limit), downloaded source is executed only after a successful HTTP fetch.
- `scripts/provision-exe-vm.sh`: fresh-VM installer, dependency setup, canonical
  checkout, customized build, tests, backup, and atomic binary replacement.
- `scripts/configure-exe-defaults.sh`: owner-run account activation helper. It
  backs up the previous value, refuses to overwrite nonempty unrelated setup,
  and verifies the value after writing it.

New VMs fetch the public fork without credentials. `origin` remains official;
`fork` has a public fetch URL and an integration-backed push URL. A GitHub grant
is needed only if that VM will push or take over the integration coordinator.
No credentials, config, or conversation database are copied between VMs.
The canonical checkout and completion marker prevent the installer from
silently upgrading or overwriting an already-customized working VM.

This setup trusts code published on `swaroopch/shelley:custom`; repository write
access therefore also controls future provisioning. Installation needs network
access and build time. A failed build/test leaves the existing Shelley binary
in place and reports an error rather than pretending provisioning succeeded.

### Activate the account default (owner's workstation)

Git commits do **not** activate an exe.dev account setting. This VM has no
owner SSH identity or forwarded agent, so activation must be performed from an
authenticated workstation. No secret needs to be supplied to Shelley:

```sh
curl -fsSL https://raw.githubusercontent.com/swaroopch/shelley/custom/scripts/configure-exe-defaults.sh -o /tmp/configure-shelley-defaults.sh
bash /tmp/configure-shelley-defaults.sh --apply
```

The helper treats the exact `(not set)` marker from a **successful** lobby read
as an absent default, keeping that raw response in the backup. It still refuses
read/authentication errors, unexpected nonempty output, and real setup scripts
(including scripts that merely mention `(not set)`). If the
lobby reports an unset key as an error, first verify that it is genuinely unset
(not an authentication failure). Then the documented manual activation is:

```sh
curl -fsSL https://raw.githubusercontent.com/swaroopch/shelley/custom/scripts/exe-first-boot.sh -o /tmp/shelley-first-boot.sh
ssh exe.dev defaults write dev.exe new.setup-script < /tmp/shelley-first-boot.sh
ssh exe.dev defaults read dev.exe new.setup-script > /tmp/shelley-first-boot-confirmed.sh
awk '{ print }' /tmp/shelley-first-boot.sh > /tmp/shelley-first-boot-normalized.sh
awk '{ print }' /tmp/shelley-first-boot-confirmed.sh > /tmp/shelley-first-boot-confirmed-normalized.sh
cmp /tmp/shelley-first-boot-normalized.sh /tmp/shelley-first-boot-confirmed-normalized.sh
```

Read-back omits the final LF even when the script was written with one. The
helper therefore compares copies with a final line terminator, while preserving
raw backups. It does **not** ignore other whitespace, extra blank lines, CRLF
changes, or changed commands. The same comparison recognizes an already-active
loader without rewriting the setting. The owner confirmed activation by
comparing the proposed and read-back loaders: only that harmless final LF
was missing. Account configuration remains external state; re-read it when
recovering or making further changes rather than assuming Git alone proves it.

Do not overwrite an existing default to use this shortcut: review and compose
its behavior with this loader first, preserving a protected local backup.
The setting applies to future VMs whose image runs the exeuntu setup hook;
it does not retrofit existing VMs or arbitrary custom images. An explicit
per-VM setup script may override it. To try it for one new VM before changing
the account default, pipe this loader to `ssh exe.dev new --setup-script /dev/stdin`.

After creation, inspect `journalctl -u exe-setup.service`, `shelley version`,
and the canonical checkout. The installer also keeps
`~/.local/state/shelley-provision/provision.log`, a `status` file, and a
`success` marker naming the installed commit. Its `tools.env` records the
Node/pnpm build PATH; source it before later manual builds when those tools
were installed privately. Managed Node is pinned to 24.18.0; an existing Node
24 installation is reused. pnpm is pinned by the checked-out `ui/package.json`,
and Go's automatic toolchain selection follows `go.mod`.

A loader/network failure can be retried through `exe-setup.service`. If the
installer already created its canonical checkout, it deliberately refuses a
blind retry: inspect the log and use the manual recovery/upgrade procedure
below, preserving that checkout and any work. A success marker makes subsequent
installer invocations a no-op, not an implicit upgrade.

On the owner's workstation,
`ssh exe.dev defaults read dev.exe new.setup-script` verifies the account
configuration. Clear the default with
`ssh exe.dev defaults delete dev.exe new.setup-script`, or restore a previous
script with the documented `defaults write` stdin form. Neither action changes
already provisioned VMs.

Sources: [exe.dev customization](https://exe.dev/docs/customization.md),
[new VM options](https://exe.dev/docs/cli-new.md), and the
[exeuntu setup service](https://github.com/boldsoftware/exeuntu/blob/main/exe-setup.service).

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
