# Facebook Reels implementation log

## Locked baseline / inspected contracts (2026-10-23)

- Hostlife22/video-uniquifier HEAD: `e9138ddbc798cb23e28b44d9edf7959a712f0add`;
  upstream v2.1.2 tag: `d8731c0540a8dc3b8139b094a4697fa02bc568bc`.
  The local fork has the same engine baseline, plus local GUI improvements.
- Python 3.11.15, FFmpeg/FFprobe 7.1.1, macOS arm64. No AI extra is needed.
- Read `docs/profiles.md`, `docs/plugins.md`, `docs/api-contracts.md`, actual
  Profile/Transform models, pipeline, runner, probe, preflight, loudness and scenes.
- Both supplied YAML documents remain user-owned inputs in
  `facebook_reels_codex_spec/`; implementation does not modify them.
- Native Profile accepts the supplied fields. Transform parameter schemas must
  additionally be validated; `load_profile` alone only validates the outer shape.
- `RunOptions` has no CRF, preset, CFR or overlay input fields. The existing graph
  builder exposes labels and argv, and accepts a pre-measured loudness result.
  Use one narrowly scoped, baseline-pinned adapter instead of changing stable
  Profile/RunOptions contracts or rewriting transforms.
- Native full-file graph measures loudness eagerly even without audio if the
  transform remains enabled. Derivation disables loudnorm for missing/silent audio.
- Native `audio_tracks: first` literally selects the first stream. Reels selects
  the default audio stream when present, otherwise first, and records its absolute
  stream index. Explicit native integer selections use absolute stream indices.
- Native runner supports cancellation, progress, watchdogs and log paths. Reuse it
  for encoding, scans and decode checks; keep processes out of shell strings.
- PySceneDetect adapter emits source boundaries; segmentation snaps to keyframes
  and is not an editorial timeline. Reels reports boundaries without rearranging.

## Implementation order

1. P0: independent native profile; strict business config; native preflight and
   10-second baseline; one encode with delivery parameters; measured loudness;
   full-decode/format/timing QA; atomic report and video publication.
2. P1: optional scene timeline, report-only black/silence detection, synchronized
   manual trim, human title/logo layers, safe-area preview and conflict checks.
3. Local worker/API integration: bounded concurrency, progress, cancellation,
   retry, isolated uploads; NestJS/BullMQ integration example and interface docs.
4. Automated edge cases, 10/30/90-second synthetic acceptance, contracts and build.

## P0 baseline evidence

- Both supplied YAML documents validate against the actual native/business schemas.
- Native CLI `preflight --encoder libx264 --json` passed for a generated 10-second
  180x320 30-fps source with AAC. Native `run` produced a 1080x1920 MP4 and QA HTML
  through the original orchestrator in 8.36 seconds; no native schema changes needed.
- Initial wrapper suite: 43 tests pass, including actual 720x1280 pad_blur encode,
  measured two-pass normalization, full output decode, A/V timing and atomic output.
- The native preflight's generic FPS message still references YouTube. Reels only
  treats it as an engine diagnostic, not a Facebook requirement or approval.

## P1 / worker integration evidence

- Scene detection runs the existing PySceneDetect adapter in a cancellable child
  process. Timeline JSON keeps original order and maps explicit trim to output time.
- Titles are rendered with local Pillow/FreeType, including Chinese and filter
  punctuation. PNG logo/title layers are fused into the native FFmpeg graph;
  actual two-layer integration confirms one delivery encode, bounded retry and QA.
- FFmpeg 7.1.1 `vfrdet` logs use `min: ... max: ...` without a leading bracket.
  Detection is based on timestamp differences; millisecond container rounding
  alone does not trigger VFR normalization.
- The HDR test initially exposed that generic output color flags alone did not
  reliably set x264's source VUI in this fixture. The fixture now explicitly sets
  `colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc` via x264 parameters.
  PQ refusal and explicit native tonemap are tested with verified HDR metadata.
  Unknown wide-gamut transfer tags fail closed. Known SDR primaries/transfer/matrix
  are converted explicitly instead of simply relabeling the output Rec.709.
- Local API covers isolated bounded uploads, bearer authentication, queue limits,
  real runner progress, cancellation, retries, restart failure records and success-only
  artifact downloads. Actual HTTP upload → encode → QA → report/download passed.
- NestJS/BullMQ integration is a Node 22 HTTP bridge, with four passing node:test
  cases. The actual Node bridge also uploaded a 10-second file to a live loopback
  worker, polled real progress and received a successful output/report URL.
  Redis/database/application wiring remains the existing NestJS host's job;
  the example does not claim an installed Redis deployment.
- `tools/install_reels.sh` was executed successfully. The registered `video-reels`
  CLI validated both original supplied YAML files, passed preflight and completed
  a real 10-second run with a consistent job ID across JSON events.
- Built source distribution and wheel (including wheel-from-sdist), then installed
  the wheel into an isolated target directory. Verified that
  the default native Profile is loaded from the wheel, independently of this checkout.

## Acceptance results (macOS arm64, FFmpeg 7.1.1)

Generated by `tools/reels_acceptance.py`, default 1080×1920 preset, scenes and
previews enabled. Local artifacts are under ignored `out/reels-acceptance-20261023/`.
These are synthetic patterns/tones, not a listening or platform-originality verdict.

| Input | Geometry / FPS | Output duration | Encode + scans/QA | LUFS | End drift |
|---|---|---|---|---|---|
| 10 s | 180×320 / 30 | 10.000 s | 11.30 s | -16.04 | 0.00 ms |
| 30 s | 320×180 / 30000/1001 | 30.000 s | 29.68 s | -16.05 | 3.37 ms |
| 90 s | 180×320 / 24000/1001 | 90.000 s | 30.90 s | -15.95 | 35.12 ms |

All three passed complete decode, H.264/yuv420p/Rec.709/SAR/faststart, audio format,
duration, loudness/peak and timestamp checks. Runtime is indicative only for these
small synthetic sources on this host. Authorized dialogue/BGM and phone/subtitle
reviews are still manual acceptance work.

## Final validation scope

- Reels unit and real-FFmpeg integration tests: **98 passed**, covering config/schema/assets, cadence,
  missing/silent/multiple audio, HDR/VFR, synchronized trim, subtitle bounds,
  native scene cuts, timed Chinese title + logo, transient retry, atomic failure,
  cancellation and real HTTP lifecycle. Core branch-aware coverage: **92.7%**.
- Existing full unit suite: **2033 passed, 2 skipped** after installing the declared
  cryptography development dependency. Skips: optional QtCharts and optional Torch;
  no AI dependency was installed. The added example/schema sync test also passed.
- Core and stable API/Profile/RunOptions/RunEvent contract regression: **261 passed**.
- `ruff check .`: passed. New worker/CLI/API/acceptance code: mypy passed (13 files).
- Whole-repository mypy still reports five existing issues in unrelated files:
  `gui/widgets/workflow_steps.py:57`, `gui/widgets/studio_preview.py:339`,
  `gui/screens/run.py:515` (two optional Qt object accesses) and
  `core/qa/sscd.py:129` (unused optional-import ignore with this mypy version).
  These modules were not changed for Reels; the whole-repository type gate is not
  claimed as passing. The full integration/hardware suite was not run.
- Wheel build, isolated package resource check, installer and CLI smoke passed.
  FastAPI TestClient emits a third-party httpx deprecation warning; product requests
  and assertions pass.
