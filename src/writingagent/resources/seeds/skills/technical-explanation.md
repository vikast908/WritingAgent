---
name: technical-explanation
genre_tags: [technical, nonfiction, reference, textbook, programming, science, article, tutorial]
status: trusted
---

## When to apply
Any section that explains a complex concept, system, algorithm, or process to a
reader who does not yet understand it. The default mode for technical writing.

## Technique

### Concrete before abstract
- Open with a specific example, a real number, or a single case the reader can
  picture. Derive the general rule from it. Do not state the abstraction first and
  then "for example" it - readers anchor on the concrete instance.
- Replace "a data structure that maps keys to values" with "a phone book: you look
  up 'Maya' and get back her number." Then name it.

### Progressive disclosure
- Teach one new idea per paragraph. Name a concept only after the reader has seen
  what it does. Introduce jargon in **bold** at first use, define it in the same
  sentence, then reuse the exact term (no synonym cycling).
- Build the explanation in dependency order: never use a term the reader has not met
  yet. If B requires A, A comes first.

### Worked examples over description
- Show the thing happening with real inputs and real outputs, not a description of
  how it would happen. "Pass [3, 1, 2] and it returns [1, 2, 3]" beats "it sorts
  the list."
- Trace one example all the way through before generalizing. Readers learn the
  pattern from the trace, not from the rule.

### Analogies that do not leak
- Use an analogy to convey one specific property, then say what the analogy is.
  State where it breaks down before the reader notices and stops trusting you.
- Drop the analogy once the real mechanism is on the table. Do not stack three
  analogies for the same idea.

### Why before how
- State the problem the concept solves before explaining the mechanism. A reader who
  knows why a cache exists understands eviction policy; one who does not just
  memorizes it.

## Anti-pattern it replaces
Definition-first explanation that front-loads abstract terms, jargon used before it
is defined, "imagine that..." analogies that never connect to the real mechanism, and
descriptions of behavior where a concrete worked example would teach it in one read.
