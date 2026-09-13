1. Never add sleeps to tests.
2. Brevity, brevity, brevity! Do not do weird defaults; have only one way of doing things; refactor relentlessly as necessary.
3. If something doesn't work, propagate the error or exit or crash. Do not have "fallbacks".
4. Do not keep old methods around for "compatibility"; this is a new project and there
   are no compatibility concerns yet.
5. The "predictable" model is a test fixture that lets you specify what a model would say if you said
   a thing. This is useful for interactive testing with a browser, since you don't rely on a model,
   and can fabricate some inputs and outputs. To test things, launch shelley with the relevant flag
   to only expose this model, and use shelley with a browser.
6. Build the UI (`make ui` or `cd ui && pnpm install && pnpm run build`) before running Go tests so `ui/dist` exists for the embed.
7. **Always run `cd ui && pnpm run type-check && pnpm run type-check:vue` after modifying any `.ts`, `.tsx`, or `.vue` file.** Fix all errors before committing. Run linting with `pnpm run lint`.
8. Run Go unit tests with `go test ./server` (or narrower packages while iterating) once the UI bundle is built.
9. To programmatically type into the message input (e.g., in browser automation), set the
   value via the native setter and dispatch an `input` event so Vue's v-model picks it up:
   ```javascript
   const input = document.querySelector('[data-testid="message-input"]');
   const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
   nativeInputValueSetter.call(input, 'your message');
   input.dispatchEvent(new Event('input', { bubbles: true }));
   ```
   Simply setting `input.value = '...'` won't work because the framework won't detect the change.
10. Commit your changes before finishing your turn.
11. If you are testing Shelley itself, be aware that you might be running "under" shelley,
  and indiscriminately running pkill -f shelley may break things.
12. To test the Shelley UI in a separate instance, build with `make build`, then run on a
    different port with a separate database:
    ```
    ./bin/shelley -config /exe.dev/shelley.json -db /tmp/shelley-test.db serve -port 8002
    ```
    Then use browser tools to navigate to http://localhost:8002/ and interact with the UI.
13. NEVER use alert(), confirm(), or prompt(). Use proper UI components like tooltips, modals, or toasts instead.
14. SQL migrations and frontend changes require rebuilding the binary (`make build` or `go generate ./... && cd ui && pnpm run build`).
15. Tool changes and UI tool widget updates go hand in hand. When you add, rename, remove, or
    restructure a tool (in `claudetool/`), you MUST update the UI components that render it:
    - `ui/src/vue/components/CoalescedToolCall.vue` (`TOOL_COMPONENTS` map) and the tool
      components under `ui/src/vue/components/tools/`
    - `ui/src/vue/components/tools/BrowserTool.vue` (if the tool is a browser action — this component
      reads the `action` field from the input and dispatches to the right sub-component)
    - `llm/predictable/predictable.go` (the "tool smorgasbord" demo response)
16. Never surface a bare "default" (or "Default") in the UI without saying what the default
    actually resolves to. A control that reads `effort: default` tells the user nothing. When
    the concrete value is knowable (usually it is; the server sends it), prefer to just
    pre-select the real value — e.g. show and select `medium`, don't add a separate `default`
    entry that duplicates one of the real choices. Only keep a `default` sentinel when the
    concrete value is genuinely unknowable; even then, spell it out if you can (e.g. `Default
    (on)` for a boolean toggle).

17. Record every fork-specific operational or architecture decision, its rationale, and its
    recovery requirements in tracked documentation or scripts. Commit and push that record to
    `custom` before relying on it; never leave required knowledge only in agent/private memory or
    in VM-only configuration. Keep secrets out of Git and document their separate recovery needs.

## This fork's feature integration

- Read `CUSTOMIZATIONS.md` before changing branches, upgrading, or deploying.
- Keep the canonical checkout on `custom`. Develop upstream-facing features in
  separate worktrees based on `origin/main`; never merge `custom` into them.
- `origin` is official Shelley; `fork` is the user's fork. The enabled feature
  list is `.shelley-features`. The VM timer merges upstream/features into a
  separate tested candidate and pushes `fork/custom`; it does not deploy.
- Do not rebase or force-push `custom`, including when the generic customization
  skill suggests rebasing. Preserve its merge history; intentionally upgrade
  the canonical checkout with `git fetch fork` and `git merge --ff-only fork/custom`.
- Test and build with `make build-custom`. Never replace the running binary or
  restart the main service without explicit approval.
- Use this fork's repository-local Git identity (`Swaroop CH`,
  `swaroop@swaroopch.com`). Do not override author/committer
  identity with Shelley or add an unresolvable Shelley co-author trailer.
  Disclose AI assistance in plain prose. Never accept or sign a CLA for the owner.
  This applies to both author and committer on new feature, maintenance, and
  automated merge commits. Inspect raw identities and the complete commit
  message before pushing; a correct `user.email` alone is not sufficient.
  Preserve historical `custom` and upstream commit identities (no history rewrite).
- Follow Conventional Commits 1.0.0 (https://www.conventionalcommits.org/en/v1.0.0/)
  for new commit subjects and PR titles: `type(optional-scope): description`
  (use `!` / `BREAKING CHANGE:` only for actual breaking changes). PR descriptions
  start with the same conventional header, a blank line, and an explanatory body
  with applicable screenshots, recreation prompt, validation, and footers.
  Automated integration merges use `chore(sync): merge <source>`.
  Preserve published `custom` history rather than rewriting old message formats.
- One-time exception: the owner explicitly approved rewriting only `custom`'s
  historical PR screenshot as described in `HISTORY_REDACTION.md`. Preserve code
  and topology, use the exact remote-tip lease, keep backups private, realign
  stale clones, and resume the normal no-rewrite policy after the cleanup.
