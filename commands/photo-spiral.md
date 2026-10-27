---
description: The Endless Photo Spiral (cinematic 3D) — Photos form a tall spiral; the camera rises through its centre, then the spiral opens into a ring of photos around the viewer.
argument-hint: [photos folder or files]
---

Render the **The Endless Photo Spiral** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `photo-spiral`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py photo-spiral --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
