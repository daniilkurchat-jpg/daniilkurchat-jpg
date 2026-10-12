#!/usr/bin/env python3
"""Prepare a photo for the ASCII portrait: isolate the subject, crop square,
smooth away noise, stretch the tones so skin reads light and features dark,
and save a grayscale PNG on a white background.

    python scripts/prep_photo.py source-photo.jpg [source-prepped.png]
        --crop x0,y0,x1,y1   crop box in source pixels (default: around the subject)
        --bg auto|flood|none background removal (default auto: rembg if installed,
                             otherwise a flood fill from the picture edges)
        --tolerance N        flood-fill colour tolerance, 0-255 (default 40)
        --line N             how strongly to darken detected lines, 0-1 (default 0.5)
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

ap = argparse.ArgumentParser()
ap.add_argument("src", nargs="?", default=os.path.join(ROOT, "source-photo.png"))
ap.add_argument("out", nargs="?", default=os.path.join(ROOT, "source-prepped.png"))
ap.add_argument("--crop", default=None)
ap.add_argument("--bg", default="auto", choices=["auto", "flood", "none"])
ap.add_argument("--tolerance", type=int, default=40)
ap.add_argument("--line", type=float, default=0.5)
ap.add_argument("--size", type=int, default=1000)
args = ap.parse_args()

im = ImageOps.exif_transpose(Image.open(args.src)).convert("RGB")
if args.crop:
    im = im.crop(tuple(int(v) for v in args.crop.split(",")))


def mask_with_rembg(image):
    try:
        from rembg import remove  # optional, heavy
    except ImportError:
        return None
    return remove(image.convert("RGBA")).split()[-1]


def mask_with_flood(image, tolerance):
    """Everything reachable from the picture edges within `tolerance` of the
    edge colour is background. Works for plain walls, studio backdrops, sky."""
    work = image.filter(ImageFilter.GaussianBlur(1.5)).convert("RGB")
    marker = (255, 0, 255)
    w, h = work.size
    seeds = [(1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2), (w // 2, 1), (1, h // 2), (w - 2, h // 2)]
    for seed in seeds:
        if work.getpixel(seed) != marker:
            ImageDraw.floodfill(work, seed, marker, thresh=tolerance)
    arr = np.array(work)
    bg = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 255)
    return Image.fromarray(np.where(bg, 0, 255).astype(np.uint8), "L")


mask = None
if args.bg == "auto":
    mask = mask_with_rembg(im) or mask_with_flood(im, args.tolerance)
elif args.bg == "flood":
    mask = mask_with_flood(im, args.tolerance)
if mask is None:
    mask = Image.new("L", im.size, 255)

alpha = np.array(mask).astype(np.float32) / 255.0
if (alpha > 0.5).sum() < 0.02 * alpha.size:
    sys.exit("subject mask is almost empty; try --bg none or a larger --tolerance")

# crop square around the subject with a margin
ys, xs = np.where(alpha > 0.5)
cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
side = int(max(xs.max() - xs.min(), ys.max() - ys.min()) * 1.12)
box = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)
im = im.crop(box)
mask = mask.crop(box)

# grayscale, denoise, tone stretch, line darkening
gray = im.convert("L").filter(ImageFilter.MedianFilter(5))
g = np.array(gray).astype(np.float32)
a = np.array(mask).astype(np.float32) / 255.0
subject = g[a > 0.5]
lo, hi = np.percentile(subject, [2, 92])
tone = np.clip((g - lo) / max(hi - lo, 1.0), 0, 1)

fine = np.array(gray.filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32)
coarse = np.array(gray.filter(ImageFilter.GaussianBlur(6))).astype(np.float32)
lines = np.clip((coarse - fine) / 40.0, 0, 1)         # thin dark strokes: eyes, brows, mouth
out = np.clip(tone - args.line * lines, 0, 1) * 255

feather = np.array(mask.filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32) / 255.0
out = out * feather + 255.0 * (1.0 - feather)

result = Image.fromarray(out.astype(np.uint8), "L").resize((args.size, args.size), Image.LANCZOS)
result.save(args.out)
print(f"wrote {args.out} {result.size}, subject covers {(a > 0.5).mean():.0%} of the crop")
