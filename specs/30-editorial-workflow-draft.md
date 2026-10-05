# Editorial workflow for authorized media — design draft

Status: **DRAFT, not an approved public-contract RFC**. Date: 2026-10-04.
This fulfils the design step of AP-26; it does not implement a story editor.

## Problem

The existing segmenter divides processing at keyframes. It does not represent
editorial choices, narration, B-roll selection, picture-in-picture or masks.
Adding more filters cannot express those temporal relationships reliably.

## Proposal and MVP scope

Introduce an opt-in editorial layer for owned/licensed assets. Its draft internal
EDL describes assets, source in/out points, destination start times, video/audio
tracks, narration, bounded rectangular overlays and subtitle cues. Each asset has
rights provenance and a content hash. Reject overlapping ambiguous primary clips,
missing assets, negative/invalid time ranges and unspecified speaker layouts before
rendering. External downloads and rights decisions remain operator responsibilities.

MVP: ordered cuts on one primary video track, one narration track, explicit B-roll
replacements, a bounded PiP rectangle and subtitle cues. Arbitrary animated masks,
automatic story writing, voice cloning, semantic scene replacement and automatic
rights clearance are outside that MVP. A subtitle renderer is not a script editor.

The editorial compiler resolves timing into a deterministic sequence of existing
core processing plans and composition operations. It calls the existing orchestrator,
filter builders, seeded transforms, encoder discovery, disk admission and final
decode gate. CLI/GUI/web remain wrappers. It must not embed a second orchestration
implementation in the frontend. Composition additions use the existing label
allocator and bounded input/thread limits; `video.blend_b` alone is not a generic
multi-track compositor.

## Timing, audio and reference policy

Maintain an explicit source-to-destination mapping for every cut and asset. Use
rational timestamps and preserve VFR cadence until the delivery policy requests
conversion. Define gap policy (black/silence or rejection), transitions, audio
ducking/headroom and narration priority. Do not silently downmix unknown surround
positions. Apply final loudness once after composition, with full-stream peak and
phase diagnostics. Resume keys include EDL, asset hashes and every render seed.

Quality references replay the exact editorial composition without delivery encoding,
including subtitles/PiP and narration. Compare encode-quality to that lossless
reference, and editorial quality separately against source/reviewer intent. A global
source/output SSCD mean cannot qualify an edited narrative. Missing or unaffordable
references produce explicit unavailability, preserving resource admission guards.

## Alternatives

1. External NLE plus this project's encode/QA pipeline: lowest implementation cost;
   exact exported timing and rights manifest still required.
2. More per-segment transforms: insufficient for track timing, story structure and
   controlled narration; not selected as the editorial abstraction.
3. Full NLE implementation: excessive initial scope; defer until MVP needs justify it.

## Migration and contract decision

No stable model, flag, profile ID or event changes in this design delivery.
Promoting EDL to a public model or adding CLI commands is MINOR and requires the
repository RFC process, accepted decision, contract snapshots, API docs and CHANGELOG
before implementation. Existing single-source Profile/Plan behavior stays available.
Do not mark this draft accepted or treat it as authorisation to publish content.

## Implementation backlog

| ID | Task | Status | Acceptance |
|---|---|---|---|
| EDL-01 | Internal timeline/rights model and validator | TODO | Invalid bounds/topology rejected; source hashes retained |
| EDL-02 | Cut/asset mapping and resume identity | TODO | Known events retain order/time across cuts and resume |
| EDL-03 | Core composition graph with bounded inputs | TODO | PiP/B-roll fixture decodes; memory/disk admission preserved |
| EDL-04 | Narration mix/ducking/loudness | TODO | Main speech, mono/headroom and speaker events qualified |
| EDL-05 | Exact lossless reference replay | TODO | Repeatable pixels/timing/audio under the same EDL/seed |
| EDL-06 | Public contract RFC/migration | TODO | Accepted RFC before stable surfaces change |
| EDL-07 | Thin CLI/GUI/web wrappers | TODO | Same core entry point; accessibility/contract checks |
| EDL-08 | Independent natural corpus and human review | TODO | Held-out titles, narrative correctness and listening labels |

MVP completion requires all eight tasks; this document completes none of them.
