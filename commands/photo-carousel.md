---
description: Photo Carousel (cinematic 3D) — Vertical photos ride a tilted 3D ellipse that turns like a carousel; the front card is lit and sharp, the far side falls into shadow and soft focus, with a faint floor reflection.
argument-hint: [photos folder or files]
---

Render the **Photo Carousel** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `photo-carousel`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py photo-carousel --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
