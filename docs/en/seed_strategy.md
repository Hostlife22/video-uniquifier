# Seed strategy

Random transforms use `Plan.run_seed` to choose parameters. `Profile.seed_strategy` controls whether a new processing run repeats those choices or generates a new variant. Use variants only for video that you own or are licensed to modify and distribute.

## The four strategies

| Strategy | Seed source | Behavior |
|---|---|---|
| `fixed` | `Profile.seed`, or 0 when unset, reduced to uint32 | Repeat the same parameter draws |
| `per_run` | A new random uint32 for a new run | Vary parameters between independent runs |
| `per_file` | First four SHA-256 bytes of `source.path.as_posix()` | Repeat choices for the same path string |
| `divergent` | A new run seed plus a derived seed for each video segment | Vary video parameters between segments |

`per_file` hashes the path, not the file contents. Moving the file or using a different path can change the seed; changing the file contents at the same path does not change this seed derivation. The plan hash separately identifies the processing plan.

## Configure a profile

Copy a native profile and set its strategy:

```yaml
seed_strategy: fixed
seed: 42
```

For independent variants, use `per_run`. For experiments requiring variation between video segments, use `divergent`; the name does not promise a particular decision by an external detection system.

```yaml
seed_strategy: divergent
```

The segment seed is the first four SHA-256 bytes, interpreted as an unsigned big-endian integer, of the UTF-8 payload `"{plan_hash}:{segment_idx}:{run_seed}"`. Identical inputs to this derivation produce the same segment seed. The full-source audio pass retains the run-level seed.

## Resume and new variants

The checkpoint in `state.json` retains the run seed. Resuming the same compatible plan reuses those choices and completed segments. `--new-variant` requests a fresh variant for `per_run` and `divergent`; `fixed` and `per_file` remain deterministic.

```bash
video-uniq run master.mp4 --profile p.yaml --out result.mp4
video-uniq run master.mp4 --profile p.yaml --out result.mp4 --new-variant
```

Here `p.yaml` is your saved native profile. Keep a dedicated output/work directory for each concurrent job.

## Reproducibility limits

A seed makes random parameter selection reproducible. It does not guarantee identical encoded bytes across encoder versions, thread scheduling, hardware, platform builds or container metadata. Retain the source checksum, profile, plan hash, effective seed and tool versions when reproducing a result. Validate decoded media correctness and use a registered reference for quality comparisons.

Local similarity scores do not predict Content ID decisions, platform originality, reach or permission to publish. Review picture, dialogue and subtitles before using an authorized derivative.

## Implementation and tests

- `core/seed_resolver.py`: run-seed resolution and per-segment derivation.
- `core/segmenter.py::_plan_for_segment`: video-segment plan copies.
- `core/orchestrator.py::build_plan`: initial run-seed selection.
- `tests/unit/test_seed_resolver.py` and `tests/unit/test_divergent_seed.py`: deterministic derivation, strategy behavior and uint32 bounds.
