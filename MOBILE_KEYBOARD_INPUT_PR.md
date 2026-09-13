fix(ui): keep the Android chat input above the software keyboard

## Summary

Keep the chat input visible above Android Chrome's software keyboard by adding `interactive-widget=resizes-content` to the page's viewport policy.

The app has a full-height layout. When opening the keyboard only shrinks the visual viewport, the textarea can remain underneath the keyboard even while its toolbar is visible. Requesting a layout-viewport resize lets the existing flex layout keep the composer on-screen, without new JavaScript keyboard-height estimates or resize listeners.

This PR contains only the keyboard fix, regression tests, and documentation. It does not include file completion or fork maintenance/deployment changes. Browsers that do not implement the directive retain their existing behavior; this is not a claim of a Safari keyboard fix.

## Before / after (real Android phone)

| Before: keyboard covers the input | After: input remains visible |
| --- | --- |
| <img src="https://raw.githubusercontent.com/swaroopch/shelley/bc9aff00b23918528e490a712819fd48e0679fcc/docs/pr-assets/mobile-keyboard-before.png" alt="Before: only the top edge of the text field is visible above the Android keyboard" width="300"> | <img src="https://raw.githubusercontent.com/swaroopch/shelley/bc9aff00b23918528e490a712819fd48e0679fcc/docs/pr-assets/mobile-keyboard-after.png" alt="After: the full Hello World text field is visible above the Android keyboard" width="300"> |

Screenshots are cropped to the composer and keyboard to omit private conversation details. The hostname in the before image is blurred. The captures use different themes. Image assets live in the fork, not in this PR's code diff.

## Recreation prompt

If you prefer to implement the intent independently rather than reuse this diff:

```text
Fix the Android Chrome chat composer being obscured by the software keyboard.
The textarea and send controls must remain visible and usable while typing,
for both new/draft and existing conversations, including long histories.

Let the conversation area resize as available space changes. Preserve drafts,
focus, and normal sending through keyboard opening/dismissal and orientation
changes. Long drafts should scroll within the textarea rather than push the
composer below the keyboard. Keep desktop behavior unchanged.

Prefer the browser's native viewport-resize policy over hard-coded keyboard
heights, timers, or competing JavaScript scroll/resize mechanisms. Keep the
change focused; do not change file completion, attachments, or sending rules.

Test both the keyboard-resize policy in the served page and the resulting
small-viewport layout, including multiline input and desktop alignment.
A headless viewport resize alone does not reproduce Android's real keyboard
behavior: explicitly state that limitation and verify on a physical phone.
```

## Validation

- The viewport-policy regression fails before the fix and passes afterward.
- Five browser checks passed: keyboard policy, new/existing conversation layout and draft preservation, and desktop composer alignment.
- Both UI type checks, lint, and all 55 UI unit-test files passed on this feature branch.
- `make build-custom` and `go test ./server -parallel 1` passed.
- The owner verified the fix with a real Android keyboard (after screenshot above).

A manual device checklist is included in `MOBILE_KEYBOARD_INPUT.md`.
