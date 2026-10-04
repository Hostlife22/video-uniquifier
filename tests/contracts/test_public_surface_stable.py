"""Lock the explicit ``__all__`` of ``video_uniquifier`` and ``video_uniquifier.core``.

These two ``__all__`` lists are the *registry* of what we
guarantee. If something is removed from a list, it is no longer
covered by the SemVer contract — that is a MAJOR change.

If you intentionally promote an internal helper to the public
surface, add it here AND document the promotion in
``docs/api-contracts.md`` under its stability label.
"""

from __future__ import annotations

import video_uniquifier
import video_uniquifier.core
from tests.contracts._snapshot import snapshot


def test_top_level_all_is_stable() -> None:
    snapshot("public_surface/video_uniquifier__all__.json", sorted(video_uniquifier.__all__))


def test_core_all_is_stable() -> None:
    snapshot(
        "public_surface/video_uniquifier_core__all__.json",
        sorted(video_uniquifier.core.__all__),
    )
