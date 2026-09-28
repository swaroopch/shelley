feat(ui): add a /skills picker to the prompt composer

## Summary

Add `/skills` to discover a skill and add an explicit activation instruction to
the prompt being composed. Selection edits the draft; it does not send a message
or execute the skill. The user can inspect, edit, or remove the instruction before
sending, and select more than one skill.

- Filter by skill name and description; show source information.
- Select with arrows and Enter/Tab, or by clicking; Escape dismisses the picker.
- Preserve surrounding text, cursor placement, attachments, and normal draft
  persistence. Loading, empty, and error states do not dispatch `/skills`.
- Reuse existing skill discovery for new drafts, including source precedence and
  environment filtering. For existing conversations, read the current post-hook
  system-prompt catalog rather than inventing an out-of-sync list.
- Return metadata only: browsing the picker does not expose instruction bodies
  to the browser or model, invoke a model, execute activation commands, run
  prompt hooks, or create a conversation. Once sent, the model follows the visible instruction using the
  existing activation mechanism; selection itself does not guarantee execution.

This does not add a skill runtime, special message syntax, permission bypass,
new dependencies, or a database migration. It does not interpret OpenCode-specific
frontmatter. New drafts cannot preview the effects of arbitrary system-prompt
hooks without running those hooks; the catalog intentionally uses discovery only.
Hooks that replace a catalog must retain the standalone `<skills>` envelope;
removing that section yields an empty catalog. Guidance and fenced examples are
not treated as skill catalogs.

## Validation

Feature branch:
- Both TypeScript and Vue type checks, plus lint: passed.
- All 73 UI unit-test files: passed.
- `go test -parallel 1 ./...`: passed with Playwright Chromium on PATH.
- Targeted backend catalog/parser tests under `-race`: passed.
- Nine deterministic Playwright browser tests: passed, including actual lazy
  draft promotion and effective-catalog snapshot behavior.
- Independent source review: both reported issues fixed and regression-tested.

The separate `custom` integration must additionally pass
`scripts/validate-custom.sh`, covering fork maintenance tests, the complete suites,
and its combined browser manifest before publication.

## Upstream submission

- Head: `swaroopch/shelley:skills-picker`.
- Base: `boldsoftware/shelley:main`.
- Keep fork operational changes, manifests, this PR draft, and any screenshots
  off the upstream-facing branch. The feature is intended as one focused commit.
- Open the PR using this title/body after the owner reviews the preview. This
  document records a submission plan, not an already-open PR or accepted CLA.
- If upstream advances, rebase only the feature branch with an explicit remote
  lease after testing. Preserve `custom` history; review integration deliberately.
- After upstream lands the feature, remove `skills-picker` from
  `.shelley-features` and review any squash-merge conflicts rather than blindly
  restoring duplicate fork patches.

Implemented with AI assistance; commits use the owner's configured identity.

## Recreation prompt

If you prefer to implement the intent independently rather than reuse this code diff:

```text
Add a /skills picker to Shelley's existing prompt composer. Typing /skills,
including within a draft, opens a searchable catalog of skills available in the
current context. Show names, descriptions, and source information. Filter by name
and description, navigate with arrow keys, select with Enter/Tab or a click, and
dismiss with Escape. Selection replaces only the command fragment with visible,
editable instructions to use the selected skill and load it with its existing
activation command. Keep surrounding text, cursor position, attachments, and
normal draft persistence intact. Allow repeated selections. Never submit, queue,
compact, execute commands, load skill bodies, or call a model merely by selecting
a skill. Loading, errors, and no results must not accidentally submit the command.
Reuse Shelley's discovery, precedence, environment filtering, and activation
mechanism. New drafts use their selected working directory; existing conversations
use the skills advertised in their current effective system prompt, including
hook changes. Return metadata only, and invalidate stale asynchronous responses
when context changes. Preserve existing slash, file, and model completion and IME
handling. Avoid special stored message types, new dependencies, and schema changes.
Include deterministic backend, parsing, async-state, and browser regression tests,
including no-send selection, multiple skills, draft preservation, errors, snapshot
consistency, attachment and failed-send behavior, and narrow/mobile layouts.
```
