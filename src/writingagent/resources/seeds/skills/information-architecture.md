---
name: information-architecture
genre_tags: [technical, nonfiction, reference, article, documentation, textbook, tutorial]
status: trusted
---

## When to apply
Structuring any long-form non-fiction or technical piece: deciding section order,
heading hierarchy, and how a reader navigates and scans the content.

## Technique

### One idea per section, named by its payload
- Each section delivers exactly one main idea. If a section needs two H3s that could
  each be a section, split it. If two sections say the same thing, merge them.
- Headings name what the reader gets, not vague labels: "How retries cause duplicate
  writes" beats "Considerations". A reader scanning only headings should grasp the arc.

### Order by the reader's dependency graph
- Sequence so nothing references a concept the reader has not met. Prerequisites
  first, payoffs after. Map setups to payoffs before drafting; a payoff with no setup
  confuses, a setup with no payoff wastes the reader's attention.
- Lead with the reader's question, not the author's history. Most technical readers
  want "how do I" and "why does this break" before "the full theory."

### Signpost transitions
- End a section by pointing at the next when the link is not obvious: "That covers
  writes; reads have the opposite problem." The white space between sections is where
  the reader infers structure - do not waste it.
- Use a short intro after the title that states what the piece covers and who it is
  for, so a reader can self-select in ten seconds.

### Make it scannable
- Use lists for genuinely parallel items, prose for argument and nuance. Do not bullet
  a narrative; do not bury a 6-item checklist in a paragraph.
- Keep heading depth shallow (rarely past H3). Deep nesting means the structure is
  wrong, not that the reader needs more levels.

### Front-load the answer
- State the conclusion or recommendation early, then support it. Technical readers
  skim; burying the takeaway under five paragraphs of build-up loses them.

## Anti-pattern it replaces
Wall-of-text sections that cover several ideas at once, vague headings ("Overview",
"Details", "Considerations") that say nothing when scanned, concepts referenced before
they are introduced, deep heading nesting, and conclusions buried at the bottom.
