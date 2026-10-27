---
description: One Photo, Many Memories (cinematic 3D) — A single photo floats close to the lens; as the camera pulls back hundreds more appear behind it, softening into the distance.
argument-hint: [photos folder or files]
---

Render the **One Photo, Many Memories** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `one-photo-many`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py one-photo-many --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
