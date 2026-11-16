"""Replace the app icon with your own artwork:  python -m app.icons path/to/icon.png

Takes any image, crops the largest centred square and writes the three sizes the home screen and browser use.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

STATIC = Path(__file__).resolve().parent / "static"
SIZES = (180, 192, 512)


def make_icons(source: str, out_dir: Path = STATIC) -> list[Path]:
    img = cv2.imread(source, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read an image from {source}")
    h, w = img.shape[:2]
    side = min(h, w)
    y0, x0 = (h - side) // 2, (w - side) // 2
    square = img[y0:y0 + side, x0:x0 + side]
    written = []
    for size in SIZES:
        path = out_dir / f"icon-{size}.png"
        cv2.imwrite(str(path), cv2.resize(square, (size, size), interpolation=cv2.INTER_AREA))
        written.append(path)
    return written


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for path in make_icons(sys.argv[1]):
        print("wrote", path)
