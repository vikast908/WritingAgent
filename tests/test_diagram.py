"""Tests for the deterministic SVG diagram renderer (diagram.py).

The whole point of the rewrite is that layout is computed, not guessed - so these tests
assert the geometric guarantees the raw-SVG approach could never make: node boxes never
overlap, text/boxes stay inside the canvas, and arrows are explicit (PDF-safe) shapes.
"""
import re

import pytest

from book_agent import diagram, nodes
from book_agent import schemas as S
from book_agent.config import load_config


def _node_rects(svg: str):
    """All node boxes (rx='9' distinguishes them from bg/lane/pill/legend rects)."""
    return [tuple(map(int, m)) for m in re.findall(
        r'<rect x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)" rx="9"', svg)]


def _canvas(svg: str):
    m = re.search(r'<svg[^>]*width="(\d+)" height="(\d+)"', svg)
    return int(m.group(1)), int(m.group(2))


def _overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def _flow_spec():
    return S.DiagramSpec(
        title="Real-time voice pipeline", subtitle="microphone to speaker",
        archetype="flow", focus="asr",
        nodes=[
            S.DiagramNode(id="mic", label="Microphone capture", group="input"),
            S.DiagramNode(id="asr", label="ASR streaming transcription",
                          detail="<= 80 ms", group="model"),
            S.DiagramNode(id="llm", label="LLM response generation", group="model"),
            S.DiagramNode(id="tts", label="TTS synthesis", group="output"),
            S.DiagramNode(id="spk", label="Speaker playback", group="output"),
        ],
        edges=[
            S.DiagramEdge(source="mic", target="asr", label="audio frames"),
            S.DiagramEdge(source="asr", target="llm", label="partial text"),
            S.DiagramEdge(source="llm", target="tts"),
            S.DiagramEdge(source="tts", target="spk"),
            S.DiagramEdge(source="spk", target="mic", label="barge-in"),   # back edge
        ],
    )


def test_flow_renders_valid_svg_with_all_nodes():
    svg = diagram.render_spec(_flow_spec())
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    for label in ("Microphone", "ASR", "LLM", "TTS", "Speaker"):
        assert label in svg
    assert len(_node_rects(svg)) == 5


def test_flow_node_boxes_never_overlap():
    rects = _node_rects(diagram.render_spec(_flow_spec()))
    assert len(rects) == 5
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not _overlap(rects[i], rects[j]), f"boxes {i},{j} overlap"


def test_flow_everything_stays_inside_canvas():
    svg = diagram.render_spec(_flow_spec())
    w, h = _canvas(svg)
    for x, y, bw, bh in _node_rects(svg):
        assert 0 <= x and x + bw <= w, "box exceeds canvas width"
        assert 0 <= y and y + bh <= h, "box exceeds canvas height"


def test_connectors_have_fill_none_and_explicit_arrowheads():
    svg = diagram.render_spec(_flow_spec())
    # every edge <path> declares fill="none" (a filled path is a black blob)
    for m in re.findall(r"<path [^>]*>", svg):
        assert 'fill="none"' in m
    # arrowheads are explicit polygons (markers are dropped by the PDF renderer)
    assert svg.count("<polygon") >= 5


def test_groups_produce_a_legend():
    svg = diagram.render_spec(_flow_spec())
    for g in ("input", "model", "output"):
        assert g in svg


def test_long_labels_wrap_instead_of_overflowing():
    lines = diagram._wrap(
        "a deliberately long node label that cannot fit on one line", diagram.MAX_INNER,
        diagram.LABEL_SIZE)
    assert len(lines) > 1
    assert all(diagram._text_w(ln, diagram.LABEL_SIZE) <= diagram.MAX_INNER for ln in lines)


def test_edges_to_unknown_nodes_are_dropped_not_crashing():
    spec = S.DiagramSpec(
        title="t", nodes=[S.DiagramNode(id="a", label="A")],
        edges=[S.DiagramEdge(source="a", target="ghost"),    # unknown target
               S.DiagramEdge(source="a", target="a")])        # self-loop
    svg = diagram.render_spec(spec)
    assert svg.startswith("<svg") and "A" in svg


def test_layered_renders_lanes_without_overlap():
    spec = S.DiagramSpec(
        title="Request path", archetype="layered",
        nodes=[
            S.DiagramNode(id="ui", label="Browser", lane="client"),
            S.DiagramNode(id="api", label="API gateway", lane="edge"),
            S.DiagramNode(id="svc", label="Auth service", lane="services"),
            S.DiagramNode(id="db", label="Postgres", lane="data"),
        ],
        edges=[S.DiagramEdge(source="ui", target="api"),
               S.DiagramEdge(source="api", target="svc"),
               S.DiagramEdge(source="svc", target="db")])
    svg = diagram.render_spec(spec)
    assert svg.startswith("<svg") and "CLIENT" in svg.upper()
    rects = _node_rects(svg)
    assert len(rects) == 4
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not _overlap(rects[i], rects[j])


def test_empty_spec_returns_placeholder():
    svg = diagram.render_spec(S.DiagramSpec(title="Nothing here", nodes=[], edges=[]))
    assert svg.startswith("<svg") and "Nothing here" in svg


def test_back_edge_does_not_reverse_the_pipeline():
    """A feedback/loop edge (spk -> mic) must not drag the start node to the far end:
    the forward order has to survive (this was the voice-pipeline rendering bug)."""
    nodes = [S.DiagramNode(id=i, label=i.upper()) for i in ("mic", "asr", "llm", "tts", "spk")]
    edges = [S.DiagramEdge(source=a, target=b) for a, b in
             (("mic", "asr"), ("asr", "llm"), ("llm", "tts"), ("tts", "spk"), ("spk", "mic"))]
    rank = diagram._ranks(nodes, edges)
    assert rank["mic"] < rank["asr"] < rank["llm"] < rank["tts"] < rank["spk"]


def test_cycle_renders_a_ring_overlap_free():
    """The cycle archetype lays nodes on a ring (varied x AND y), not a flow column."""
    spec = S.DiagramSpec(
        title="Feedback loop", archetype="cycle",
        nodes=[S.DiagramNode(id=f"n{i}", label=f"Stage {i}") for i in range(5)],
        edges=[S.DiagramEdge(source=f"n{i}", target=f"n{(i + 1) % 5}") for i in range(5)])
    rects = _node_rects(diagram.render_spec(spec))
    assert len(rects) == 5
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not _overlap(rects[i], rects[j])
    xs = {r[0] for r in rects}
    ys = {r[1] for r in rects}
    assert len(xs) > 1 and len(ys) > 1            # a ring spreads both axes (flow would not)


def test_comparison_renders_two_labelled_columns():
    spec = S.DiagramSpec(
        title="A vs B", archetype="comparison", edges=[],
        nodes=[S.DiagramNode(id="a1", label="A one", group="Option A"),
               S.DiagramNode(id="a2", label="A two", group="Option A"),
               S.DiagramNode(id="b1", label="B one", group="Option B"),
               S.DiagramNode(id="b2", label="B two", group="Option B")])
    svg = diagram.render_spec(spec)
    assert "Option A" in svg and "Option B" in svg     # column headers present
    rects = _node_rects(svg)
    assert len(rects) == 4
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not _overlap(rects[i], rects[j])
    # two distinct column x-positions
    assert len({r[0] for r in rects}) == 2


def test_cycle_and_comparison_degrade_to_flow_when_underspecified():
    # cycle with < 3 nodes -> flow (still valid, no crash)
    tiny = S.DiagramSpec(title="t", archetype="cycle",
                         nodes=[S.DiagramNode(id="a", label="A"), S.DiagramNode(id="b", label="B")],
                         edges=[S.DiagramEdge(source="a", target="b")])
    assert diagram.render_spec(tiny).startswith("<svg")
    # comparison with < 2 groups -> flow
    one = S.DiagramSpec(title="t", archetype="comparison",
                        nodes=[S.DiagramNode(id="a", label="A"), S.DiagramNode(id="b", label="B")],
                        edges=[])
    assert diagram.render_spec(one).startswith("<svg")


def test_generate_svg_diagram_fake_mode_is_placeholder(monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")
    out = nodes.generate_svg_diagram(load_config(), "some heading", context="ctx")
    assert out.startswith("<svg") and "some heading" in out


# ── Optional D2 backend ───────────────────────────────────────────────────────
def test_to_d2_flow_source():
    src = diagram.to_d2(_flow_spec())
    assert "direction: right" in src
    assert "mic:" in src and "asr:" in src
    assert "mic -> asr" in src
    assert "stroke:" in src                       # group colours carried


def test_to_d2_layered_uses_lane_containers_and_qualified_edges():
    spec = S.DiagramSpec(
        title="t", archetype="layered",
        nodes=[S.DiagramNode(id="ui", label="UI", lane="client"),
               S.DiagramNode(id="api", label="API", lane="edge")],
        edges=[S.DiagramEdge(source="ui", target="api")])
    src = diagram.to_d2(spec)
    assert "direction: down" in src
    assert "client: " in src and "{" in src       # lane container
    assert "client.ui -> edge.api" in src         # edges reference container-qualified ids


def test_render_d2_returns_none_without_binary(monkeypatch):
    monkeypatch.setattr(diagram, "find_d2", lambda: None)
    assert diagram.render_d2(_flow_spec()) is None


def test_generate_svg_diagram_falls_back_to_builtin_without_d2(monkeypatch):
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)
    monkeypatch.setattr(diagram, "find_d2", lambda: None)

    def fake_spec(model, system, user, schema, **_kw):
        return S.DiagramSpec(title="t", archetype="flow",
                             nodes=[S.DiagramNode(id="a", label="Capture"),
                                    S.DiagramNode(id="b", label="Process")],
                             edges=[S.DiagramEdge(source="a", target="b")])
    monkeypatch.setattr(nodes, "complete_structured", fake_spec)
    out = nodes.generate_svg_diagram(load_config(), "h", engine="auto")
    assert out.startswith("<svg") and "Capture" in out
    assert "data-d2-version" not in out           # the built-in engine, not d2


def test_inject_d2_legend_extends_viewbox_and_adds_swatches():
    svg = '<svg xmlns="x" viewBox="0 0 400 200"><rect/></svg>'
    out = diagram._inject_d2_legend(svg, _flow_spec())   # groups: input/model/output
    assert 'fill-opacity="0.55"' in out and "input" in out
    h = float(re.search(r'viewBox="0 0 400 ([\d.]+)"', out).group(1))
    assert h > 200                                # canvas grew to fit the legend strip


def test_inject_d2_legend_noop_without_groups():
    svg = '<svg viewBox="0 0 400 200"><rect/></svg>'
    spec = S.DiagramSpec(title="t", nodes=[S.DiagramNode(id="a", label="A")], edges=[])
    assert diagram._inject_d2_legend(svg, spec) == svg


def test_generate_svg_diagram_emits_spec_to_on_spec(tmp_brain, monkeypatch):
    """The freshly-built spec is handed to `on_spec` so the orchestrator can persist it."""
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)
    monkeypatch.setattr(diagram, "find_d2", lambda: None)   # force the built-in path
    spec = S.DiagramSpec(title="t", archetype="flow",
                         nodes=[S.DiagramNode(id="a", label="Alpha")],
                         edges=[])
    monkeypatch.setattr(nodes, "complete_structured", lambda *a, **k: spec)
    captured = {}
    nodes.generate_svg_diagram(load_config(), "h", on_spec=lambda sp: captured.setdefault("spec", sp))
    assert captured["spec"].nodes[0].label == "Alpha"


@pytest.mark.skipif(diagram.find_d2() is None, reason="d2 binary not installed")
def test_render_d2_with_real_binary():
    svg = diagram.render_d2(_flow_spec())
    assert svg and svg.startswith("<svg") and "data-d2-version" in svg
    assert "Microphone capture" in svg
    assert 'fill-opacity="0.55"' in svg           # injected legend present
