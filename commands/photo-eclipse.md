---
description: Photo Eclipse (cinematic 3D) — A dark-backed card turns in front of a glowing light with a bright rim, reveals its photo, and smaller photos drift out into a weightless orbit.
argument-hint: [photos folder or files]
---

Render the **Photo Eclipse** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `photo-eclipse`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py photo-eclipse --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
