# Manual GUI smoke checklist

Run `scripts/manual_gui_smoke.sh` to launch the GUI with a generated
5-second sample clip. Walk every numbered step; record FAIL with the
screen + repro in the issue tracker.

Goal: catch anything `make test-gui` cannot — drag-and-drop, chart
rendering, hotkeys, dialog/file-pickers, theme switching, persistence
across restarts.

## 1. Run screen — golden path
- [ ] Drag the sample clip into the input picker (or use Choose…). Filename and directory appear; long paths elide with a full-path tooltip.
- [ ] Verify the suggested output is separate from the source; choose another path if desired.
- [ ] Click **Check video** — finding rows render in the panel (PASS or WARN, no FAIL on the sample).
- [ ] Click **Start processing** — progress fraction advances, timeline shows segments green.
- [ ] On finish, status becomes "Done", result actions scroll into view and Open quality report enables. Expand Measured metrics to inspect the KPI pills.
- [ ] Click Open quality report — system browser opens the `.qa.html`.

## 2. Run screen — cancel
- [ ] Start Run, click **Cancel** mid-run — status flips to "Cancelling…" then "Cancelled".
- [ ] Start processing button is re-enabled after cancellation.

## Short sample, comparison and processing stages

- [ ] Preview original plays locally without starting an encode.
- [ ] Source thumbnail and five filmstrip frames appear asynchronously; changing the source discards older frames.
- [ ] Profile cards show readable picture/audio descriptions in Russian and English, including at 980×640. Selecting a card updates the profile; custom profiles clear card selection.
- [ ] Click/drag the filmstrip or use arrow keys; the HH:MM:SS.cc input follows the selection. Use this time for sample in the original player sets the same start.
- [ ] Expand Test a short fragment, select a start and 10/15/20 seconds, then Process sample. A short source is clamped at its end.
- [ ] Sample completion opens Before / after. The original file, full destination and run history stay unchanged.
- [ ] Scrub and play both panels; switch between original/result audio and confirm only one soundtrack is heard. Pausing mutes both.
- [ ] Step forward and backward while paused, including a variable-frame-rate clip. The displayed frame changes by one adjacent timestamp.
- [ ] Switch side-by-side/original/result and Fit/100%. Inspect pixel detail; scroll larger frames on a Retina display.
- [ ] Switch to Draggable divider. Drag the handle and use Left/Right, Home/End; verify source on the left, result on the right and matching frame positions.
- [ ] Select 50/200/400% and drag the image; both sides move together. In side-by-side mode, scroll/drag either picture and confirm the other follows.
- [ ] Save sample… writes an identical MP4 that survives closing the application. Original-path, symlink and hardlink destinations are rejected. Cancel keeps any existing destination intact and allows retry.
- [ ] Navigate to Settings while processing a sample; progress remains in the global banner. Return to task selects the right screen; completed tasks disappear. Select between simultaneous run/batch tasks.
- [ ] For a changed-tempo result, select Sync by duration; verify shared presentation progress without assuming semantic scene alignment.
- [ ] At 760×540, comparison controls remain usable. Close the dialog during frame lookup; the application remains responsive.
- [ ] During a full run, stages continue through saving and quality checks. Stage ETA resets at transitions; pause freezes elapsed time, and unknown/stalled progress has no numeric ETA.
- [ ] Cancel during sample preparation and during QA. Controls allow retry and the result is labelled Cancelled.
- [ ] HDR input disables the sample button with an explanation; full processing remains available.
- [ ] Known PQ/HLG HDR comparison frames disable the raster divider; native panels remain available. Confirm display color separately on suitable HDR equipment.

## 3. Batch screen
- [ ] Pick a directory with 2+ mp4s. Table preview lists them.
- [ ] Change pattern to `*.mov` — preview updates / clears.
- [ ] Run batch, watch per-file status cycle: queued → running → done.
- [ ] Continue-on-error toggle visibly changes failure behavior when one file errors.

## 4. Calibrate screen
- [ ] Pick the sample as calibration input.
- [ ] Set iterations to 1 and click **Find settings** (short — under 1 min on tiny clip).
- [ ] After completion **Save tuned profile as…** is enabled.
- [ ] Save to a temp YAML and confirm file exists.

## 5. QA Viewer
- [ ] Switch to **Open existing** tab; pick the `.qa.html` from step 1.
- [ ] The report renders when an embedded viewer is available; browser fallback remains usable.
- [ ] **Open in browser** opens the HTML report.

## 6. Profile Editor
- [ ] Pick `cid_aware` from the dropdown — table populates with transforms.
- [ ] Edit one parameter, click **Save as…**, write to a new path.
- [ ] **Reload list** picks up the new profile.

## 7. History
- [ ] Verify the run from step 1 appears in the history table.
- [ ] Apply a filter — rows update live.
- [ ] **Clear all** prompts confirmation and empties the table.

## 8. Queue
- [ ] **Browse…** + **Init queue here** on an empty directory — buttons cycle from disabled to enabled.
- [ ] **Add files…** adds the sample. Stats label shows pending=1.
- [ ] **▶ Start worker** — sample drains; on completion stats show done=1.
- [ ] **Stop** during active drain halts cleanly.

## 9. Validation
- [ ] Step 1 → pick the sample + 2 variants + Generate; rows appear.
- [ ] Step 2 → record per-row CID outcome (pass/fail) and save CSV.
- [ ] Step 3 → Run correlation analysis; output box shows the report.

## 10. Settings + Corpus + theme switch
- [ ] Switch theme dark↔light — every visible screen re-skins immediately.
- [ ] Choose a default profile and Save — re-open Settings to confirm persistence.
- [ ] Corpus → Add file → entry appears. Remove → row disappears.
- [ ] Close the app and re-launch — recents, selected profile, language and theme survive restart.

## 11. Misc
- [ ] Resize window — no overlapping widgets, no clipped labels.
- [ ] Expand Advanced settings and Activity log with keyboard focus + Space.
- [ ] At 980×640, primary actions stay visible while the page scrolls.
- [ ] Switch language: navigation, page titles and main workflow update without blank controls.
- [ ] No console errors on stderr after a normal session.
