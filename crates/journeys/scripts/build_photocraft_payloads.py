#!/usr/bin/env python3
"""Build deterministic layered PSD workloads from the pinned source corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tomllib

from PIL import Image, ImageOps
from psd_tools import PSDImage


PHOTO_NAMES = ("iss050e013545.jpg", "iss048e046434.jpg", "iss035e013332.jpg")
LICENSED_FIXTURES = {"adjustment-mask.psd", "layer_effects.psd"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cover(image: Image.Image, size: tuple[int, int], seed: int) -> Image.Image:
    x = ((seed * 17) % 7 + 1) / 8
    y = ((seed * 13) % 7 + 1) / 8
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(x, y))


def add_photo_patches(psd: PSDImage, photos: list[Image.Image], width: int, height: int, count: int, tier: str) -> None:
    tile_w, tile_h = ((1600, 1200) if tier == "typical" else (1800, 1350))
    for index in range(count - 2):
        photo_index = index % len(photos)
        left = (index * 997 + (index // 4) * 131) % (width - tile_w + 1)
        top = (index * 613 + (index // 3) * 79) % (height - tile_h + 1)
        image = cover(photos[photo_index], (tile_w, tile_h), index + 1)
        psd.create_pixel_layer(
            image,
            name=f"NASA photo patch {index + 1:02d} — {PHOTO_NAMES[photo_index].split('.')[0]}",
            top=top,
            left=left,
            opacity=208 + (index % 4) * 12,
        )

def build(tier: str, corpus: Path, out: Path) -> dict:
    width, height, raster_count, effect_count = (4000, 3000, 12, 3) if tier == "typical" else (5000, 4800, 31, 11)
    sources = {p.name: p for p in corpus.iterdir() if p.is_file()}
    for name in (*PHOTO_NAMES, *LICENSED_FIXTURES):
        if name not in sources:
            raise FileNotFoundError(f"corpus source missing: {name}")
    manifest_path = Path(__file__).parents[2] / "corpus" / "manifests" / "photocraft-latency-2026.toml"
    manifest = tomllib.loads(manifest_path.read_text())
    expected = {row["path"]: row["sha256"] for row in manifest["file"]}
    for name in (*PHOTO_NAMES, *LICENSED_FIXTURES):
        actual = sha256(sources[name])
        if actual != expected[name]:
            raise ValueError(f"SHA-256 mismatch for {name}: {actual}")

    photos = [Image.open(sources[name]).convert("RGB") for name in PHOTO_NAMES]
    psd = PSDImage.new(mode="RGB", size=(width, height), depth=8)

    # psd-tools appends each new layer to the top of the stack. Build bottom-to-top so the
    # selected, translucent full-canvas photo is last and its underlying photo/adjustment/effect
    # layers remain visible in the composite.
    psd.create_pixel_layer(cover(photos[0], (width, height), 202), name="Background — NASA river")
    add_photo_patches(psd, photos, width, height, raster_count, tier)

    # Copy one real Photoshop adjustment layer plus actual Photoshop effects from the pinned
    # MIT-licensed psd-tools test fixtures. These retain their native PSD records and effects.
    adjustment_doc = PSDImage.open(sources["adjustment-mask.psd"])
    list(adjustment_doc)[1].copy_to(psd)
    effects_doc = PSDImage.open(sources["layer_effects.psd"])
    for layer in list(effects_doc)[1 : 1 + effect_count]:
        layer.copy_to(psd)

    # The selected top raster spans the canvas and offers a large move/brush target.
    psd.create_pixel_layer(cover(photos[1], (width, height), 101), name="Large move target — NASA clouds", opacity=205)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"photocraft-{tier}-layered.psd"
    psd.save(path)
    check = PSDImage.open(path)
    layers = list(check)
    adjustment_layers = [layer.name for layer in layers if layer.kind == "brightnesscontrast"]
    effect_layers = [layer.name for layer in layers if getattr(layer, "effects", None)]
    if check.size != (width, height) or check.depth != 8 or len(layers) != raster_count + effect_count + 1:
        raise RuntimeError(f"generated PSD metadata mismatch: size={check.size}, depth={check.depth}, layers={len(layers)}")
    if len(adjustment_layers) != 1 or len(effect_layers) < effect_count:
        raise RuntimeError(f"generated PSD missing adjustment/effect layers: {adjustment_layers=}, {effect_layers=}")
    return {
        "tier": tier,
        "path": str(path),
        "sha256": sha256(path),
        "dimensions": [width, height],
        "megapixels": width * height / 1_000_000,
        "layers": len(layers),
        "raster_layers": raster_count,
        "adjustment_layers": adjustment_layers,
        "effect_layers": effect_layers,
        "bit_depth": check.depth,
        "license": "Constructed: NASA public-domain photographs; native adjustment/effect layers from MIT-licensed psd-tools fixtures.",
        "recipe": "See crates/journeys/README.md#photocraft-session-latency-hyper-291.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path, help="craft-corpus fetch directory")
    parser.add_argument("out", type=Path, help="generated payload directory outside the stamped corpus")
    parser.add_argument("--tier", choices=("typical", "heavy", "both"), default="both")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tiers = ("typical", "heavy") if args.tier == "both" else (args.tier,)
    report = [build(tier, args.corpus.resolve(), args.out.resolve()) for tier in tiers]
    report_path = args.out / "payload-manifest.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(report_path.read_text(), end="")


if __name__ == "__main__":
    main()
