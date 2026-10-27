---
description: The Memory Corridor (cinematic 3D) — Photos line both sides of an endless corridor; the camera speeds up as each catches the light, then one turns to the lens and fills the screen.
argument-hint: [photos folder or files]
---

Render the **The Memory Corridor** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `memory-corridor`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py memory-corridor --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
