## Summary

Add `@` file and folder name completion to the chat composer, making it easier to reference local paths without copying them from a terminal or file browser.

- Search relative to the conversation's working directory, or the selected directory for a new conversation/draft.
- Offer keyboard and mouse selection; insert a JSON-escaped, double-quoted absolute path. Folders have an icon and retain their trailing `/`.
- Support fuzzy name searches, quoted queries containing spaces, and explicit paths. An exact folder path offers the folder itself; a trailing slash browses its contents.
- Insert prompt text only: no automatic file reads, attachments, or folder expansion.
- Debounce/cancel searches, reject stale results, preserve surrounding text, and leave normal input usable on empty results/errors.

### Implementation and scope

Reuses the name-only `findFiles` API with opt-in `include_dirs=true` and `is_dir` result metadata. Existing callers keep file-only behavior. Adds bounded directory discovery, ignored-directory handling, empty-directory support, and submodule deduplication, with backend, frontend, and browser coverage.

This PR is from `swaroopch:file-name-completion`. It contains only the feature, tests, and usage/API documentation—not the fork's provisioning scripts, integration timer, or deployment configuration.

## Recreation prompt (intent, independent of this implementation)

If you would rather implement this using your own architecture or coding agent, the following is a self-contained specification. Reusing this diff is not required.

```text
Add file and folder name completion to Shelley's chat message composer.

Goal: let a user reference a local file or folder while composing a message,
without switching to a file browser or manually copying an absolute path.
This is a text-reference feature, not an attachment or automatic file-reading
feature.

Desired behavior:
1. Typing @ at a word/token boundary opens a file/folder suggestions popup.
   Do not trigger for email addresses or in shell-command mode.
2. Search names within the active conversation's working directory. For a
   new conversation or draft, use the currently selected directory. Handle
   directory/context changes without showing stale suggestions.
3. Support fuzzy name queries and quoted queries containing spaces, e.g.
   @readme and @"My Notes. Unquoted queries stop at whitespace or prose
   punctuation. Include empty folders, distinguish folders visually, and
   show their trailing slash.
4. Support explicit relative and absolute paths. An exact folder path such
   as @./docs offers that folder; @./docs/ browses its contents. Resolve
   insertions against the actual search directory, including searches that
   move outside the initial working directory.
5. Up/Down changes the highlighted result; Enter or Tab accepts it; clicking
   or tapping accepts it; Escape dismisses without blurring the composer.
   Preserve Shift+Enter for a newline and do not interfere with IME input.
6. Replace only the active @ token around the cursor, preserving surrounding
   message text. Insert the server-resolved absolute path in double quotes,
   using JSON escaping for quotes, backslashes, and unusual characters.
   Folder references retain a trailing /. Do not use Markdown backticks.
   Do not claim this quoting is shell-safe for arbitrary pasted commands.
7. Inserting a reference must not read or attach contents, recursively expand
   folders, send a message, or switch the conversation's working directory.
8. Debounce requests, cancel superseded work, and discard out-of-order
   results. Empty results and errors must leave normal typing and sending
   available. Respect ignored directories and bound filesystem traversal.
9. Keep the existing editor file finder and other file-only consumers
   unchanged; directory results should be explicitly opt-in.
10. Fit the existing UI on desktop and mobile. Add tests for token boundaries,
    cursor-local replacement, escaping/spaces, keyboard and pointer behavior,
    cancellation/context changes, errors, empty/ignored/nested directories,
    explicit paths, and preservation of existing file-only search behavior.

Choose whatever internal implementation best fits upstream Shelley. Preserve
these user-facing semantics and avoid unrelated maintenance/deployment changes.
```

## Validation

Rechecked on the feature branch:
- Both UI type checks and lint passed.
- UI unit suite: 58 test files passed.
- `make build-custom` passed.
- Finder-focused Go tests passed.
- `go test ./server -parallel 1` passed on recheck. The first run hit the existing `TestReflectionProbeCachedAndCollapsed` singleflight/cache flake (two probes instead of one); no unrelated test code was changed.
- `file-completion.spec.ts`: 24 browser checks passed across desktop and mobile Chromium, using the predictable model, a temporary database, and a separate test server.
- Clean test merge with current upstream `main`.
