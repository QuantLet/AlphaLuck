"""Preview publication figures on white and check the opaque-background contract.

The white plotting surface and black type are intentional for manuscript
legibility. Check sheets add a white margin around each exported figure.
"""
from __future__ import annotations

import glob
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style

OUT = os.path.join(style.FIGDIR, "_check")
WHITE = (255, 255, 255)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    names = sorted(glob.glob(os.path.join(style.FIGDIR, "*.png")))
    if not names:
        raise SystemExit("no figures found")
    for p in names:
        name = os.path.splitext(os.path.basename(p))[0]
        im = Image.open(p).convert("RGBA")
        alpha = im.getchannel("A")
        opaque = alpha.getextrema() == (255, 255)
        w, h = im.size
        pad = 14
        sheet = Image.new("RGB", (w + pad * 2, h + pad * 2), WHITE)
        sheet.paste(im, (pad, pad), im)
        sheet.save(os.path.join(OUT, f"{name}_check.png"))
        flag = "  <-- REGENERATE FOR WHITE BACKGROUND" if not opaque else ""
        print(f"  {name}: {w}x{h}px opaque={opaque}{flag}")
    print(f"\ncheck sheets in {os.path.relpath(OUT, style.ROOT)}")


if __name__ == "__main__":
    main()
