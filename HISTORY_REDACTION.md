# One-time PR screenshot history redaction

The owner explicitly authorized a one-time exception to the no-rewrite rule
for `custom` to replace the historical, unblurred **before** screenshot with the
blurred image already displayed in upstream PR #281. The feature branches never
contained these image assets and must not be rewritten for this cleanup.

## Scope and limitations

- Replace only the original before-image blob in reachable `custom` history.
  Preserve code, merge topology, empty commits, upstream/feature commits, and
  original author/committer metadata. Correct historical screenshot URLs in the
  PR draft to point at the sanitized asset commit.
- Keep the original history only in a protected local recovery bundle, outside
  Git. Never publish an archive/backup branch containing the original image.
- This does not erase GitHub caches, already-known commit URLs, third-party
  clones, or other appearances of the hostname (such as historical Git author
  addresses). Do not claim internet-wide deletion or complete anonymization.
- Updating a tracked PR draft does not edit the upstream PR. Its body must be
  updated separately by an authorized GitHub user if API writes remain blocked.
- Do not replace the running binary or restart the main service. Its embedded
  pre-rewrite commit remains useful with the private commit map; verify that
  deployed application source is identical to the rewritten counterpart.

## Procedure and recovery

1. Stop both `shelley-custom-sync.timer` and `shelley-custom-sync.service`.
   Ensure all affected worktrees are clean; never discard another user's work.
2. Save a private `git bundle --all`, public/local ref snapshots, running-version
   receipt, and the approved blurred PNG under a mode-0700 run directory in
   `~/.local/state/shelley-history-redaction/`. Keep commit maps, filter inputs,
   and verification receipts there too. This directory is VM-local and contains
   the original image; a separate private backup is needed for disaster recovery.
3. Publish this authorization/procedure record with a normal fast-forward push
   before relying on the exception. Record the resulting remote `custom` tip
   privately as the exact lease for the later force-push.
4. Work in an isolated, single-branch bare clone using `git-filter-repo` 2.47.0.
   Limit filtering to the first image commit's parent through `custom`. Use
   `--prune-empty never --prune-degenerate never --preserve-commit-hashes`.
   First replace the original image blob with the approved blurred bytes; then
   replace historical screenshot URLs with URLs at the sanitized first asset
   commit. Preserve maps from both passes rather than assuming their format.
5. Before publishing, verify each rewritten commit against its original:
   parent order/count and metadata preserved; only the before-image and PR draft
   screenshot links may change. Require all feature branch objects unchanged,
   the original PNG blob absent from reachable `custom` objects, and all historical
   before-image versions equal to the approved blurred PNG. Validate the candidate
   with the normal integration gate from a separate worktree, using official
   Shelley as `origin`. The live service remains untouched.
6. Recheck every published branch/tag against the saved snapshot. Push only
   `custom`, with `--force-with-lease=refs/heads/custom:<recorded-old-tip>`.
   If the lease fails, stop and inspect; never weaken it to a blind force-push.
7. Fetch the sanitized tip and realign the clean canonical `custom`, maintenance
   worktree, and owned sync workspace with `reset --keep`/detached checkout.
   Do **not** merge or cherry-pick the old `custom` back into sanitized history.
   Check every public ref and local publishable ref for stale image ancestry.
   Old private reflogs/bundles may remain for recovery but must not be pushed.
8. Update the upstream PR's image URLs, or provide its owner the corrected draft
   if API writes are unavailable. Check the original public URL separately and
   report whether GitHub still serves it. Branch cleanup alone proves no purge.
9. Resume the sync timer/service and verify its normal protected integration
   succeeds. Future clones use sanitized `fork/custom`. Existing other clones
   must save local work separately, fetch, and realign to that branch; an ordinary
   pull/merge from stale history can reintroduce the original image.

After this one-time operation, the standard no-rebase/no-force-push rule for
`custom` applies again. Restoring the private bundle is a deliberate emergency
rollback, not routine recovery: publishing its old refs would undo the redaction.
