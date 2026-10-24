# Desktop UI direction

The primary journey is import → adjust and preview → export. The window should
answer three questions immediately: where am I, what can I do, and what happens
next? Keep all existing processing and queue capabilities available.

The ui-ux-pro-max design-system and UX searches informed this direction:
progressive disclosure, an actionable empty state, clear selection and focus,
and stable hover feedback. Apply these principles to the existing native PyQt6
desktop application. Use system fonts with native Chinese glyph support rather
than the suggested web font pairing. Keep one teal action color instead of
assigning warning colors to ordinary workflow steps.

- Neutral graphite dark surfaces; white cards on a soft gray light canvas.
- One accent for the current step, selected profile and primary action.
- Thin neutral borders, 8–12 px corner radii, 8/12/16/24 px spacing.
- Compact page headers and a persistent bottom processing action.
- An import action inside the empty video preview, with the same file picker and
  drag/drop behavior as the source field. Show supported formats and explain
  that the original is retained.
- A three-step indicator reflects actual state, without forcing wizard navigation.
- Plain-language profile benefits remain visible; technical encoder/profile
  controls remain in the advanced disclosure.
- A recommended short sample is clearly separate from exporting the full video.
  Disabled actions explain their prerequisites.
- Sidebar descriptions clarify advanced destinations without moving indices or
  changing keyboard shortcuts.
- Test dark/light, English/Chinese and minimum/large desktop window sizes. Mobile
  breakpoints do not apply to this native desktop application.
- Compact previews hide decorative upload artwork and format captions so the
  import action stays visible. Opening diagnostics temporarily hides the step
  overview to reserve space for the log and processing result.
- Respect reduced motion and retain visible keyboard focus. Do not rely solely
  on color for selection or processing status.
