#!/usr/bin/env python3
"""
Generate brand assets from Origin Energy's own logo.

`origin_logo.svg` is Origin's official logo, taken from the header of
originenergy.com.au. It is their trademark, not ours -- see README.md in
this directory before doing anything with these files.

The source is a single vector path, so both the square icon and the
horizontal lockup are derived from it by adjusting the viewBox rather than
by cropping pixels. Nothing is redrawn or approximated.

Rendering goes through ImageMagick at 4x and downsamples. That matters:
ImageMagick's built-in SVG renderer approximates beziers with line
segments, and the curves of the "O" visibly facet if rendered straight to
the target size.

    python3 brands/make_assets.py brands

Needs ImageMagick (`magick`). No Python packages.

It also installs the four PNGs Home Assistant serves into
`custom_components/origin_energy/brand/`. Since 2026.3 the frontend asks
its own `/api/brands/integration/{domain}/{image}` endpoint, which checks a
custom integration's local `brand/` directory before falling back to the
CDN -- so shipping them there is what actually puts the icon in the UI.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = "origin_logo.svg"

# homeassistant/loader.py: has_branding is `"brand" in self._top_level_files`,
# so the directory name is load-bearing and there is no manifest flag.
INSTALL_DIR = Path("custom_components/origin_energy/brand")
INSTALL_FILES = ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png")

# Ink bounds of the source, measured from a 20x render (see README).
# The wordmark starts at x=38, so the mark is everything left of that.
MARK_W, MARK_H = 31.70, 28.55
LOGO_W, LOGO_H = 106.0, 32.0

# Breathing room around the mark in the square icon, as a fraction of its
# longest side. Home Assistant renders these as small tiles; a little air
# stops the mark colliding with the edge of the frame.
ICON_PADDING = 0.18

SUPERSAMPLE = 4


def square_viewbox():
    """A square viewBox centred on the mark, with padding."""
    side = max(MARK_W, MARK_H) * (1 + ICON_PADDING)
    return (MARK_W / 2 - side / 2, MARK_H / 2 - side / 2, side, side)


def rewrite(svg, viewbox, width, height):
    svg = re.sub(r'viewBox="[^"]*"', f'viewBox="{viewbox}"', svg, count=1)
    svg = re.sub(r'\swidth="[^"]*"', f' width="{width}"', svg, count=1)
    svg = re.sub(r'\sheight="[^"]*"', f' height="{height}"', svg, count=1)
    # The <title> travels with the file; keep it accurate.
    return re.sub(r"<title>.*?</title>", "<title>Origin Energy</title>", svg, flags=re.S)


def render(svg_text, out_path, width, height, tmp):
    """Rasterise via a supersampled intermediate, then downsample."""
    big = rewrite(svg_text, _viewbox_of(svg_text),
                  width * SUPERSAMPLE, height * SUPERSAMPLE)
    tmp.write_text(big)
    subprocess.run(
        ["magick", "-background", "none", str(tmp),
         "-filter", "Lanczos", "-resize", f"{width}x{height}!",
         f"PNG32:{out_path}"],
        check=True,
    )
    print(f"  {out_path.name:20} {width}x{height}")


def _viewbox_of(svg):
    return re.search(r'viewBox="([^"]*)"', svg).group(1)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    source = (out / SOURCE).read_text()
    tmp = out / "_render.svg"

    vb = square_viewbox()
    icon_svg = rewrite(source, " ".join(f"{v:.4g}" for v in vb), 256, 256)
    (out / "icon.svg").write_text(icon_svg)
    print(f"  {'icon.svg':20} viewBox {' '.join(f'{v:.4g}' for v in vb)}")

    logo_svg = rewrite(source, f"0 0 {LOGO_W:g} {LOGO_H:g}", 512, 155)
    (out / "logo.svg").write_text(logo_svg)
    print(f"  {'logo.svg':20} viewBox 0 0 {LOGO_W:g} {LOGO_H:g}")

    try:
        for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
            render(icon_svg, out / name, size, size, tmp)

        # Home Assistant's brands repository caps the longest side at 512
        # for logo.png and 1024 for the @2x variant.
        for name, width in (("logo.png", 512), ("logo@2x.png", 1024)):
            render(logo_svg, out / name, width, round(width * LOGO_H / LOGO_W), tmp)
    finally:
        tmp.unlink(missing_ok=True)

    # No dark_* variants. Origin's orange sits on transparency and stays
    # legible on both themes, and the proxy's IMAGE_FALLBACKS already maps
    # every dark_* request onto the light equivalent, so supplying them
    # would be duplication rather than coverage.
    install = Path(__file__).resolve().parent.parent / INSTALL_DIR
    install.mkdir(parents=True, exist_ok=True)
    for name in INSTALL_FILES:
        shutil.copy2(out / name, install / name)
    print(f"  installed {len(INSTALL_FILES)} file(s) -> {INSTALL_DIR}/")


if __name__ == "__main__":
    main()
