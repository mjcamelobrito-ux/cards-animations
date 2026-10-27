---
description: Through the Photograph (cinematic 3D) — The camera pushes into a photo, which splits into background, subject and foreground layers; it travels between them to a second photo waiting behind.
argument-hint: [photos folder or files]
---

Render the **Through the Photograph** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `through-the-photo`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py through-the-photo --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
