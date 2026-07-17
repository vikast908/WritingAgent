---
name: runnable-code-examples
genre_tags: [technical, programming, reference, tutorial, article, nonfiction, textbook]
status: trusted
---

## When to apply
Any section that includes code: a snippet, a function, a config block, a shell
command, or a full example a reader might copy and run.

## Technique

### Minimal and complete
- Show the smallest code that actually demonstrates the point, but make it runnable
  as shown: real imports, real names, no `...` or `# your code here` where working
  code is expected. A reader should be able to copy it and have it run.
- Cut everything not load-bearing for the idea. Error handling, logging, and edge
  cases go in later, named as omitted ("error handling elided for brevity").

### Fence and tag every block
- Every code block is a fenced block with a language tag (```python, ```bash,
  ```json). Untagged fences lose syntax highlighting and signal carelessness.
- Shell commands and their output go in separate blocks, or prefix output lines so
  the reader can tell input from result.

### Show expected output
- After a runnable example, show what it prints or returns. The output is half the
  lesson - it tells the reader whether their copy worked.
- For transformations, show input and output side by side.

### Correctness is non-negotiable
- Code must be syntactically valid and actually do what the prose claims. Wrong code
  in a technical piece destroys trust faster than any prose error.
- Variable and function names carry meaning: `user_count` not `x`, `parse_header`
  not `do_thing`. The names are part of the explanation.

### Introduce, then show, then read
- One line of prose saying what the block does and why, then the block, then (if
  non-obvious) a line reading the key part back. Never drop a block with no setup.

## Anti-pattern it replaces
Pseudocode or fragments presented as if runnable, untagged code fences, examples with
no output so the reader cannot verify them, single-letter variable names, and code
that does not match what the surrounding prose says it does.
