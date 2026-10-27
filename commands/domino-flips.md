---
description: Domino Flips — Cards flip from thin edges to full photos in a staggered wave, then fold away in reverse.
argument-hint: [photos folder or files] [--label "text"] [--bg #hex] [--mov]
---

Render the **Domino Flips** card animation.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow it with the animation fixed to `domino-flips`.
2. Collect the photos the user gave (files or a folder) into a fresh folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx.py domino-flips --photos <folder> --out <project>/out [--label ...] [--bg ...] [--mov]`
3. With no photos, render with the built-in placeholders and say so.
4. Look at a few frames (`--check 0.5,1.5,3.0`) before delivering; deliver the mp4 preview and the transparent webm (and .mov if asked).
