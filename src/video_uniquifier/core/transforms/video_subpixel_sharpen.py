"""Luma-only unsharp masking for controlled authorized derivatives.

The kernel and luma amount alter high-frequency texture. Visibility depends on
content, scale and encoding; no universal sub-visible threshold is established.
This filter has no demonstrated relationship to a proprietary matching system.
Chroma remains untouched to limit color fringing on edges.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from video_uniquifier.core.transforms.base import (
    FilterChain,
    LabelAllocator,
    TransformSpec,
    ensure_params,
    register,
)


class SubpixelSharpenParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Luma amount; assess visibility on the actual material.
    luma_amount: float = Field(default=0.05, ge=0.0, le=0.3)
    # Kernel size for the local-mean subtraction. 5×5 standard.
    # Must be odd (ffmpeg constraint); clamped to {3, 5, 7, 9, 11}.
    radius: int = Field(default=5, ge=3, le=11)


def _build_subpixel_sharpen(
    params: BaseModel, alloc: LabelAllocator, in_lbl: str, *, rng: object = None
) -> FilterChain:
    params = ensure_params(params, SubpixelSharpenParams)
    r = params.radius
    # ffmpeg unsharp requires odd kernel; round up if user passed even value.
    if r % 2 == 0:
        r += 1
    a = params.luma_amount
    out = alloc.next("v")
    # lx/ly = luma kernel size, la = luma amount, ca=0.0 = chroma untouched.
    filt = f"unsharp=lx={r}:ly={r}:la={a:.4f}:cx={r}:cy={r}:ca=0.0"
    return FilterChain(in_label=in_lbl, out_label=out, filter_str=filt)


register(
    TransformSpec(
        id="video.subpixel_sharpen",
        kind="video",
        schema=SubpixelSharpenParams,
        build=_build_subpixel_sharpen,
        defaults={"luma_amount": 0.05, "radius": 5},
    )
)
