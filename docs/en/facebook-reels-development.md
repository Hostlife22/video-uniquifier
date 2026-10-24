# Facebook Reels implementation log

## PR review corrections (2026-10-24)

- Clearing an absent sample preserves the original preview decoder and its first-frame state. A Windows/Python 3.11 repetition caught a native pause stall while settings unnecessarily reset the original during decoder initialization. Pausing now calls the native player only in `PlayingState`. Regression tests cover absent-sample invalidation, real sample replacement and all playback states. A C-level pytest watchdog dumps threads and exits at the existing 180-second per-test limit even when a native call blocks the Python timer; development requires pytest 9.1.1 or newer. Before the fix, the ninth Windows repetition blocked in `QMediaPlayer.pause()`; after the fix, all 20 real preflight/sample/export/cancellation repetitions and four targeted regressions passed.
- Worker JSON writes and downloads normalize and confine paths to the configured storage root, including symlinks and sibling-directory prefixes. Restored job identifiers must be hexadecimal, and malformed records are skipped. Temporary JSON files are exclusively created and flushed before atomic replacement.
- PNG logo dimensions are checked before resizing: narrow inputs can otherwise expand far beyond the source pixel budget and exhaust worker memory.
- Table selection uses an owned checkbox positioned from public header geometry, avoiding private Qt corner discovery and SIP casts after a Linux native crash. Resize, header visibility, both layout directions and teardown are covered. Translation enumerates public caption controls, blocks only combo/tab/table signals, and skips deleted descendants. Hidden delivery pages no longer widen the outer page; forms wrap long rows. Small-window checks cover English, Russian and Chinese, with reviewed visual baselines for all eleven screens.
- Real 10/30/90-second exports passed technical QA. Native Cocoa acceptance passed source/sample/export, decoded playback, comparison, quality reports and small windows. Real loopback HTTP acceptance passed authenticated upload, processing, cancellation, retry, download and rejection of escaping artifact symlinks.
- Evidence is kept under ignored `out/pr34-review/`: core and desktop acceptance JSON, HTTP acceptance JSON, screenshots, and test/build logs. These checks use generated footage and do not replace editorial listening/subtitle review.
- Fast core contract tests cover source limits/HDR/subtitles, native audio selection and trim graphs, loudness caching, cadence diagnostics and queued cancellation. Clean fast-test run: 2298 passed, one optional-branch skip; core coverage is 81.88%, above the required 80% gate. The loaded-HD preview integration checks sample actions on their new settings page and waits for Qt layout completion.
- HDR integration also checks the unsupported-build case: macOS CI's FFmpeg may lack zscale, in which case explicit conversion must fail preflight without publishing a result. Hosts with zscale still run and verify the real conversion.
- The integration step has a 30-minute total budget after Linux/macOS runners exhausted the previous 15 minutes. The 180-second per-test cap is unchanged; CI now records the twenty slowest tests. All integration tests remain enabled.
- Comparison checks local file availability before invoking a native decoder, matching the existing studio preview. Missing-file errors and early close are tested alongside real playback. CI prints integration test names so native process exits can be attributed to a specific test instead of an anonymous dot.
- GUI test windows remain strongly referenced until Qt's deferred deletions are flushed. Cancellation watcher tests use native Python processes on every OS rather than Git Bash/MSYS sleep wrappers; the seven-second bound and separate native process-tree cancellation integration remain unchanged.

## Tabular desktop quality reports (2026-10-23)

- Delivery's quality-report action opens a native window with source/output columns for resolution, frame rate, duration, codecs, bitrates, file size, measured loudness, sample rate and channel count. A second tab shows technical checks, A/V drift, measured true peak, warnings and outstanding human review.
- Values come from the completed export snapshot; missing measurements are explicit. Form changes and removal of the JSON file do not alter an already available snapshot. Existing report files can also be loaded, with unreadable reports handled inline. The JSON artifact remains available to CLI/API consumers without changes to core schema.
- Chinese/English switching, minimum window layout, missing audio, malformed/missing values, failures, snapshot isolation and real export handoff are tested. The report widget has **98.7% branch-aware coverage**. Native Cocoa screenshots are recorded as
  `docs/screenshots/delivery-quality-{comparison,checks}-zh.png` using synthetic footage.
- Final unit/contract/desktop smoke recheck: **2155 passed, 2 skipped**. GUI mypy (74 files), Ruff and wheel build pass.

## In-app delivery review (2026-10-23)

- Reused `VideoCompareDialog` for completed delivery exports. The result page has a primary before/after comparison action and a separate in-app result-only player; neither video action invokes the system default player. Folder/report actions remain available.
- Export review retains the completed source/output pair and trims its reference timeline to the exact start/end selected for that export. Later form changes do not replace it. Duration synchronization scales the retained interval instead of the entire source.
- Visible export completion opens the comparison; background completion leaves other work undisturbed. Navigation pauses review, and replacement, shutdown and Escape release media. Result-only playback also works when the original file has moved or been deleted.
- Validation: **2137 passed, 2 skipped** in unit/contract/desktop smoke regression;
  **109 passed** in focused review/delivery tests including real export and cancellation;
  **11 passed** with native macOS/Cocoa media playback. Reviewed screen/player modules have
  **86.2% branch-aware coverage**. GUI mypy, Ruff and wheel build pass.
- Native acceptance re-exports the 10-second synthetic source, seeks both comparison players and checks the standalone result player. Result/small-window screenshots and new comparison/playback layouts are recorded in `docs/screenshots/delivery-*`. QWidget captures omit native GPU video surfaces; decoded frames and transport are checked by acceptance assertions and real-media integration tests.

## Desktop delivery workflow (2026-10-23)

- Added **Workspace → Video delivery**(Chinese:**工作区 → 视频交付**). Reels identifies the current vertical delivery preset rather than defining the module name.
- Four independent source/settings/sample/export pages replace the dense single form. Video, audio/timeline and optional branding each have their own settings tab. The original Run screen also separates source, settings and results.
- `ReelsWorker` calls the existing core directly in QThread. It snapshots settings, stages bounded local assets, keeps 10-second samples separate from full export, invalidates stale samples, retains worker references until the thread finishes, and propagates native cancellation. Successful full exports enter existing history.
- Native macOS/Cocoa acceptance: real 10-second footage → sample → 720×1280 export, PySceneDetect timeline, safe-area PNG and final technical QA passed. Duration error and start/end A/V drift: 0. Loudness: -16.04 LUFS. Dialogue/subtitle review remains manual. Evidence is generated at `out/reels-desktop-acceptance/acceptance.json` by
  `tools/reels_desktop_acceptance.py`; reviewed screenshots are in `docs/screenshots/delivery-*`.
- Native acceptance found that selecting a hidden sidebar item allowed focus changes to navigate away during processing. Replaced it with a single visible, grouped sidebar and route-to-screen mapping. Existing screen identities and keyboard shortcuts remain stable; tests verify route identity, language changes, task return and small windows.
- Desktop regression tests include real ffmpeg sample/full export/cancellation and strict options, asset limits, errors and live Chinese switching. New desktop modules reached 90.5% branch-aware coverage in the focused coverage run.
- Final unit/contract/desktop smoke regression: **2120 passed, 2 skipped**(optional QtCharts and Torch). Focused desktop tests:**20 passed**. Native screenshots include all four steps plus 980×640, light theme and the reorganized ordinary processing pages.
- GUI mypy passes (73 files), Ruff and wheel resource checks pass. Four existing Qt optional-object typing errors were fixed while updating the shared UI widgets; whole-source mypy retains the existing optional `core/qa/sscd.py:129` unused-ignore issue.

## Locked baseline / inspected contracts (2026-10-23)

- Hostlife22/video-uniquifier HEAD: `e9138ddbc798cb23e28b44d9edf7959a712f0add`; upstream v2.1.2 tag: `d8731c0540a8dc3b8139b094a4697fa02bc568bc`. The local fork has the same engine baseline, plus local GUI improvements.
- Python 3.11.15, FFmpeg/FFprobe 7.1.1, macOS arm64. No AI extra is needed.
- Read `docs/en/profiles.md`, `docs/en/plugins.md`, `docs/en/api-contracts.md`, actual Profile/Transform models, pipeline, runner, probe, preflight, loudness and scenes.
- Both supplied YAML documents remain user-owned inputs in
  `facebook_reels_codex_spec/`; implementation does not modify them.
- Native Profile accepts the supplied fields. Transform parameter schemas must additionally be validated; `load_profile` alone only validates the outer shape.
- `RunOptions` has no CRF, preset, CFR or overlay input fields. The existing graph builder exposes labels and argv, and accepts a pre-measured loudness result. Use one narrowly scoped, baseline-pinned adapter instead of changing stable Profile/RunOptions contracts or rewriting transforms.
- Native full-file graph measures loudness eagerly even without audio if the transform remains enabled. Derivation disables loudnorm for missing/silent audio.
- Native `audio_tracks: first` literally selects the first stream. Reels selects the default audio stream when present, otherwise first, and records its absolute stream index. Explicit native integer selections use absolute stream indices.
- Native runner supports cancellation, progress, watchdogs and log paths. Reuse it for encoding, scans and decode checks; keep processes out of shell strings.
- PySceneDetect adapter emits source boundaries; segmentation snaps to keyframes and is not an editorial timeline. Reels reports boundaries without rearranging.

## Implementation order

1. P0: independent native profile; strict business config; native preflight and 10-second baseline; one encode with delivery parameters; measured loudness; full-decode/format/timing QA; atomic report and video publication.
2. P1: optional scene timeline, report-only black/silence detection, synchronized manual trim, human title/logo layers, safe-area preview and conflict checks.
3. Local worker/API integration: bounded concurrency, progress, cancellation, retry, isolated uploads; NestJS/BullMQ integration example and interface docs.
4. Automated edge cases, 10/30/90-second synthetic acceptance, contracts and build.

## P0 baseline evidence

- Both supplied YAML documents validate against the actual native/business schemas.
- Native CLI `preflight --encoder libx264 --json` passed for a generated 10-second 180x320 30-fps source with AAC. Native `run` produced a 1080x1920 MP4 and QA HTML through the original orchestrator in 8.36 seconds; no native schema changes needed.
- Initial wrapper suite: 43 tests pass, including actual 720x1280 pad_blur encode, measured two-pass normalization, full output decode, A/V timing and atomic output.
- The native preflight's generic FPS message still references YouTube. Reels only treats it as an engine diagnostic, not a Facebook requirement or approval.

## P1 / worker integration evidence

- Scene detection runs the existing PySceneDetect adapter in a cancellable child process. Timeline JSON keeps original order and maps explicit trim to output time.
- Titles are rendered with local Pillow/FreeType, including Chinese and filter punctuation. PNG logo/title layers are fused into the native FFmpeg graph; actual two-layer integration confirms one delivery encode, bounded retry and QA.
- FFmpeg 7.1.1 `vfrdet` logs use `min: ... max: ...` without a leading bracket. Detection is based on timestamp differences; millisecond container rounding alone does not trigger VFR normalization.
- The HDR test initially exposed that generic output color flags alone did not reliably set x264's source VUI in this fixture. The fixture now explicitly sets
  `colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc` via x264 parameters. PQ refusal and explicit native tonemap are tested with verified HDR metadata. Unknown wide-gamut transfer tags fail closed. Known SDR primaries/transfer/matrix are converted explicitly instead of simply relabeling the output Rec.709.
- Local API covers isolated bounded uploads, bearer authentication, queue limits, real runner progress, cancellation, retries, restart failure records and success-only artifact downloads. Actual HTTP upload → encode → QA → report/download passed.
- NestJS/BullMQ integration is a Node 22 HTTP bridge, with four passing node:test cases. The actual Node bridge also uploaded a 10-second file to a live loopback worker, polled real progress and received a successful output/report URL. Redis/database/application wiring remains the existing NestJS host's job; the example does not claim an installed Redis deployment.
- `tools/install_reels.sh` was executed successfully. The registered `video-reels` CLI validated both original supplied YAML files, passed preflight and completed a real 10-second run with a consistent job ID across JSON events.
- Built source distribution and wheel (including wheel-from-sdist), then installed the wheel into an isolated target directory. Verified that the default native Profile is loaded from the wheel, independently of this checkout.

## Acceptance results (macOS arm64, FFmpeg 7.1.1)

Generated by `tools/reels_acceptance.py`, default 1080×1920 preset, scenes and previews enabled. Local artifacts are under ignored `out/reels-acceptance-20261023/`. These are synthetic patterns/tones, not a listening or platform-originality verdict.

| Input | Geometry / FPS | Output duration | Encode + scans/QA | LUFS | End drift |
|---|---|---|---|---|---|
| 10 s | 180×320 / 30 | 10.000 s | 11.30 s | -16.04 | 0.00 ms |
| 30 s | 320×180 / 30000/1001 | 30.000 s | 29.68 s | -16.05 | 3.37 ms |
| 90 s | 180×320 / 24000/1001 | 90.000 s | 30.90 s | -15.95 | 35.12 ms |

All three passed complete decode, H.264/yuv420p/Rec.709/SAR/faststart, audio format, duration, loudness/peak and timestamp checks. Runtime is indicative only for these small synthetic sources on this host. Authorized dialogue/BGM and phone/subtitle reviews are still manual acceptance work.

## Final validation scope

- Reels unit and real-FFmpeg integration tests: **98 passed**, covering config/schema/assets, cadence, missing/silent/multiple audio, HDR/VFR, synchronized trim, subtitle bounds, native scene cuts, timed Chinese title + logo, transient retry, atomic failure, cancellation and real HTTP lifecycle. Core branch-aware coverage:**92.7%**.
- Existing full unit suite: **2033 passed, 2 skipped** after installing the declared cryptography development dependency. Skips: optional QtCharts and optional Torch; no AI dependency was installed. The added example/schema sync test also passed.
- Core and stable API/Profile/RunOptions/RunEvent contract regression: **261 passed**.
- `ruff check .`: passed. New worker/CLI/API/acceptance code: mypy passed (13 files).
- Whole-repository mypy still reports five existing issues in unrelated files:
  `gui/widgets/workflow_steps.py:57`, `gui/widgets/studio_preview.py:339`,
  `gui/screens/run.py:515` (two optional Qt object accesses) and
  `core/qa/sscd.py:129` (unused optional-import ignore with this mypy version). These modules were not changed for Reels; the whole-repository type gate is not claimed as passing. The full integration/hardware suite was not run.
- Wheel build, isolated package resource check, installer and CLI smoke passed. FastAPI TestClient emits a third-party httpx deprecation warning; product requests and assertions pass.
