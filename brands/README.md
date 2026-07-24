# Brand assets

Origin Energy's logo, prepared at the sizes Home Assistant's brands
repository expects.

> **These are Origin Energy Limited's trademarks, not this project's.**
> This integration is independent and unofficial — not affiliated with,
> endorsed by, or sponsored by Origin Energy. The logo is here solely to
> identify the service the integration connects to. It is **not** covered
> by this project's MIT licence. Read [TRADEMARKS.md](../TRADEMARKS.md).

## Files

This directory is the workshop. The files Home Assistant actually serves
are the copies in `custom_components/origin_energy/brand/`, which
`make_assets.py` installs — see
[below](#how-home-assistant-picks-these-up).

| File | Size | Use |
|---|---|---|
| `origin_logo.svg` | vector | **the source** — Origin's official logo, unmodified |
| `icon.svg` | vector | the "O" mark alone, square viewBox |
| `icon.png` | 256×256 | the square icon Home Assistant displays |
| `icon@2x.png` | 512×512 | high-DPI variant |
| `logo.svg` | vector | full horizontal lockup |
| `logo.png` | 512×155 | lockup raster |
| `logo@2x.png` | 1024×309 | high-DPI variant |

There are deliberately no `dark_*` variants. Origin's orange sits on
transparency and stays legible on both light and dark Home Assistant
themes, and the proxy resolves dark requests onto these files anyway.

## Where the source came from

`origin_logo.svg` is the logo inlined in the header of
`originenergy.com.au`, marked up on their own site as
`<title>Origin Energy Logo</title>`. It is a single vector path, which is
what makes the rest of this reproducible without redrawing anything.

## How the derivatives are made

`make_assets.py` produces everything from that one file. Both outputs are
made by **changing the viewBox**, not by cropping pixels or tracing — the
artwork is never altered:

- **icon** — a square viewBox centred on the mark. Measured from a 20×
  render, the mark's ink occupies `x 0–31.70`, `y 0–28.55`, and the
  wordmark starts at `x 38`. The square is the longer side plus 18%
  padding, so the mark doesn't collide with the edge of a small tile.
- **logo** — the source viewBox untouched (`0 0 106 32`), which is already
  tight to the ink on all four sides.

```bash
python3 brands/make_assets.py brands
```

It needs ImageMagick and no Python packages.

Rendering goes through a 4× intermediate and downsamples. This is not
premature polish: ImageMagick's built-in SVG renderer approximates béziers
with line segments, and the curves of the "O" visibly facet if rendered
straight to 256px.

## If you'd rather not ship a trademark

An original mark — an amber bolt on an indigo tile, drawn for this project
and owned by it — was used before this and is still in the git history.
`git log -- brands/` will find it. It is the safer choice if you are
uneasy about redistributing Origin's marks, at the cost of being less
recognisable to users.

## How Home Assistant picks these up

Since **2026.3** the frontend no longer hits the brands CDN directly. It
asks Home Assistant's own
[brands proxy](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/)
at `/api/brands/integration/{domain}/{image}`, and that endpoint checks a
custom integration's local files *before* falling back to the CDN.

So the icon ships with the integration — no pull request, no CDN round
trip, and it works offline. `make_assets.py` installs the four PNGs into:

```
custom_components/origin_energy/brand/
    icon.png   icon@2x.png   logo.png   logo@2x.png
```

Two details from `homeassistant/components/brands/` worth knowing, because
neither is obvious:

- **The directory must be named `brand`** (singular). `loader.py` defines
  `has_branding` as `"brand" in self._top_level_files`, and the proxy skips
  any integration where that is false. There is no manifest flag — the
  directory name *is* the flag.
- **`dark_*` variants are unnecessary.** The proxy's `IMAGE_FALLBACKS`
  chain already resolves every `dark_*` request onto its light equivalent,
  so all eight allowed image names serve correctly from these four files.

On older versions the CDN is the only route, in which case the icon falls
back to a generic placeholder unless it is submitted to
[home-assistant/brands](https://github.com/home-assistant/brands) (for
custom integrations, under `custom_integrations/origin_energy/`). These
files are shaped for that too, but it is no longer necessary.
