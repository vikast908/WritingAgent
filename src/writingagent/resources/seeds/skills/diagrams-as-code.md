---
name: diagrams-as-code
genre_tags: [technical, nonfiction, reference, textbook, programming, science]
status: trusted
---

## When to apply
Technical or non-fiction chapters that need a diagram: a flow, architecture, process, or relationship.

## Technique
- Prefer text-renderable diagrams over external image files. Use a fenced ```mermaid block
  (flowchart, sequenceDiagram, classDiagram, erDiagram) or a clean ASCII diagram.
- Give every figure a number and caption: "Figure 3.2 - what it shows".
- Reference figures by number in the prose ("see Figure 3.2"), never "below"/"above".

## Anti-pattern it replaces
Vague prose descriptions of structure, or dependence on external image files that may be missing.
