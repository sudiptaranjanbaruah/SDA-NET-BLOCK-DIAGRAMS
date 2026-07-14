# Figures — which file to open

## Two versions of every diagram

| Version | Where | Use it for |
|---|---|---|
| **Simple** (bold colours, plain English, only the essentials) | `simple/` | **The default.** Slides, the poster, anyone who is not reading the code. |
| Detailed (every tensor shape, function name, and hyper-parameter) | top level | The paper's appendix, or defending a claim in Q&A. |

Both versions carry the same five diagrams (D1–D5) and the same honesty markers. The simple
set is the one to show people; the detailed set is the one to check facts against.

Each version has the same three renderings — **pick by tool:**

| You are… | Use | Why |
|---|---|---|
| **Editing in Adobe Illustrator** | `pdf/*.pdf` | Opens natively, fully editable vectors, no SVG-importer quirks. **Start here.** |
| Editing in Figma / Inkscape / a browser | `ai/*_ai.svg` | Flattened SVG — no CSS, no markers, no patterns. Also opens in Illustrator. |
| Re-authoring the diagram itself | `D*.svg` | The hand-authored source. Edit these, then re-run the exports below. |
| Dropping a picture into a doc | `D*_check.png` | Raster previews. |

So for a slide, the file you want is **`simple/pdf/D1_system_overview.pdf`**.

## Why the Illustrator-safe variants exist

Opening the authored `D*.svg` in Illustrator made **most of the connector lines disappear.**
Illustrator's SVG importer is much stricter than a browser's, and the authored files use three
constructs it handles badly:

1. **`<marker>`** — the arrowheads. Illustrator often drops the marker, and in some versions drops
   the whole stroked path along with it. This is the most likely cause of the vanishing lines.
2. **`<style>`** — an internal CSS block. Support is partial; elements whose fill or font comes
   only from a class can lose it entirely.
3. **`<pattern>`** — the hatch fill on D4's crossed-out "joint network" box.

`make_illustrator_safe.py` removes all three rather than guessing which one bit:

- every CSS class is resolved into presentation attributes on the element itself
- every arrowhead becomes an explicit `<polygon>` triangle, computed from each path's end point
  and direction, sized to match what the marker drew (length = `markerWidth` × stroke-width)
- the hatch becomes a plain fill
- runs of 2+ spaces become non-breaking spaces, so monospace columns stay aligned without
  `white-space: pre` (Chrome honors that rule; Illustrator ignores it — and `xml:space="preserve"`
  is ignored by *Chrome*, so neither mechanism works everywhere. NBSP works in both.)

The flattened output was re-rendered and diffed against the originals: geometry-identical.

## Regenerating

```bash
# 1. flatten:  D*.svg  →  ai/D*_ai.svg
python figures/make_illustrator_safe.py

# 2. rasterize a preview (no rsvg/ImageMagick on this machine — use Chrome)
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless --disable-gpu --screenshot=D1_check.png \
          --window-size=1460,2170 --default-background-color=FFFFFF --hide-scrollbars \
          "file://$PWD/figures/D1_system_overview.svg"
```

PDFs are produced by wrapping each flattened SVG in an HTML page with
`@page { size: <W>px <H>px; margin: 0 }` and running Chrome with `--print-to-pdf`.
Verified: 1 page each, correct dimensions, **0 raster bitmaps**, all text embedded as real fonts.

## Canvas sizes (px)

D1 1460×2170 (portrait — this is paper Figure 1) · D2 1800×1360 · D3 1800×1070 ·
D4 1800×1460 · D5 1800×1380

## Fonts

Authored for Inter + JetBrains Mono. Neither is installed here, so the PDFs embed the
substitutes Chrome picked (Helvetica Neue / Menlo / Arial). Install the real fonts before the
final export if you want the intended typography — the text stays live and editable either way.

## Known caveat

These are the **light / print** variants. `SLIDE_PROMPTS.md` specifies a dark slate deck
(`#0F172A` background), so slide versions need the palette inverted — not yet done.
# SDA-NET-BLOCK-DIAGRAMS
