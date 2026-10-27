---
description: Magnetic Photo Cluster — One photo lands in the centre; the others glide in from all sides and lock around it.
argument-hint: [photos folder or files] [--label "text"] [--bg #hex] [--mov]
---

Render the **Magnetic Photo Cluster** card animation.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow it with the animation fixed to `magnetic-cluster`.
2. Collect the photos the user gave (files or a folder) into a fresh folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx.py magnetic-cluster --photos <folder> --out <project>/out [--label ...] [--bg ...] [--mov]`
3. With no photos, render with the built-in placeholders and say so.
4. Look at a few frames (`--check 0.5,1.5,3.0`) before delivering; deliver the mp4 preview and the transparent webm (and .mov if asked).
