"""Deterministic SVG diagram renderer (plan §15.1).

The model is *terrible* at SVG layout: it emits absolute coordinates blind, so text
overflows its boxes and edge labels collide no matter how hard the prompt tries (two
prompt rounds did not fix it). So we stop asking the model to do layout. It produces a
**structured `DiagramSpec`** (nodes, edges, labels, archetype - things an LLM is good at)
and THIS module measures text and places everything on a grid, where overlap is
impossible by construction.

Two layouts cover the bulk of technical figures:
  - **flow**     - column-ranked left->right DAG (pipelines, architectures, decision flows)
  - **layered**  - named horizontal lanes (stacks, request paths)
`cycle`/`comparison` degrade to `flow` (still clean, still overlap-free).

Arrowheads are drawn as explicit triangles, not just an SVG `<marker>` - the PDF exporter
(svglib) ignores markers, so a marker-only arrow vanishes in PDF. Every connector also
carries fill="none" (a filled path renders as a black blob).
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile

from . import schemas as S

# ── Geometry / type constants ─────────────────────────────────────────────────
FONT = "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif"
MARGIN = 40
TITLE_TOP = 34          # title baseline
SUB_TOP = 55            # subtitle baseline
COL_GAP = 74
ROW_GAP = 26
PAD_X, PAD_Y = 14, 11
LABEL_SIZE, DETAIL_SIZE = 14, 11
LABEL_LH, DETAIL_LH = 17, 14
TITLE_SIZE, SUB_SIZE, EDGE_SIZE, LANE_SIZE, LEG_SIZE = 20, 13, 11, 11, 11
MAX_INNER, MIN_BOX_W = 168, 116
CH_GAP = 16             # vertical spacing between stacked edge channels
MAX_NODES, MAX_EDGES = 12, 24

_INK = "#1a1a1a"
_MUTED = "#5b6470"
_EDGE = "#64748b"
_BG = "#f8f9fb"
_NEUTRAL = "#64748b"
# One colour = one category, used consistently; assigned in first-seen group order.
_PALETTE = ["#4f8ef7", "#34c98a", "#ff6719", "#a78bfa", "#e5534b", "#0ea5e9"]

# Per-character advance widths (relative to font size) - a cheap but decent text
# metric so boxes are sized to their text and labels wrap before they overflow.
_NARROW = set("iljftI.,;:'!|()[]{}/\\ ")
_WIDE = set("mwMW@%")


def _char_w(c: str) -> float:
    if c in _NARROW:
        return 0.30
    if c in _WIDE:
        return 0.92
    if c.isupper() or c.isdigit():
        return 0.62
    return 0.54


def _text_w(s: str, size: float) -> float:
    return size * sum(_char_w(c) for c in s)


def _wrap(text: str, max_w: float, size: float) -> list[str]:
    """Greedy word-wrap to `max_w` px; hard-breaks any single word that is too long."""
    out: list[str] = []
    cur = ""
    for word in (text or "").split():
        trial = f"{cur} {word}".strip()
        if not cur or _text_w(trial, size) <= max_w:
            cur = trial
            continue
        out.append(cur)
        if _text_w(word, size) > max_w:           # a single over-long token: char-break it
            piece = ""
            for ch in word:
                if piece and _text_w(piece + ch, size) > max_w:
                    out.append(piece)
                    piece = ch
                else:
                    piece += ch
            cur = piece
        else:
            cur = word
    if cur:
        out.append(cur)
    return out or [""]


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


# ── Public entry ──────────────────────────────────────────────────────────────
def render_spec(spec: S.DiagramSpec) -> str:
    """Render a validated DiagramSpec to a standalone SVG string (starts with '<svg')."""
    nodes = list(spec.nodes)[:MAX_NODES]
    ids = {n.id for n in nodes}
    edges = [e for e in spec.edges
             if e.source in ids and e.target in ids and e.source != e.target][:MAX_EDGES]
    if not nodes:
        return placeholder(spec.title or "Diagram")
    arche = spec.archetype if spec.archetype in ("flow", "layered", "cycle", "comparison") else "flow"
    if arche == "layered" and any(n.lane for n in nodes):
        return _render_layered(spec, nodes, edges)
    if arche == "cycle" and len(nodes) >= 3:
        return _render_cycle(spec, nodes, edges)
    if arche == "comparison" and len(_group_colors(nodes)) >= 2:
        return _render_comparison(spec, nodes, edges)
    return _render_flow(spec, nodes, edges)


def placeholder(title: str) -> str:
    """A minimal, valid figure used when no spec/SVG could be produced."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="760" height="120" '
        'viewBox="0 0 760 120"><rect width="760" height="120" fill="#f8f9fb" rx="10"/>'
        f'<text x="380" y="66" text-anchor="middle" font-family="{FONT}" '
        f'font-size="15" fill="#5b6470">{_esc(title)}</text></svg>'
    )


# ── Shared rendering pieces ───────────────────────────────────────────────────
def _group_colors(nodes) -> dict[str, str]:
    colors: dict[str, str] = {}
    for n in nodes:
        g = (n.group or "").strip()
        if g and g not in colors:
            colors[g] = _PALETTE[len(colors) % len(_PALETTE)]
    return colors


def _box_size(nodes) -> tuple[dict, int, int, bool]:
    """Uniform box size for tidy alignment: wrap every label, take the widest line and
    the most lines so all boxes share one footprint (and nothing ever overflows)."""
    wrapped, widest, most_lines = {}, float(MIN_BOX_W - 2 * PAD_X), 1
    has_detail = any((n.detail or "").strip() for n in nodes)
    for n in nodes:
        lines = _wrap(n.label, MAX_INNER, LABEL_SIZE)
        wrapped[n.id] = lines
        most_lines = max(most_lines, len(lines))
        widest = max(widest, *[_text_w(ln, LABEL_SIZE) for ln in lines])
        if (n.detail or "").strip():
            widest = max(widest, _text_w(n.detail, DETAIL_SIZE))
    box_w = int(min(MAX_INNER + 2 * PAD_X, max(MIN_BOX_W, widest + 2 * PAD_X)))
    box_h = int(2 * PAD_Y + most_lines * LABEL_LH + (DETAIL_LH if has_detail else 0))
    return wrapped, box_w, box_h, has_detail


def _node_svg(n, x, y, w, h, lines, color, focus) -> str:
    cx = x + w / 2
    label_block = len(lines) * LABEL_LH + (DETAIL_LH if (n.detail or "").strip() else 0)
    first = y + (h - label_block) / 2 + LABEL_SIZE * 0.82
    sw = 2.6 if focus else 1.6
    parts = [
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="9" '
        f'fill="{color}" fill-opacity="0.14" stroke="{color}" stroke-width="{sw}"/>',
        f'<text x="{cx:.0f}" y="{first:.0f}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="{LABEL_SIZE}" font-weight="600" fill="{_INK}">',
    ]
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else LABEL_LH
        parts.append(f'<tspan x="{cx:.0f}" dy="{dy}">{_esc(ln)}</tspan>')
    parts.append("</text>")
    if (n.detail or "").strip():
        dy = first + (len(lines) - 1) * LABEL_LH + DETAIL_LH
        parts.append(
            f'<text x="{cx:.0f}" y="{dy:.0f}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="{DETAIL_SIZE}" fill="{_MUTED}">{_esc(n.detail)}</text>')
    return "<g>" + "".join(parts) + "</g>"


def _arrow(x: float, y: float, direction: str) -> str:
    """Explicit arrowhead triangle (markers are dropped by the PDF renderer)."""
    s = 5.5
    pts = {
        "right": f"{x},{y} {x - 2 * s},{y - s} {x - 2 * s},{y + s}",
        "left":  f"{x},{y} {x + 2 * s},{y - s} {x + 2 * s},{y + s}",
        "down":  f"{x},{y} {x - s},{y - 2 * s} {x + s},{y - 2 * s}",
        "up":    f"{x},{y} {x - s},{y + 2 * s} {x + s},{y + 2 * s}",
    }[direction]
    return f'<polygon points="{pts}" fill="{_EDGE}"/>'


def _path(d: str) -> str:
    return f'<path d="{d}" fill="none" stroke="{_EDGE}" stroke-width="1.6"/>'


def _arrow_at(x: float, y: float, angle: float) -> str:
    """Arrowhead whose tip is (x, y), pointing along `angle` radians (for non-orthogonal
    edges in the cycle/comparison layouts)."""
    s = 5.5
    bx, by = x - 2 * s * math.cos(angle), y - 2 * s * math.sin(angle)
    px, py = -math.sin(angle) * s, math.cos(angle) * s
    return (f'<polygon points="{x:.1f},{y:.1f} {bx + px:.1f},{by + py:.1f} '
            f'{bx - px:.1f},{by - py:.1f}" fill="{_EDGE}"/>')


def _box_edge(cx: float, cy: float, hw: float, hh: float, tx: float, ty: float) -> tuple[float, float]:
    """Where the ray from a box centre (cx,cy) toward (tx,ty) crosses the box border."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return (cx, cy)
    sx = hw / abs(dx) if dx else math.inf
    sy = hh / abs(dy) if dy else math.inf
    s = min(sx, sy)
    return (cx + dx * s, cy + dy * s)


def _edge_label(x: float, y: float, text: str, placed: list, seen: set | None = None) -> str:
    """A white pill behind an edge label, nudged vertically to avoid earlier pills.

    `seen` (when given) de-duplicates repeated relationship labels: a comparison
    figure with three 'provides' edges should show 'provides' once, not stack three
    overlapping pills in the column gap."""
    if not text.strip():
        return ""
    if seen is not None:
        key = text.strip().lower()
        if key in seen:
            return ""
        seen.add(key)
    w = _text_w(text, EDGE_SIZE) + 12
    h = 17
    for _ in range(6):
        rect = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        if not any(_overlap(rect, r) for r in placed):
            break
        y += h + 3
    placed.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    return (f'<rect x="{x - w / 2:.0f}" y="{y - h / 2:.0f}" width="{w:.0f}" height="{h}" '
            f'rx="7" fill="{_BG}"/>'
            f'<text x="{x:.0f}" y="{y + 3.5:.0f}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="{EDGE_SIZE}" fill="{_MUTED}">{_esc(text)}</text>')


def _overlap(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _header(w: int, h: int, spec) -> list[str]:
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="{_BG}" rx="12"/>',
        f'<text x="{w / 2:.0f}" y="{TITLE_TOP}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="{TITLE_SIZE}" font-weight="700" fill="#111">{_esc(spec.title)}</text>',
    ]
    if (spec.subtitle or "").strip():
        out.append(
            f'<text x="{w / 2:.0f}" y="{SUB_TOP}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="{SUB_SIZE}" fill="{_MUTED}">{_esc(spec.subtitle)}</text>')
    return out


def _legend(nodes, colors, w: int, y: int) -> list[str]:
    """A horizontal legend strip centered at the bottom (never collides with content)."""
    if not colors:
        return []
    items = list(colors.items())
    widths = [22 + _text_w(g, LEG_SIZE) + 18 for g, _ in items]
    total = sum(widths)
    x = (w - total) / 2
    out = []
    for (g, c), wd in zip(items, widths, strict=True):
        out.append(f'<rect x="{x:.0f}" y="{y - 9}" width="11" height="11" rx="2" '
                   f'fill="{c}" fill-opacity="0.6" stroke="{c}" stroke-width="1.2"/>')
        out.append(f'<text x="{x + 18:.0f}" y="{y:.0f}" font-family="{FONT}" '
                   f'font-size="{LEG_SIZE}" fill="{_MUTED}">{_esc(g)}</text>')
        x += wd
    return out


# ── Flow layout (column-ranked left -> right) ─────────────────────────────────
def _ranks(nodes, edges) -> dict[str, int]:
    """Assign each node a column via longest-path layering. Back edges (a loop / feedback
    arrow, e.g. 'barge-in') are detected by DFS and EXCLUDED from ranking - otherwise a
    cycle drags its start node to the far end and the whole pipeline reads backwards."""
    ids = [n.id for n in nodes]
    succ: dict[str, list[str]] = {i: [] for i in ids}
    for e in edges:
        succ[e.source].append(e.target)
    state = {i: 0 for i in ids}                   # 0 unvisited · 1 on-stack · 2 done
    back: set[tuple[str, str]] = set()
    for root in ids:
        if state[root]:
            continue
        stack = [(root, iter(succ[root]))]
        state[root] = 1
        while stack:
            u, it = stack[-1]
            advanced = False
            for v in it:
                if state[v] == 1:                 # target is an ancestor -> back edge
                    back.add((u, v))
                elif state[v] == 0:
                    state[v] = 1
                    stack.append((v, iter(succ[v])))
                    advanced = True
                    break
            if not advanced:
                state[u] = 2
                stack.pop()

    fwd = [e for e in edges if (e.source, e.target) not in back]
    rank = {i: 0 for i in ids}
    for _ in range(len(ids)):                     # longest path over the acyclic edges
        changed = False
        for e in fwd:
            if rank[e.source] + 1 > rank[e.target]:
                rank[e.target] = rank[e.source] + 1
                changed = True
        if not changed:
            break
    used = sorted(set(rank.values()))             # compress to contiguous columns
    remap = {r: i for i, r in enumerate(used)}
    return {k: remap[v] for k, v in rank.items()}


def _render_flow(spec, nodes, edges) -> str:
    wrapped, box_w, box_h, _hd = _box_size(nodes)
    colors = _group_colors(nodes)
    rank = _ranks(nodes, edges)
    cols: dict[int, list] = {}
    for n in nodes:
        cols.setdefault(rank[n.id], []).append(n)
    ncols = max(cols) + 1
    col_h = {r: len(v) * box_h + (len(v) - 1) * ROW_GAP for r, v in cols.items()}
    content_h = max(col_h.values())
    top = SUB_TOP + 22 if (spec.subtitle or "").strip() else TITLE_TOP + 24

    pos = {}                                       # node id -> (x, y)
    for r in range(ncols):
        col = cols.get(r, [])
        x = MARGIN + r * (box_w + COL_GAP)
        y0 = top + (content_h - col_h.get(r, 0)) / 2
        for i, n in enumerate(col):
            pos[n.id] = (x, y0 + i * (box_h + ROW_GAP))

    # Non-adjacent edges route through stacked channels under the content (no box crossings).
    routed = [e for e in edges if abs(rank[e.target] - rank[e.source]) != 1
              or rank[e.target] < rank[e.source]]
    ch_base = top + content_h + 18
    canvas_w = MARGIN + ncols * box_w + (ncols - 1) * COL_GAP + MARGIN
    legend_y = ch_base + len(routed) * CH_GAP + (10 if routed else 0) + 18
    canvas_h = int(legend_y + (12 if colors else -6) + MARGIN - 18)

    body, labels = [], []
    placed: list = []
    ch_i = 0
    for e in edges:
        sx0, sy0 = pos[e.source]
        tx0, ty0 = pos[e.target]
        s_cx, s_cy = sx0 + box_w / 2, sy0 + box_h / 2
        t_cx, t_cy = tx0 + box_w / 2, ty0 + box_h / 2
        if rank[e.target] == rank[e.source] + 1:   # adjacent forward: clean elbow
            sx, sy, tx, ty = sx0 + box_w, s_cy, tx0, t_cy
            xm = (sx + tx) / 2
            d = (f"M {sx:.0f} {sy:.0f} H {xm:.0f} V {ty:.0f} H {tx:.0f}"
                 if abs(sy - ty) > 1 else f"M {sx:.0f} {sy:.0f} H {tx:.0f}")
            body.append(_path(d))
            body.append(_arrow(tx, ty, "right"))
            lx = xm if abs(sy - ty) > 1 else (sx + tx) / 2
            labels.append(_edge_label(lx, (sy + ty) / 2, e.label, placed))
        else:                                       # span / back / same: drop into a channel
            cy = ch_base + ch_i * CH_GAP
            ch_i += 1
            sx, sy = s_cx, sy0 + box_h
            tx, ty = t_cx, ty0 + box_h
            d = f"M {sx:.0f} {sy:.0f} V {cy:.0f} H {tx:.0f} V {ty:.0f}"
            body.append(_path(d))
            body.append(_arrow(tx, ty, "up"))
            labels.append(_edge_label((sx + tx) / 2, cy, e.label, placed))

    for n in nodes:
        x, y = pos[n.id]
        color = colors.get((n.group or "").strip(), _NEUTRAL)
        body.append(_node_svg(n, x, y, box_w, box_h, wrapped[n.id], color, n.id == spec.focus))

    out = _header(canvas_w, canvas_h, spec)
    out += body + [lbl for lbl in labels if lbl]
    out += _legend(nodes, colors, canvas_w, legend_y)
    out.append("</svg>")
    return "".join(out)


# ── Layered layout (named horizontal lanes) ───────────────────────────────────
def _render_layered(spec, nodes, edges) -> str:
    wrapped, box_w, box_h, _hd = _box_size(nodes)
    colors = _group_colors(nodes)
    lanes: dict[str, list] = {}
    for n in nodes:
        lanes.setdefault((n.lane or "main").strip(), []).append(n)
    lane_names = list(lanes)
    widest = max(len(v) for v in lanes.values())
    lane_w_label = 70
    content_w = widest * box_w + (widest - 1) * ROW_GAP
    canvas_w = MARGIN + lane_w_label + content_w + MARGIN
    lane_h = box_h + 30
    top = SUB_TOP + 18 if (spec.subtitle or "").strip() else TITLE_TOP + 22
    legend_y = top + len(lane_names) * lane_h + 20
    canvas_h = int(legend_y + (12 if colors else -4) + MARGIN - 16)

    out = _header(canvas_w, canvas_h, spec)
    pos = {}
    for li, name in enumerate(lane_names):
        ly = top + li * lane_h
        if li % 2 == 0:
            out.append(f'<rect x="{MARGIN}" y="{ly:.0f}" width="{canvas_w - 2 * MARGIN}" '
                       f'height="{box_h + 16}" rx="8" fill="#ffffff" fill-opacity="0.6"/>')
        out.append(f'<text x="{MARGIN + 4}" y="{ly + box_h / 2 + 12:.0f}" font-family="{FONT}" '
                   f'font-size="{LANE_SIZE}" letter-spacing="1" fill="#8a93a0">'
                   f'{_esc(name.upper()[:10])}</text>')
        row = lanes[name]
        x0 = MARGIN + lane_w_label
        for i, n in enumerate(row):
            x = x0 + i * (box_w + ROW_GAP)
            pos[n.id] = (x, ly + 8)

    placed: list = []
    for e in edges:
        sx0, sy0 = pos[e.source]
        tx0, ty0 = pos[e.target]
        s_cx, t_cx = sx0 + box_w / 2, tx0 + box_w / 2
        if abs(sy0 - ty0) < 1:                      # same lane: short elbow above
            xm = (s_cx + t_cx) / 2
            ytop = sy0 - 12
            out.append(_path(f"M {s_cx:.0f} {sy0:.0f} V {ytop:.0f} H {t_cx:.0f} V {ty0:.0f}"))
            out.append(_arrow(t_cx, ty0, "down"))
            out.append(_edge_label(xm, ytop, e.label, placed))
        elif ty0 > sy0:                             # downward between lanes
            sy, ty = sy0 + box_h, ty0
            out.append(_path(f"M {s_cx:.0f} {sy:.0f} V {(sy + ty) / 2:.0f} "
                             f"H {t_cx:.0f} V {ty:.0f}"))
            out.append(_arrow(t_cx, ty, "down"))
            out.append(_edge_label((s_cx + t_cx) / 2, (sy + ty) / 2, e.label, placed))
        else:                                       # upward between lanes
            sy, ty = sy0, ty0 + box_h
            out.append(_path(f"M {s_cx:.0f} {sy:.0f} V {(sy + ty) / 2:.0f} "
                             f"H {t_cx:.0f} V {ty:.0f}"))
            out.append(_arrow(t_cx, ty, "up"))
            out.append(_edge_label((s_cx + t_cx) / 2, (sy + ty) / 2, e.label, placed))

    for n in nodes:
        x, y = pos[n.id]
        color = colors.get((n.group or "").strip(), _NEUTRAL)
        out.append(_node_svg(n, x, y, box_w, box_h, wrapped[n.id], color, n.id == spec.focus))
    out += _legend(nodes, colors, canvas_w, legend_y)
    out.append("</svg>")
    return "".join(out)


# ── Cycle layout (nodes on a ring) ────────────────────────────────────────────
def _render_cycle(spec, nodes, edges) -> str:
    """Nodes evenly on a circle, edges as straight chords with angle-aware arrowheads -
    the natural shape for a feedback loop or lifecycle (vs. forcing it into a line)."""
    wrapped, box_w, box_h, _hd = _box_size(nodes)
    colors = _group_colors(nodes)
    n = len(nodes)
    top = SUB_TOP + 24 if (spec.subtitle or "").strip() else TITLE_TOP + 28
    # Radius so adjacent boxes (chord = 2R·sin(π/n)) clear each other.
    R = max(box_h * 1.7, (box_w + 34) / (2 * math.sin(math.pi / n)))
    cx = MARGIN + R + box_w / 2
    cyc = top + R + box_h / 2
    canvas_w = int(2 * R + box_w + 2 * MARGIN)
    legend_y = int(top + 2 * R + box_h + 26)
    canvas_h = int(legend_y + (12 if colors else -8) + MARGIN - 14)

    pos = {}
    for i, nd in enumerate(nodes):
        theta = 2 * math.pi * i / n - math.pi / 2          # first node at the top, clockwise
        pos[nd.id] = (cx + R * math.cos(theta) - box_w / 2,
                      cyc + R * math.sin(theta) - box_h / 2)

    body, placed = [], []
    for e in edges:
        sx0, sy0 = pos[e.source]
        tx0, ty0 = pos[e.target]
        s_c = (sx0 + box_w / 2, sy0 + box_h / 2)
        t_c = (tx0 + box_w / 2, ty0 + box_h / 2)
        sp = _box_edge(*s_c, box_w / 2, box_h / 2, *t_c)
        tp = _box_edge(*t_c, box_w / 2, box_h / 2, *s_c)
        body.append(_path(f"M {sp[0]:.0f} {sp[1]:.0f} L {tp[0]:.0f} {tp[1]:.0f}"))
        body.append(_arrow_at(tp[0], tp[1], math.atan2(tp[1] - sp[1], tp[0] - sp[0])))
        body.append(_edge_label((sp[0] + tp[0]) / 2, (sp[1] + tp[1]) / 2, e.label, placed))

    for nd in nodes:
        x, y = pos[nd.id]
        color = colors.get((nd.group or "").strip(), _NEUTRAL)
        body.append(_node_svg(nd, x, y, box_w, box_h, wrapped[nd.id], color, nd.id == spec.focus))

    out = _header(canvas_w, canvas_h, spec)
    out += body                                            # edges, arrowheads + labels, then nodes
    out += _legend(nodes, colors, canvas_w, legend_y)
    out.append("</svg>")
    return "".join(out)


# ── Comparison layout (two labelled columns) ──────────────────────────────────
def _render_comparison(spec, nodes, edges) -> str:
    """Two side-by-side columns headed by the first two groups - 'A vs B'. The column
    headers carry the colour, so no separate legend is needed."""
    wrapped, box_w, box_h, _hd = _box_size(nodes)
    colors = _group_colors(nodes)
    g_left, g_right = list(colors)[:2]
    left = [n for n in nodes if (n.group or "").strip() == g_left]
    right = [n for n in nodes if (n.group or "").strip() == g_right]
    for nd in nodes:                                       # nodes outside the two groups
        if nd not in left and nd not in right:
            (left if len(left) <= len(right) else right).append(nd)

    gap = 120
    top = SUB_TOP + 26 if (spec.subtitle or "").strip() else TITLE_TOP + 30
    head_y = top + 4
    body_top = top + 30
    rows = max(len(left), len(right))
    canvas_w = int(2 * box_w + gap + 2 * MARGIN)
    content_h = rows * box_h + (rows - 1) * ROW_GAP
    canvas_h = int(body_top + content_h + MARGIN)
    x_left = MARGIN
    x_right = MARGIN + box_w + gap

    pos = {}
    for col, x in ((left, x_left), (right, x_right)):
        for i, nd in enumerate(col):
            pos[nd.id] = (x, body_top + i * (box_h + ROW_GAP))

    out = _header(canvas_w, canvas_h, spec)
    for x, g in ((x_left, g_left), (x_right, g_right)):     # column headers in group colour
        c = colors[g]
        out.append(f'<text x="{x + box_w / 2:.0f}" y="{head_y:.0f}" text-anchor="middle" '
                   f'font-family="{FONT}" font-size="14" font-weight="700" fill="{c}">'
                   f'{_esc(g)}</text>')
        out.append(f'<line x1="{x}" y1="{head_y + 6:.0f}" x2="{x + box_w}" y2="{head_y + 6:.0f}" '
                   f'stroke="{c}" stroke-width="2"/>')

    placed: list = []
    seen_lbl: set = set()                                  # repeated relations shown once
    for e in edges:                                        # any cross-column relations
        if e.source not in pos or e.target not in pos:
            continue
        sx, sy = pos[e.source]
        tx, ty = pos[e.target]
        s_c = (sx + box_w / 2, sy + box_h / 2)
        t_c = (tx + box_w / 2, ty + box_h / 2)
        sp = _box_edge(*s_c, box_w / 2, box_h / 2, *t_c)
        tp = _box_edge(*t_c, box_w / 2, box_h / 2, *s_c)
        out.append(_path(f"M {sp[0]:.0f} {sp[1]:.0f} L {tp[0]:.0f} {tp[1]:.0f}"))
        out.append(_arrow_at(tp[0], tp[1], math.atan2(tp[1] - sp[1], tp[0] - sp[0])))
        out.append(_edge_label((sp[0] + tp[0]) / 2, (sp[1] + tp[1]) / 2, e.label, placed, seen_lbl))

    for nd in nodes:
        if nd.id not in pos:
            continue
        x, y = pos[nd.id]
        color = colors.get((nd.group or "").strip(), _NEUTRAL)
        out.append(_node_svg(nd, x, y, box_w, box_h, wrapped[nd.id], color, nd.id == spec.focus))
    out.append("</svg>")
    return "".join(out)


# ── Optional D2 backend (terrastruct.github.io/d2) - alternative auto-layout ───
# The built-in engine above is zero-dependency, measures text, lays out compactly, and
# carries the title/legend/metrics - so it is the DEFAULT (`diagram_engine: auto`).
# The `d2` CLI (a Go binary, ELK layout) routes complex graphs (fan-out/fan-in, lane
# containers) better but renders much wider/harder to read, so it is EXPLICIT opt-in
# (`diagram_engine: d2`), not auto-selected just because the binary is present. The
# model output (DiagramSpec) is identical either way.
_D2_PAL = [("#e9f1fe", "#4f8ef7"), ("#e7faf1", "#34c98a"), ("#fff0e6", "#ff6719"),
           ("#f1ecfe", "#a78bfa"), ("#fdecea", "#e5534b"), ("#e6f6fd", "#0ea5e9")]


def find_d2() -> str | None:
    """The d2 binary path: $WRITINGAGENT_D2 (explicit) or `d2` on PATH; None if absent."""
    return os.environ.get("WRITINGAGENT_D2") or shutil.which("d2")


_VIEWBOX_RE = re.compile(r'viewBox="(-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+)"')


def _inject_d2_legend(svg: str, spec: S.DiagramSpec) -> str:
    """Append a colour legend strip under a d2-rendered SVG (d2 has no legend of its own).

    Extends the OUTER viewBox height and draws swatches+labels in d2's coordinate space,
    using the SAME first-seen group order/colours as `to_d2`, so the legend matches the node
    borders. Best-effort - on any parse surprise the SVG is returned unchanged."""
    colors = _group_colors(spec.nodes)              # group -> stroke colour (first-seen order)
    if not colors:
        return svg
    m = _VIEWBOX_RE.search(svg)                     # first viewBox = the outer <svg>
    if not m:
        return svg
    vx, vy, vw, vh = (float(g) for g in m.groups())
    size = max(13.0, vh * 0.05)                     # scale the legend to d2's large canvas
    strip = size * 3.0
    new_vb = f'viewBox="{vx:g} {vy:g} {vw:g} {vh + strip:g}"'
    svg = svg[:m.start()] + new_vb + svg[m.end():]
    y = vy + vh + strip * 0.6
    items = list(colors.items())
    widths = [size * 1.5 + _text_w(g, size) + size * 1.4 for g, _ in items]
    x = vx + (vw - sum(widths)) / 2
    parts = [f'<rect x="{vx:g}" y="{vy + vh:g}" width="{vw:g}" height="{strip:g}" fill="#ffffff"/>']
    for (g, c), wd in zip(items, widths, strict=True):
        parts.append(f'<rect x="{x:.0f}" y="{y - size:.0f}" width="{size:.0f}" height="{size:.0f}" '
                     f'rx="2" fill="{c}" fill-opacity="0.55" stroke="{c}" stroke-width="1.2"/>')
        parts.append(f'<text x="{x + size * 1.5:.0f}" y="{y:.0f}" font-family="{FONT}" '
                     f'font-size="{size:.0f}" fill="{_MUTED}">{_esc(g)}</text>')
        x += wd
    k = svg.rfind("</svg>")
    return svg[:k] + "".join(parts) + svg[k:]


def _d2_lbl(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _d2_id(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s) or "x"


def to_d2(spec: S.DiagramSpec) -> str:
    """Convert a DiagramSpec to D2 source (the model authors content; D2 lays it out).

    Groups -> consistent fill/stroke; `layered` -> lane containers; focus -> thick stroke.
    """
    groups: dict[str, int] = {}

    def color(g: str) -> tuple[str, str]:
        g = (g or "").strip()
        if not g:
            return ("#eef1f5", "#64748b")
        groups.setdefault(g, len(groups))
        return _D2_PAL[groups[g] % len(_D2_PAL)]

    layered = spec.archetype == "layered" and any(n.lane for n in spec.nodes)
    lines = [f"direction: {'down' if layered else 'right'}"]

    def decl(n, indent="") -> str:
        lbl = _d2_lbl(n.label) + ("\\n" + _d2_lbl(n.detail) if (n.detail or "").strip() else "")
        fill, stroke = color(n.group)
        sw = "; stroke-width: 3" if n.id == spec.focus else ""
        return f'{indent}{_d2_id(n.id)}: "{lbl}" {{ style: {{ fill: "{fill}"; stroke: "{stroke}"{sw} }} }}'

    node_lane: dict[str, str] = {}
    if layered:
        lanes: dict[str, list] = {}
        for n in spec.nodes:
            lanes.setdefault((n.lane or "main").strip(), []).append(n)
            node_lane[n.id] = (n.lane or "main").strip()
        for lane, ns in lanes.items():
            lines.append(f'{_d2_id(lane)}: "{_d2_lbl(lane)}" {{')
            lines += [decl(n, "  ") for n in ns]
            lines.append("}")

        def ref(i):
            return f"{_d2_id(node_lane[i])}.{_d2_id(i)}"
    else:
        lines += [decl(n) for n in spec.nodes]

        def ref(i):
            return _d2_id(i)

    ids = {n.id for n in spec.nodes}
    for e in spec.edges:
        if e.source in ids and e.target in ids and e.source != e.target:
            lbl = f': "{_d2_lbl(e.label)}"' if (e.label or "").strip() else ""
            lines.append(f"{ref(e.source)} -> {ref(e.target)}{lbl}")
    return "\n".join(lines)


def render_d2(spec: S.DiagramSpec, *, layout: str = "elk", timeout: float = 25.0) -> str | None:
    """Render a DiagramSpec via the d2 CLI (ELK layout by default). Returns an SVG string,
    or None if d2 is unavailable, times out, or errors - the caller falls back to the
    built-in engine. Never raises."""
    exe = find_d2()
    if not exe or not spec.nodes:
        return None
    src_path = out_path = None
    try:
        fd, src_path = tempfile.mkstemp(suffix=".d2")
        os.close(fd)
        fd, out_path = tempfile.mkstemp(suffix=".svg")
        os.close(fd)
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(to_d2(spec))
        proc = subprocess.run([exe, "--layout", layout, src_path, out_path],  # noqa: S603
                              capture_output=True, timeout=timeout, check=False)
        if proc.returncode != 0:
            return None
        with open(out_path, encoding="utf-8") as f:
            svg = f.read()
        i = svg.find("<svg")
        if i < 0:
            return None
        return _inject_d2_legend(svg[i:], spec)  # drop <?xml?> prolog; add the colour legend
    except Exception:  # noqa: BLE001 - any failure -> built-in fallback
        return None
    finally:
        for p in (src_path, out_path):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass
