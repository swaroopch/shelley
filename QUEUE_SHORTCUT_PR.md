feat(ui): queue the composer's message with Alt+Enter

Queueing a follow-up message for a busy agent was reachable only from the send split-button's dropdown. Bind Alt+Enter to it, so the composed message waits for the current turn instead of interrupting it.

Alt+Enter is free inside a page: no browser binds it there (Firefox reserves it only in the address bar), and a textarea's default action for it is nothing at all — measured in Chromium and Firefox — so no native behavior is lost. It previously fell through the composer's Enter branch to an undocumented "send".

- Queue while the agent is working; send normally when it is idle, matching what the send button's plain arrow already promises.
- Preview it: holding Alt shows the queue clock icon and "Queue after agent finishes" on the send button, and alt+click on Send does the same as the key.
- Shift+Enter keeps inserting newlines, and Cmd/Ctrl+Enter keeps compacting and sending. `isAltEvent` requires bare Alt, so AltGr (Ctrl+Alt) layouts are unaffected.
- The dropdown row shows the shortcut hint.

## Validation

- Both UI type checks and lint passed; all UI unit-test files passed (83).
- New `ui/e2e/queue-shortcut.spec.ts` passed in Chromium and Firefox.
- Existing composer browser regressions passed locally: `compact-send-shortcut`, `queue-messages`, `message-input-alignment`, `mobile-keyboard-input` (22 tests).
- Playwright specs are not part of CI (`if: false` in `.github/workflows/test.yml`), so the browser runs above were local.

## Recreation prompt

If you prefer to implement the intent independently rather than use this code diff:

```text
In Shelley's prompt composer, bind Alt+Enter (⌥↵ on mac) to the send split-button's "Queue after agent finishes" action, which is currently reachable only from its dropdown. While the agent is working in an existing conversation, Alt+Enter must queue the composed message (the chat request carries queue: true) and clear the composer; when nothing is running it must behave like Enter and send immediately, since there is nothing to wait for. Holding Alt must preview the action on the send button: show the queue clock icon and an accessible label naming the queue action, and make alt+click on Send do the same as the key. Require bare Alt: AltGr reports as Ctrl+Alt on Windows/Linux layouts, and Cmd/Ctrl combinations must keep their existing meanings (Cmd/Ctrl+Enter stays compact-and-send). Do not take Shift+Enter, which is the composer's newline, and keep the dropdown's keyboard hint in sync with the binding. Acceptance criteria: a browser test queues a message with Alt+Enter while the agent is busy (queued badge appears, composer clears, the message runs only after the turn ends), Alt+Enter sends when the agent is idle, Shift+Enter still inserts a newline while the agent works, and holding Alt previews the queue label on the send button.
```

Implemented with AI assistance.
