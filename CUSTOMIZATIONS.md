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
  Its upstream PR draft, recreation prompt, and before/after screenshots are
  recorded in [MOBILE_KEYBOARD_INPUT_PR.md](MOBILE_KEYBOARD_INPUT_PR.md). The
  screenshots are cropped to exclude private conversation content and hosted
  on `custom` so they do not add binaries to the upstream feature diff. The
  PR-creation API still rejects POSTs as read-only (HTTP 403); this draft awaits
  owner submission through the pre-filled GitHub compare page.
- `custom` is the tested integration branch: upstream plus the feature branches
  listed in [.shelley-features](.shelley-features), plus fork-specific maintenance.
  It preserves merge history. **Never rebase or force-push `custom`.** The
  completed, one-time screenshot cleanup is recorded in
  [HISTORY_REDACTION.md](HISTORY_REDACTION.md); it is not continuing permission
  to rewrite this branch. Stale clones must realign, not merge old history back.

`origin` deliberately remains the official repository for Shelley's build
metadata. `fork` uses the exe.dev GitHub integration for pushes on this VM.

## Git identity and CLA attribution

Use the owner's explicitly requested identity for this fork's commits:

```sh
git config --local user.name 'Swaroop CH'
git config --local user.email 'swaroop@swaroopch.com'
```

The owner also chose `swaroop@swaroopch.com` as this VM's global Git email
in `~/.gitconfig`. To restore that default, run
`git config --global user.email 'swaroop@swaroopch.com'`.
Repository-local overrides still take precedence; this does not modify the
owner's laptop or other VMs.

These repository-local settings are shared by its worktrees. The first-boot
installer sets them on new clones; reapply them when recovering a checkout.
This applies to **both author and committer** for every new fork commit,
including maintenance, PR assets, and automated integration merges. The sync
runner configures its independent workspace with this identity and explicitly
sets Git's author/committer environment for its Git subprocesses so inherited
variables cannot silently restore a bot identity. Validator subprocesses keep
their own environment; fixture/upstream authors must not be relabeled.
Inspect raw `%an <%ae>` / `%cn <%ce>` and the complete message before publishing,
not just the local `user.email` setting. The identity regression test exercises
conflicting inherited author and committer settings.
The owner explicitly prefers this address over GitHub's no-reply address.
Do not substitute another address; GitHub email verification belongs to the owner.
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

| Original commit | Initial no-reply correction | Owner-email correction |
| --- | --- | --- |
| `76d6a62` | `8078c46` | `3070a52` |
| `2b3395e` | `dc8fbc3` | `9a37f11` |
| `be3cade` | `058df5e` | `1cdbd04` |

The initial correction used a GitHub no-reply address. At the owner's request,
the second correction changes both author and committer emails to
`swaroop@swaroopch.com`, again preserving every source tree and upstream parent.
Publish the owner-email correction only to `file-name-completion`, using an explicit
`--force-with-lease=refs/heads/file-name-completion:058df5e30bed7c6784ad125606224f9a4468835d`.
Never force-push or rewrite `custom`. The original commits remain recoverable
from its preserved integration history. Subsequent integration can merge the
corrected feature history normally; verify that this introduces no source diff.
If the branch has moved, stop and inspect rather than weakening the lease or
overwriting another contributor's work. A byte-identical tree does not imply
CLA acceptance: inspect the PR bot's new result after pushing.

The same metadata-only correction applies to `mobile-keyboard-input`:
`7535f996d7364b204913c52a4b555fd79dcd356e` becomes
`d84cbc232ae6b4a971ed8070381a0d0c3efeb7d1`. Its tree, parent, and original dates
are unchanged; both identities use the owner's email and AI assistance is
acknowledged in prose instead of a fictitious co-author trailer. Publish only
with an explicit lease against that original feature tip. Integration may then
merge the corrected feature histories normally, with no application-code diff.

Previously published `custom` commits retain their original raw metadata. This
is an explicit consequence of preserving its append-only history, not a claim
that every historical email was changed. Never rewrite upstream contributors
or force-push `custom` to repair attribution. The old feature objects remain
recoverable through `custom`, including the hashes used by deployed binaries.
During identity maintenance, pause the sync timer/service; after publishing the
record and fast-forwarding the canonical checkout to the corrected runner,
restart `shelley-custom-sync.timer` and deliberately run the sync service. This
updates source/automation, not the deployed binary or main service.

## Commit and PR message convention

Follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
for new commit subjects and PR titles: `type(optional-scope): description`.
Use `feat` for features, `fix` for bug fixes, and descriptive types such as
`docs`, `test`, or `chore` for other changes. Only use `!` or a
`BREAKING CHANGE:` footer when the change really is breaking.

For PR descriptions, the owner requests the same conventional header followed
by a blank line and an explanatory body. Keep summary, screenshots, recreation
prompt, validation, and any applicable footers; the convention does not require
turning each paragraph into another commit subject. The tracked PR drafts use
this format. A published PR needs a separate authorized update; changing these
drafts does not change its GitHub title or body.

Automated merges use `chore(sync): merge <source>`, with a regression test for
the generated subject. Preserve upstream messages and existing `custom` history.
The pending keyboard PR's single feature commit is corrected from
`d84cbc232ae6b4a971ed8070381a0d0c3efeb7d1` to
`d1833844b318aa8db427bc43c53aae5a9284a334`, with subject
`fix(ui): keep the Android chat input above the software keyboard`. This changes
only the message; source tree, parents, dates, and owner email are preserved.
Publish only to `mobile-keyboard-input` with a lease against the recorded old
tip. No binary deployment is needed for message-format or identity maintenance.

## Maintainer-requested PR rebases

The owner approved rebasing PRs #280 and #281 onto upstream commit
`479414bf8807871196cacd0f10d8a2d729951ad3` to refresh their CLA checks, following
the maintainer's recommendation. This upstream commit includes the maintainer's
addition of `swaroopch` to `.clabot`; the fork does not add itself or accept a CLA.
A successful bot check must be observed separately from a successful Git push.

Only `file-name-completion` and `mobile-keyboard-input` are rebased. Replay the
feature patches without old upstream merge commits, preserve reviewed merge
resolutions by comparing with a clean merge of each old feature tip and the new
upstream, and keep all feature authors/committers at the owner identity. Rewritten
feature subjects follow Conventional Commits. Retain prior bug fixes, double-quoted
path insertion, and the upstream recording UI. Never merge `custom` into a PR.

Before publishing, pause the sync timer/service, save a private Git bundle and
remote-ref snapshot under `~/.local/state/shelley-pr-rebases/`, and rerun both UI
type checks, lint, unit tests, `make build-custom`, serial server tests, and the
feature's browser regressions. Publish both feature refs atomically with explicit
leases against the reviewed remote tips:

- PR #280: `b65b35e5b8bbdb519e9a028966ba2bceea7da500`.
- PR #281: `d1833844b318aa8db427bc43c53aae5a9284a334`.

If either remote moves, stop rather than replacing the lease. Keep `custom`
append-only; after feature publication, resume its normal tested integration
process. Do not update the canonical checkout or deploy as part of a PR rebase.
The original feature commits remain available in preserved `custom` ancestry
and the private bundle. Restore or fix a feature only with a new explicit lease;
never use the bundle to reintroduce pre-redaction `custom` history. Inspect PR
bot results after pushing; CLA acceptance and maintainer approval are separate.

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

The sync service PATH puts the first-boot provisioner's private pnpm and Node
installations ahead of user-local tools. This lets provisioned VMs reuse their
pinned build tools without replacing an owner's unrelated Node installation
(for example, Node 22 in `~/.local/bin`). On recovery, restore those tools with
the provisioner's documented versions, or install Node 24 and the repository's
pinned pnpm in the remaining service PATH. Verify versions using that exact
PATH before starting the job. If `uv` is already installed at
`/usr/local/bin/uv`, satisfy the unit's literal executable path with
`ln -s /usr/local/bin/uv ~/.local/bin/uv` (only when the latter is absent).
Install Playwright's Chromium OS dependencies before the first validation;
the validator downloads the browser into its rebuildable user cache.

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
