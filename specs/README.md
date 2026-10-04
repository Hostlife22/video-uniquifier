# RFC index

This directory retains design and compatibility decisions for public contracts:

| RFC | Scope |
| --- | --- |
| [26 — No-upscale geometry policy](26-no-upscale-policy-rfc.md) | Explicit scaling policy and profile migration; GitHub RFC #11. |
| [27 — Raw and registered QA metrics](27-registered-qa-metrics-rfc.md) | Separate raw/registered metrics and bounded audio alignment; GitHub RFC #12. |
| [28 — QA correctness, loudness and quality thresholds](28-qa-correctness-loudness-rfc.md) | Accepted additive QA evidence and opt-in quality gates; GitHub issue #21. |
| [29 — Project rename](29-project-rename-rfc.md) | Owner-authorized v2.0.0 naming migration across packages, executables and builds. |

RFCs preserve the proposal and decision record. For current shipped behavior,
consult [API contracts](../docs/api-contracts.md), [profiles](../docs/profiles.md)
and [QA reports](../docs/qa_report.md).

Outstanding production work is tracked in [PRODUCTION_PLAN.md](../PRODUCTION_PLAN.md)
and [RISK_REGISTER.md](../RISK_REGISTER.md). Measured evidence is retained in
[BENCHMARKS.md](../BENCHMARKS.md).

Completed phase plans 00–25 and release roadmaps were removed from the working
tree. Their original contents remain available in Git history, for example:

```bash
git log --all -- specs/ .claude/plans/
git show <commit>:specs/03-segmenter-resume-metadata-preflight.md
```
