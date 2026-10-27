---
description: Light Sweeping Across Memories (cinematic 3D) — In near darkness only card edges show; a narrow beam sweeps across, revealing each photo, and the last one turns fully into the light.
argument-hint: [photos folder or files]
---

Render the **Light Sweeping Across Memories** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `light-sweep`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py light-sweep --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
