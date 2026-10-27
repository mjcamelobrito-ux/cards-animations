# cards-animations

Ten photo-card animations for vertical video, as a Claude Code plugin. Drop in photos, run one command, get a 1080×1920 preview plus a **transparent** version to layer over any footage.

| Command | Animation | What happens |
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

## Install

```
/plugin marketplace add mjcamelobrito-ux/cards-animations
/plugin install cards-animations@cards-animations-marketplace
```

Then: `/photo-bloom ./my-photos --label "Made to stand out"`, or `/cards-animate all ./my-photos`.

## Without Claude

```
pip install pillow numpy
python3 cardfx.py list
python3 cardfx.py photo-bloom --photos ./my-photos --label "Made to stand out"
python3 cardfx.py all --mov          # every animation, incl. ProRes 4444 .mov
```

Outputs go to `out/`:
- `<name>.mp4` — preview on White Base (`--bg` to change)
- `<name>-transparent.webm` — VP9 with alpha (web, CapCut, Chrome)
- `<name>-transparent.mov` — ProRes 4444 with alpha, with `--mov` (Premiere, Final Cut, DaVinci, After Effects)

Photos: any size, cover-cropped to 4:5 cards with rounded corners. With no photos, palette placeholders are used. Put photos in `photos/` or pass `--photos`.

## Palette & type
Vision Purple `#A000FF` · Astral Achievement `#000000` · White Base `#F8F8F8` · Prospera Grow `#96FF70` · Limitless Sky `#7EE8FC` · Opportunity Glow `#FEFF61` · Flame of Success `#FE8744`. Headline in Poppins SemiBold (SIL Open Font License, `fonts/OFL.txt`).
