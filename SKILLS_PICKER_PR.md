feat(ui): add a /skills picker to the prompt composer

Adds a searchable `/skills` picker with keyboard and mouse selection. Choosing a skill inserts editable activation instructions into the draft without sending the message or executing the skill.

Reuses existing discovery for new drafts and the effective system-prompt catalog for existing conversations. No new dependencies or database changes.

## Validation

- 73 UI test files, both type checks, and lint passed.
- Full Go suite and targeted catalog/parser race tests passed.
- Nine browser regressions passed; the deployed feature was also user-tested.

<details>
<summary>Mobile picker (synthetic test skills)</summary>

![Skills picker](https://raw.githubusercontent.com/swaroopch/shelley/d7217888034bf53e342e0042cb89220e48d7f9fd/docs/pr-assets/skills-picker.png)

</details>

## Recreation prompt

If you prefer to implement the intent independently rather than reuse this code diff:

```text
Add /skills to Shelley's prompt composer. Show a searchable catalog with skill
names, descriptions, and sources. Support arrows, Enter/Tab, clicking, and Escape.
Selection replaces only the command fragment with editable instructions to use
that skill and load it through its existing activation command. Preserve other
text, caret position, attachments, and draft persistence; allow multiple selections.
Do not send, queue, compact, or execute anything on selection, including during
loading, empty results, or errors. Reuse existing discovery for new drafts and the
current effective system-prompt catalog for existing conversations. Return metadata
only and reject stale responses after context changes. Preserve existing completion
and IME behavior. Avoid new dependencies and schema changes. Include deterministic
tests for selection, snapshots, draft promotion, errors, retries, and mobile layout.
```

Implemented with AI assistance.
