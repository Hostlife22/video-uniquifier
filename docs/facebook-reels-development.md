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
