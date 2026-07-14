"""
Flatten the D1–D5 SVGs into an Illustrator-safe form.

Illustrator's SVG importer is far stricter than a browser's. Three constructs in the
authored files are known to render in Chrome but drop or mangle in Illustrator:

  1. <marker>  — arrowheads referenced via marker-end. Illustrator frequently drops the
                 marker, and in some versions drops the whole stroked path with it. This
                 is the "most of the lines disappear" symptom.
  2. <style>   — an internal CSS block. Illustrator's support is partial; elements whose
                 fill/font come only from a class can lose them entirely.
  3. <pattern> — the hatch fill in D4.

Rather than guess which one bit, this strips all three:

  · every CSS class is resolved into presentation attributes on the element itself
  · every arrowhead becomes an explicit <polygon> triangle, computed from the path's
    end point and direction (matching what the marker drew: length = markerWidth · stroke-width,
    half-width = markerHeight/2 · stroke-width, tip on the end point)
  · the hatch pattern becomes a plain fill
  · runs of 2+ spaces become non-breaking spaces, so monospace columns stay aligned
    without needing `white-space: pre` (which Illustrator ignores)

Output: figures/ai/<name>_ai.svg — geometry-identical, no defs, no CSS, no markers.

Usage:  python figures/make_illustrator_safe.py
"""

from __future__ import annotations

import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "ai"          # rebound in __main__ when a source dir is passed

# CSS declarations that map cleanly onto SVG presentation attributes.
PRESENTATION_PROPS = {
    "font-size", "font-weight", "font-family", "font-style", "fill",
    "fill-opacity", "stroke", "stroke-width", "letter-spacing", "text-anchor",
}

# Arrowhead geometry, taken from the <marker> definitions in the authored files:
#   markerWidth -> triangle length, markerHeight/2 -> half base, both in stroke-width units.
MARKER_GEOM = {
    "a-amber": (8, 3), "a-cyan": (8, 3), "a-violet": (8, 3),
    "a-slate": (8, 3), "a-green": (8, 3), "a-red": (8, 3),
    "a-sm": (6, 2.5),
}


def parse_css(style_text: str) -> dict[str, dict[str, str]]:
    """Pull `.cls { prop: val; ... }` rules out of the <style> block."""
    rules: dict[str, dict[str, str]] = {}
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style_text):
        decls = {}
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            prop, _, val = decl.partition(":")
            prop, val = prop.strip(), val.strip()
            if prop in PRESENTATION_PROPS:
                decls[prop] = val
        for sel in selector.split(","):
            sel = sel.strip()
            if sel.startswith("."):
                rules[sel[1:]] = decls
    return rules


def path_points(d: str) -> list[tuple[float, float]]:
    """Absolute on-path vertices for the M/L/H/V/A/C subset these figures use."""
    pts: list[tuple[float, float]] = []
    cur = (0.0, 0.0)
    for cmd, args in re.findall(r"([MLAHVCZmlahvcz])([^MLAHVCZmlahvcz]*)", d):
        nums = [float(n) for n in re.findall(r"-?\d*\.?\d+", args)]
        if cmd in "ML":
            for i in range(0, len(nums) - 1, 2):
                cur = (nums[i], nums[i + 1])
                pts.append(cur)
        elif cmd == "A":                      # arc: endpoint is the last 2 of each 7
            for i in range(0, len(nums) - 6, 7):
                cur = (nums[i + 5], nums[i + 6])
                pts.append(cur)
        elif cmd == "C":                      # cubic: endpoint is the last 2 of each 6
            for i in range(0, len(nums) - 5, 6):
                cur = (nums[i + 4], nums[i + 5])
                pts.append(cur)
        elif cmd == "H":
            for n in nums:
                cur = (n, cur[1])
                pts.append(cur)
        elif cmd == "V":
            for n in nums:
                cur = (cur[0], n)
                pts.append(cur)
    return pts


def arrow_polygon(pts, marker_id, stroke, stroke_width):
    """Build the triangle the <marker> used to draw at the end of this path."""
    if len(pts) < 2:
        return None
    tip = pts[-1]
    prev = next((p for p in reversed(pts[:-1]) if p != tip), None)
    if prev is None:
        return None

    dx, dy = tip[0] - prev[0], tip[1] - prev[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return None
    ux, uy = dx / length, dy / length          # direction of travel
    px, py = -uy, ux                           # perpendicular

    mlen, mhalf = MARKER_GEOM.get(marker_id, (8, 3))
    L, H = mlen * stroke_width, mhalf * stroke_width

    base = (tip[0] - ux * L, tip[1] - uy * L)
    a = (base[0] + px * H, base[1] + py * H)
    b = (base[0] - px * H, base[1] - py * H)

    poly = ET.Element(f"{{{SVG_NS}}}polygon")
    poly.set("points", " ".join(f"{x:.2f},{y:.2f}" for x, y in (tip, a, b)))
    poly.set("fill", stroke)                   # match the line it terminates
    poly.set("stroke", "none")
    return poly


def nbsp(s: str | None) -> str | None:
    """Repeated spaces collapse in SVG; NBSP survives in both Chrome and Illustrator."""
    if not s:
        return s
    return re.sub(r" {2,}", lambda m: " " * len(m.group()), s)


def flatten(src: Path) -> Path:
    tree = ET.parse(src)
    root = tree.getroot()

    # ── 1. resolve the CSS block, then delete it ──────────────────────────────
    css: dict[str, dict[str, str]] = {}
    for parent in root.iter():
        for style_el in list(parent):
            if style_el.tag == f"{{{SVG_NS}}}style":
                css = parse_css(style_el.text or "")
                parent.remove(style_el)

    # ── 2. collect + drop <marker> and <pattern> defs ─────────────────────────
    for parent in root.iter():
        for child in list(parent):
            if child.tag in (f"{{{SVG_NS}}}marker", f"{{{SVG_NS}}}pattern"):
                parent.remove(child)

    # ── 3. walk the tree: inline classes, materialise arrowheads, fix spacing ──
    for parent in root.iter():
        new_children = []
        for el in list(parent):
            # class -> presentation attributes (an explicit attribute already on the
            # element wins, which is how these files were authored and rendered)
            cls = el.get("class")
            if cls:
                for name in cls.split():
                    for prop, val in css.get(name, {}).items():
                        if el.get(prop) is None:
                            el.set(prop, val)
                del el.attrib["class"]

            # marker-end -> explicit polygon
            mk = el.get("marker-end")
            if mk:
                marker_id = mk.strip()[len("url(#"):-1]
                stroke = el.get("stroke", "#000000")
                sw = float(el.get("stroke-width", "1"))
                if el.tag == f"{{{SVG_NS}}}line":
                    pts = [(float(el.get("x1")), float(el.get("y1"))),
                           (float(el.get("x2")), float(el.get("y2")))]
                else:
                    pts = path_points(el.get("d", ""))
                poly = arrow_polygon(pts, marker_id, stroke, sw)
                if poly is not None:
                    new_children.append(poly)
                del el.attrib["marker-end"]

            # the hatch pattern no longer exists
            if el.get("fill", "").startswith("url(#hatch"):
                el.set("fill", "#FEE2E2")

            if el.tag in (f"{{{SVG_NS}}}text", f"{{{SVG_NS}}}tspan"):
                el.text = nbsp(el.text)
                for sub in el.iter():
                    sub.text = nbsp(sub.text)
                    sub.tail = nbsp(sub.tail)

        for poly in new_children:
            parent.append(poly)                # arrowheads paint last, on top

    # ── 4. drop any now-empty <defs> ─────────────────────────────────────────
    for parent in root.iter():
        for child in list(parent):
            if child.tag == f"{{{SVG_NS}}}defs" and len(child) == 0:
                parent.remove(child)

    OUT_DIR.mkdir(exist_ok=True)
    dst = OUT_DIR / f"{src.stem}_ai.svg"
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    return dst


if __name__ == "__main__":
    import sys

    src_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE
    OUT_DIR = src_dir / "ai"
    for src in sorted(src_dir.glob("D*.svg")):
        dst = flatten(src)
        print(f"{src.parent.name}/{src.name:28s} → {dst.parent.parent.name}/ai/{dst.name}")
