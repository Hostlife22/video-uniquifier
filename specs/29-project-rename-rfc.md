# RFC: rename the project to video-uniquifier

Status: accepted naming scope — the repository owner explicitly requested that
all code, builds and GitHub links follow the renamed repository. This records
that direct authorization; no external reviewer votes or RFC issue are claimed.
The owner's implementation instruction takes precedence over the usual review
window for this rename. The owner subsequently requested pushing the completed
change and tagging v2.0.0 to run the release workflows.

SemVer classification: MAJOR, version 2.0.0.

## Problem

The repository is now `Hostlife22/video-uniquifier`, while imports, executable
names, package metadata, release workflows and service endpoints use old names.
A partial rename would break installation, resource lookup and release downloads.

## Proposal

- Distribution/repository/OCI image: `video-uniquifier`.
- Python package and plugin group: `video_uniquifier`, `video_uniquifier.transforms`.
- Executables: `video-uniq`, `video-uniq-gui`, `video-uniq-web`.
- Environment prefixes: `VIDEO_UNIQ_*`, `VIDEO_UNIQUIFIER_*`, `VU_*`.
- Error base class: `VideoUniquifierError`; metric/SBOM names use the new prefix.
- Rename native bundle/spec/desktop files and update all build references.
- Update GitHub, GitHub Pages, updater signing identity and marketplace URLs.
- Preserve media-processing behavior, profile names/parameters and event payloads.

## Alternatives

A repository-only rename leaves inconsistent installation and user-facing names.
Keeping old import/command aliases maintains two identities indefinitely; the
owner requested a complete rename, so old executable/module aliases are removed.

## Migration plan

Reinstall the editable package or install the new wheel. Update Python imports,
scripts, environment variables, plugin entry points, metrics dashboards and image
references to the names above. GUI state/history is copied from old locations
when the new directory has no state; old files remain as backups. Core caches
use the new namespace and are regenerated; previous processing/QA evidence is
retained separately and is not asserted to qualify the renamed release.

Update API-contract documentation and contract snapshots. Verify lint, typing,
tests, wheel contents, executable entry points and native packaging. Historical
release filenames and measurements retain their original provenance. After
validation, push the change and create v2.0.0 so the existing release, Docker
and documentation workflows build and publish the new version.
