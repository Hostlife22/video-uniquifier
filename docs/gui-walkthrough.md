# GUI walkthrough

A screen-by-screen tour of the PyQt6 desktop client. The screen
reference (event signals, worker wiring, packaging) lives in
[`gui.md`](gui.md); this page is the user-facing tour.

## Launching

```bash
pip install video-uniquifier[gui]
video-uniq-gui
```

The first launch shows a one-time **Local telemetry** dialog
(off-by-default; see [Telemetry](telemetry.md)). The main window
opens on the **Process video** screen.

## Sidebar

Ten screens, navigable via Ctrl+1..Ctrl+0:

| # | Screen | Use |
|---|--------|-----|
| 1 | Process video | Choose source/destination, apply a profile and inspect results |
| 2 | Batch processing | Process a folder and track each file |
| 3 | Auto-tune | Search profile settings against quality and similarity constraints |
| 4 | Quality reports | Open a report or compare an input/output pair |
| 5 | Profiles | Edit effects, inspect YAML and browse community profiles |
| 6 | History | Find past jobs and open their videos/reports |
| 7 | Reference library | Manage your own local fingerprint references |
| 8 | Processing queue | Organize pending work and control background workers |
| 9 | Experiments | Generate owned/licensed variants and record observations |
| 10 | Settings | Theme, language, default profile and optional integrations |

On Process video, follow **Source & destination → Processing → Progress & result**.
The destination is suggested automatically. Start with `soft` for an initial quality
comparison, or use a saved profile. Expand Advanced settings only when you need
encoder selection, profile editing or auto-tuning. The Activity log opens on errors.

## Keyboard shortcuts (Run screen)

| Shortcut    | Action                  |
|-------------|-------------------------|
| `Ctrl+R`    | Start processing        |
| `Ctrl+T`    | Auto-tune profile       |
| `Space`     | Pause / Resume          |
| `Esc`       | Cancel                  |
| `Ctrl+S`    | Save preferences        |
| `Ctrl+P`    | Check video             |
| `Ctrl+Q`    | Open quality report     |
| `Ctrl+1..0` | Jump to sidebar screen  |

## Settings → Language (v0.9 R5)

Switching the language is hot — the translator re-installs and
the choice persists to `state.json`. Navigation, page headings and the main
processing workflow update immediately. Some secondary dialogs and technical
messages retain their original strings until restart; Coverage matrix and contributor guide at
[Localization](i18n.md).

## Accessibility (v1.0.0 R6)

Every screen meets **WCAG 2.1 AA**: visible 2-px focus outline
on every interactive control (dark + light themes), every widget
has a screen-reader-announced name + role, every button hits the
≥24×24 px target-size floor, and every painted foreground /
background pair clears the 4.5:1 contrast ratio. Full conformance
statement + screen-reader manual test guide:
[`docs/accessibility.md`](accessibility.md).

## Screenshots

Reviewed visual baselines live under `tests/visual/__snapshots__/`, with the
capture platform recorded in `host.json`. Native font rendering differs between
macOS and Linux; use `make test-visual-update` only for an intentional change and
review the images on that host. `make test-visual` compares the reviewed baseline.

The layout and behavior suite separately checks all ten pages at 980×640 in both
themes, including keyboard disclosures, source preservation and encoder selection.
