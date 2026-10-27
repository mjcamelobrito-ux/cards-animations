---
description: Bullet-Time Gallery (cinematic 3D) — A burst of photos freezes in mid-air while the camera circles it; time resumes and they scatter outward.
argument-hint: [photos folder or files]
---

Render the **Bullet-Time Gallery** cinematic card scene.

Arguments: $ARGUMENTS

1. Load the `cards-animations` skill and follow its cinematic workflow with the scene fixed to `bullet-time`.
2. Collect the photos into one folder, then run:
   `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx3d.py bullet-time --photos <folder> --out <project>/out`
3. With no photos, render with the built-in placeholders and say so.
4. Check a few frames first (`--check 1,3,5,7`), then deliver the mp4 (dark room, light) and the transparent webm (cards only).
