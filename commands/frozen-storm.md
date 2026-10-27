---
description: Frozen Photo Storm (cinematic 3D) — Dozens of photos hang at different depths in a dark room; the camera drifts past blurred cards to one lit image, then they all rush past the lens.
argument-hint: [photos folder or files]
---

Render the **Frozen Photo Storm** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `frozen-storm`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py frozen-storm --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
