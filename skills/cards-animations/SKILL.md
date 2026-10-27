---
name: cards-animations
description: Render photo-card motion presets (Photo Bloom, Orbiting Gallery, Shuffle and Reveal, Scattered to Organized, Photo Accordion, Magnetic Photo Cluster, Focus Spotlight, Picture Tunnel, Domino Flips, Photo Ribbon) as vertical video with transparent exports. Use when the user runs one of these commands or asks for a card/photo animation by one of these names.
---

# Cards Animations

Everything renders through `${CLAUDE_PLUGIN_ROOT}/cardfx.py` (Python 3 + Pillow + NumPy + FFmpeg). Output is 1080×1920 at 30 fps.

## Animations

| Command | Name | What happens |
|---|---|---|
| `/photo-bloom` | Photo Bloom | A small centre stack opens like petals around a headline, then folds back in. |
| `/orbiting-gallery` | Orbiting Gallery | Photos circle an invisible oval; the one passing the front grows while the rest recede. |
| `/shuffle-reveal` | Shuffle and Reveal | A centred stack shuffles: the top card slides away to reveal the next, then tucks in at the back. |
| `/scattered-to-grid` | Scattered to Organized | Photos float at random spots and angles, then snap into a perfectly spaced grid. |
| `/photo-accordion` | Photo Accordion | One card expands sideways into an overlapping row, curves into a fan, then closes. |
| `/magnetic-cluster` | Magnetic Photo Cluster | One photo lands in the centre; the others glide in from all sides and lock around it. |
| `/focus-spotlight` | Focus Spotlight | Small photos float around; one glides to the centre and grows while the others step back. Repeats. |
| `/picture-tunnel` | Picture Tunnel | Each photo flies toward the viewer and past the frame while the next appears behind it. |
| `/domino-flips` | Domino Flips | Cards flip from thin edges to full photos in a staggered wave, then fold away in reverse. |
| `/photo-ribbon` | Photo Ribbon | Photos glide along a gentle curve, slow down through the centre, then gather into a neat stack. |

## Workflow
1. Check the tools: `python3 -c "import PIL, numpy"` and `ffmpeg -version`; `pip install pillow numpy --break-system-packages` if missing.
2. Put the user's photos in one folder. Any size works: each is cover-cropped to a 4:5 card with rounded corners. Fewer photos than the animation needs are repeated; none means palette placeholders.
3. Pick options from the user's notes:
   - `--label "text"` headline (used by photo-bloom)
   - `--bg "#RRGGBB"` background of the preview mp4 (default White Base #F8F8F8)
   - `--mov` adds a ProRes 4444 transparent .mov for Premiere / Final Cut / DaVinci / After Effects (large files)
4. Review first: `python3 cardfx.py <name> --photos <dir> --check 0.5,1.5,3.0 --out <dir>` writes PNG frames; look at them.
5. Render: `python3 cardfx.py <name> --photos <dir> --out <dir>`. Run at most two renders in parallel.
6. Deliver `<name>.mp4` (preview) and `<name>-transparent.webm` (alpha; web, CapCut), plus the .mov if asked.

## Look
- Palette: Vision Purple #A000FF, Astral Achievement #000000, White Base #F8F8F8, Prospera Grow #96FF70, Limitless Sky #7EE8FC, Opportunity Glow #FEFF61, Flame of Success #FE8744.
- Cards: 312×390 px at scale 1, 44 px corner radius, soft drop shadow. Headline: Poppins SemiBold 56 px, black.

## Changing an animation
Each animation is one function in `cardfx.py` decorated with `@anim(name, description)`. It returns `(duration, card_count, frame_fn)`; `frame_fn(t)` returns a list of card states `S(i, x, y, s, r, sx, a, z, shade)` plus the headline opacity and position. Add a new animation the same way, then add a command file in `commands/`.
