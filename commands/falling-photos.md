---
description: Falling Photographs (cinematic 3D) — Photos fall slowly through a spotlight, tumbling like paper; the camera follows one as it turns face-up and lands on a growing pile.
argument-hint: [photos folder or files]
---

Render the **Falling Photographs** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `falling-photos`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py falling-photos --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
