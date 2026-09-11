# Local customizations

## `@` filename completion

In the chat composer, type `@` at the start of a word to search filenames in
that conversation's working directory. New conversations and drafts use the
currently selected directory. Search uses the existing name-only `findFiles`
API; no file contents are fetched or attached.

- Type `@readme` to fuzzy-search names, or `@"My Notes` for a query with spaces.
  Quotes also allow punctuation in a query. Unquoted queries stop at whitespace
  or prose punctuation such as commas and parentheses.
- Use Up/Down to select, Enter/Tab to insert, or click a result.
- Escape dismisses without blurring; Shift+Enter still inserts a newline.
- Insertion replaces the token under the cursor with a double-quoted, escaped
  absolute path, preserving surrounding text. Results resolve against the API's
  `search_dir`, including searches rooted outside the conversation directory.
- Searches are debounced and cancelled when the query, directory, conversation,
  or focus changes. Errors and empty results leave normal keyboard input usable.
- Email addresses and shell-mode input do not trigger completion.

Implementation: `ui/src/utils/fileCompletion.ts`,
`ui/src/vue/composables/fileCompletion.ts`, `MessageInput.vue`, and the working
folder prop in `ChatInterface.vue`. No backend or database changes.

## Build and verify

Keep changes committed on `custom`. From this checkout, run `make build-custom`
(not `make build`) so binary self-updates do not discard the customization.

From `ui/`:

```sh
pnpm run type-check
pnpm run type-check:vue
pnpm run lint
pnpm test
pnpm exec playwright test e2e/file-completion.spec.ts
```

From the checkout root, after building the UI: `go test ./server -parallel 1`.
The upstream reflection-cache test can fail in the default parallel suite;
serial execution and the focused file-finder tests pass.

The preview uses a separate database and port. Disable its CLI socket so it
cannot replace the running installation's socket. On this exe.dev VM:

```sh
./bin/shelley -config /exe.dev/shelley.json -db /tmp/shelley-custom-preview.db serve -port 8010 -socket none -banner 'Preview: @ filename completion — separate history'
```

Run the preview in tmux. Do not replace or restart the primary installation
without explicit approval.
