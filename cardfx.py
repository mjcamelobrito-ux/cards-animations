#!/usr/bin/env python3
"""cards-animations — photo-card motion presets rendered to video.

Usage:
  python3 cardfx.py <animation> [--photos DIR] [--label TEXT] [--bg HEX] [--mov] [--out DIR]
  python3 cardfx.py all            # render every animation
  python3 cardfx.py list           # list animations
  python3 cardfx.py <animation> --check 0.5,1.2,2.0   # PNG frames at those seconds, for review

Outputs (1080x1920, 30 fps):
  out/<animation>.mp4                    preview on the background colour
  out/<animation>-transparent.webm       VP9 with alpha (web, CapCut)
  out/<animation>-transparent.mov        ProRes 4444 with alpha (only with --mov)
"""
import argparse, glob, math, os, random, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
CX, CY = W / 2, H / 2

# ---------------------------------------------------------------- palette
WHITE_BASE = (248, 248, 248); BLACK = (0, 0, 0)
PURPLE = (160, 0, 255); GREEN = (150, 255, 112); SKY = (126, 232, 252)
YELLOW = (254, 255, 97); ORANGE = (254, 135, 68)

# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, k): return a + (b - a) * k
def ease_out_cubic(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in_cubic(t): t = clamp(t); return t ** 3
def ease_in_out_cubic(t): t = clamp(t); return 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2
def ease_out_back(t, s=1.6): t = clamp(t) - 1; return 1 + (s + 1) * t ** 3 + s * t ** 2
def ease_in_back(t, s=1.2): t = clamp(t); return (s + 1) * t ** 3 - s * t ** 2
def spring(t, damp=5.5, freq=9.0):
    """0 -> 1 with a soft overshoot and settle."""
    if t <= 0: return 0.0
    return 1 - math.exp(-damp * t) * math.cos(freq * t)
def window(t, t0, t1): return clamp((t - t0) / (t1 - t0))

# ---------------------------------------------------------------- cards
CW, CH = 312, 390          # on-screen size at scale 1 (4:5)
RES = 2                    # sprites are rendered at 2x for sharp enlargements
RADIUS = 44

def placeholder(i):
    combos = [(PURPLE, WHITE_BASE), (SKY, BLACK), (ORANGE, WHITE_BASE), (GREEN, BLACK), (YELLOW, BLACK),
              (PURPLE, YELLOW), (ORANGE, BLACK), (SKY, PURPLE), (GREEN, PURPLE), (YELLOW, ORANGE),
              (BLACK, GREEN), (ORANGE, SKY)]
    bg, fig = combos[i % len(combos)]
    w, h = CW * RES * 2, CH * RES * 2
    base = Image.new("RGB", (w, h), bg)
    light = Image.new("RGB", (w, h), tuple(min(255, c + 45) for c in bg))
    g = Image.radial_gradient("L").resize((w * 2, h * 2)).crop((0, 0, w, h))
    im = Image.composite(base, light, g)
    d = ImageDraw.Draw(im)
    r = random.Random(i); cx = w / 2 + r.uniform(-0.06, 0.06) * w
    d.rounded_rectangle((cx - 0.38 * w, h * 0.66, cx + 0.38 * w, h * 1.3), radius=int(0.35 * w), fill=fig)
    d.ellipse((cx - 0.2 * w, h * 0.25, cx + 0.2 * w, h * 0.25 + 0.45 * w), fill=fig)
    im = im.resize((CW * RES, CH * RES), Image.LANCZOS)
    a = np.asarray(im).astype(np.int16)
    a = np.clip(a + np.random.default_rng(i).normal(0, 3, a.shape[:2])[..., None], 0, 255).astype(np.uint8)
    return Image.fromarray(a)

def load_images(photo_dir, n):
    files = []
    if photo_dir and os.path.isdir(photo_dir):
        for e in ("jpg", "jpeg", "png", "webp", "JPG", "JPEG", "PNG", "WEBP"):
            files += glob.glob(os.path.join(photo_dir, f"*.{e}"))
    files = sorted(set(files))
    imgs = [ImageOps.fit(ImageOps.exif_transpose(Image.open(f)).convert("RGB"), (CW * RES, CH * RES), Image.LANCZOS)
            for f in files]
    if not imgs:
        imgs = [placeholder(i) for i in range(n)]
    while len(imgs) < n:                      # repeat photos if fewer than needed
        imgs.append(imgs[len(imgs) % max(1, len(files) or len(imgs))])
    return imgs[:n]

SHADOW_PAD = 40 * RES
def card_sprite(img):
    big = Image.new("L", (img.width * 3, img.height * 3), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), RADIUS * RES * 3, 255)
    mask = big.resize(img.size, Image.LANCZOS)
    card = img.convert("RGBA"); card.putalpha(mask)
    p = SHADOW_PAD
    out = Image.new("RGBA", (img.width + 2 * p, img.height + 2 * p), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 70), (p + 4 * RES, p + 14 * RES), mask)
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14 * RES)))
    out.alpha_composite(card, (p, p))
    return out

class S:
    """Card state: centre x,y; scale s (1 = 312x390 on screen); rotation r (deg);
    sx = horizontal squash for flips (0..1); a = opacity; z = paint order; shade = brightness."""
    __slots__ = ("i", "x", "y", "s", "r", "sx", "a", "z", "shade")
    def __init__(self, i, x, y, s=1.0, r=0.0, sx=1.0, a=1.0, z=0.0, shade=1.0):
        self.i, self.x, self.y, self.s, self.r, self.sx, self.a, self.z, self.shade = i, x, y, s, r, sx, a, z, shade

def draw_card(layer, sprite, st):
    if st.a <= 0.01 or st.s <= 0.005: return
    k = st.s / RES
    w = max(1, int(sprite.width * k * max(st.sx, 0.02))); h = max(1, int(sprite.height * k))
    if w * h > 9e6: return
    im = sprite.resize((w, h), Image.BILINEAR if k < 0.5 else Image.BICUBIC)
    if st.shade < 0.999:
        rgb = ImageEnhance.Brightness(im.convert("RGB")).enhance(st.shade).convert("RGBA"); rgb.putalpha(im.getchannel("A")); im = rgb
    if st.a < 0.999:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * st.a)))
    if abs(st.r) > 0.05: im = im.rotate(-st.r, Image.BICUBIC, expand=True)
    x, y = int(st.x - im.width / 2), int(st.y - im.height / 2)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + im.width), min(H, y + im.height)
    if x1 > x0 and y1 > y0:
        layer.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))

def draw_label(layer, text, x, y, a, size=56):
    if a <= 0.01 or not text: return
    f = ImageFont.truetype(os.path.join(HERE, "fonts", "Poppins-SemiBold.ttf"), size)
    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(tl)
    w = d.textlength(text, font=f)
    d.text((x - w / 2, y - size * 0.62), text, font=f, fill=(*BLACK, int(255 * clamp(a))))
    layer.alpha_composite(tl)

# ---------------------------------------------------------------- animations
# Each returns (duration, n_cards, frame_fn(t) -> (list[S], label_alpha, label_xy)).
ANIMS = {}
def anim(name, desc):
    def deco(fn): ANIMS[name] = (fn, desc); return fn
    return deco

def float_xy(i, t, amp=10):
    return math.sin(t * 1.9 + i * 1.3) * amp, math.cos(t * 1.6 + i * 0.7) * amp * 1.1

@anim("photo-bloom", "A small centre stack opens like petals around a headline, then folds back in.")
def photo_bloom():
    n, dur = 8, 4.8
    rx, ry = 360, 470
    def f(t):
        pop = ease_out_back(window(t, 0, 0.35))
        opn = ease_out_back(window(t, 0.55, 1.35), 1.3)
        cls = ease_in_out_cubic(window(t, 3.3, 4.05))
        k = opn * (1 - cls)
        out = []
        for i in range(n):
            ang = -math.pi / 2 + math.pi / n + i * 2 * math.pi / n   # no petal sits beside the headline
            fx, fy = float_xy(i, t, 9 * k)
            x = CX + math.cos(ang) * rx * k + fx; y = CY + math.sin(ang) * ry * k + fy
            r = lerp((i - n / 2) * 2.5, math.degrees(ang + math.pi / 2) * 0.12, k)
            out.append(S(i, x, y, (0.62 + 0.06 * k) * pop, r, z=i if k > 0.05 else -i))
        la = window(t, 1.05, 1.45) * (1 - window(t, 3.15, 3.35))
        return out, la, (CX, CY)
    return dur, n, f

@anim("orbiting-gallery", "Photos circle an invisible oval; the one passing the front grows while the rest recede.")
def orbiting_gallery():
    n, dur = 7, 7.0
    rx, ry = 340, 210
    def f(t):
        pop = ease_out_back(window(t, 0, 0.4))
        out = []
        for i in range(n):
            th = math.pi / 2 + i * 2 * math.pi / n - t * 2 * math.pi / dur
            depth = (math.sin(th) + 1) / 2                     # 1 = front
            d = math.atan2(math.sin(th - math.pi / 2), math.cos(th - math.pi / 2))
            front = math.exp(-(d / 0.42) ** 2)                # bump as it passes the front
            s = (0.42 + 0.22 * depth + 0.55 * front) * pop
            x = CX + math.cos(th) * rx * (1 - 0.25 * front)
            y = CY + math.sin(th) * ry - 80 * front
            out.append(S(i, x, y, s, math.cos(th) * -6 * (1 - front), z=depth + front, shade=0.82 + 0.18 * max(depth, front)))
        return out, 0, None
    return dur, n, f

@anim("shuffle-reveal", "A centred stack shuffles: the top card slides away to reveal the next, then tucks in at the back.")
def shuffle_reveal():
    n, dur, cyc = 5, 6.4, 1.5
    def slot(rank):  # rank 0 = top
        return CX + rank * 16, CY - rank * 22, 1.0 - rank * 0.05, rank * -2.0
    def f(t):
        pop = ease_out_back(window(t, 0, 0.4))
        tt = max(0, t - 0.4); c = int(tt // cyc); u = (tt % cyc) / cyc
        out = []
        for i in range(n):
            rank = (i - c) % n
            x, y, s, r = slot(rank)
            if rank == 0:            # top card: slide out, then tuck behind
                o = ease_in_out_cubic(window(u, 0.05, 0.45)); b = ease_in_out_cubic(window(u, 0.5, 0.9))
                bx, by, bs, br = slot(n - 1)
                ox, oy, orr = CX + 600, CY - 40, 16
                x = lerp(lerp(x, ox, o), bx, b); y = lerp(lerp(y, oy, o), by, b)
                s = lerp(s, bs, b); r = lerp(lerp(r, orr, o), br, b)
                z = 100 if u < 0.5 else -100
            else:                    # the rest step up one place
                k = ease_out_back(window(u, 0.3, 0.75), 1.4)
                nx, ny, ns, nr = slot(rank - 1)
                x, y, s, r = lerp(x, nx, k), lerp(y, ny, k), lerp(s, ns, k), lerp(r, nr, k)
                z = -rank
                x += math.sin(u * math.pi) * (10 if rank % 2 else -10)   # little sideways shuffle
            out.append(S(i, x, y, s * 1.05 * pop, r, z=z))
        return out, 0, None
    return dur, n, f

@anim("scattered-to-grid", "Photos float at random spots and angles, then snap into a perfectly spaced grid.")
def scattered_to_grid():
    n, dur = 9, 4.6
    r = random.Random(5)
    scat = [(r.uniform(170, 910), r.uniform(520, 1400), r.uniform(-20, 20), r.uniform(0.5, 0.62)) for _ in range(n)]
    gx, gy, gs = 300, 372, 0.84
    order = list(range(n)); r.shuffle(order)
    def f(t):
        out = []
        for j, i in enumerate(order):
            pop = ease_out_back(window(t, j * 0.05, j * 0.05 + 0.35))
            k = spring(max(0, t - (1.8 + j * 0.03)) / 0.9)
            sx0, sy0, sr0, ss0 = scat[i]
            fx, fy = float_xy(i, t, 12 * (1 - min(k, 1)))
            col, row = i % 3, i // 3
            tx, ty = CX + (col - 1) * gx, CY + (row - 1) * gy
            out.append(S(i, lerp(sx0 + fx, tx, k), lerp(sy0 + fy, ty, k), lerp(ss0, gs, k) * pop, lerp(sr0, 0, k), z=j))
        return out, 0, None
    return dur, n, f

@anim("photo-accordion", "One card expands sideways into an overlapping row, curves into a fan, then closes.")
def photo_accordion():
    n, dur = 7, 5.2
    def f(t):
        pop = ease_out_back(window(t, 0, 0.35))
        e = ease_out_back(window(t, 0.5, 1.25), 1.2)           # expand to row
        fan = ease_in_out_cubic(window(t, 1.35, 2.05))           # curve into fan
        cls = ease_in_out_cubic(window(t, 3.5, 4.4))             # close
        e *= (1 - cls); fan *= (1 - cls)
        out = []
        for i in range(n):
            o = i - (n - 1) / 2
            rx_, ry_, rr = CX + o * 112 * e, CY, 0.0
            a = math.radians(o * 10)                             # fan around a pivot below
            R = 620
            fx, fy, fr = CX + R * math.sin(a), CY + 300 - R * math.cos(a), math.degrees(a)
            x, y, r = lerp(rx_, fx, fan), lerp(ry_, fy, fan), lerp(rr, fr, fan)
            breathe = math.sin(t * 2.4) * 2.5 * fan
            out.append(S(i, x, y, 0.8 * pop, r + breathe * o / 3, z=i))
        return out, 0, None
    return dur, n, f

@anim("magnetic-cluster", "One photo lands in the centre; the others glide in from all sides and lock around it.")
def magnetic_cluster():
    n, dur = 7, 4.8
    slots = [(0, 0, 0.82, 0)] + [(math.cos(math.radians(a)) * rr, math.sin(math.radians(a)) * rr * 1.18, s, rot)
             for a, rr, s, rot in [(-90, 300, 0.58, -5), (-30, 315, 0.6, 6), (30, 300, 0.56, -4),
                                   (90, 300, 0.6, 5), (150, 315, 0.58, -6), (210, 300, 0.56, 4)]]
    froms = [None, (CX, -400), (W + 400, 500), (W + 400, 1500), (CX, H + 400), (-400, 1500), (-400, 500)]
    def f(t):
        out = []
        bump = 0
        for i in range(n):
            sx_, sy_, ss, sr = slots[i]
            tx, ty = CX + sx_, CY + sy_
            if i == 0:
                out.append(None); continue
            t0 = 0.45 + (i - 1) * 0.16
            k = ease_out_back(window(t, t0, t0 + 0.7), 1.25)
            land = window(t, t0 + 0.55, t0 + 0.75); bump = max(bump, math.sin(land * math.pi) * 0.03)
            fx, fy = froms[i]
            gf = float_xy(i, t, 6 * window(t, 2.4, 2.8))
            out.append(S(i, lerp(fx, tx, k) + gf[0], lerp(fy, ty, k) + gf[1], ss, lerp(sr * 4, sr, k), z=1 + i % 2))
        c = ease_out_back(window(t, 0, 0.4))
        gf = float_xy(0, t, 4 * window(t, 2.4, 2.8))
        out[0] = S(0, CX + gf[0], CY + gf[1], 0.82 * c * (1 + bump), 0, z=0.5)
        return out, 0, None
    return dur, n, f

@anim("focus-spotlight", "Small photos float around; one glides to the centre and grows while the others step back. Repeats.")
def focus_spotlight():
    n, dur = 8, 7.0
    ring = [(CX + math.cos(a) * 360, CY + math.sin(a) * 600) for a in [math.radians(-90 + i * 45 + 8) for i in range(n)]]
    focus = [(0, 0.6), (3, 2.7), (6, 4.8)]                     # (card, start)
    def fk(t, t0): return ease_in_out_cubic(window(t, t0, t0 + 0.55)) * (1 - ease_in_out_cubic(window(t, t0 + 1.6, t0 + 2.15)))
    def f(t):
        F = max(fk(t, t0) for _, t0 in focus)
        out = []
        for i in range(n):
            pop = ease_out_back(window(t, i * 0.04, i * 0.04 + 0.35))
            bx, by = ring[i]; fx, fy = float_xy(i, t, 12)
            mine = max([fk(t, t0) for c, t0 in focus if c == i] or [0])
            push = 1 + 0.16 * (F - mine)
            x = CX + (bx - CX) * push + fx; y = CY + (by - CY) * push + fy
            s = 0.44 * (1 - 0.25 * (F - mine))
            x, y, s = lerp(x, CX, mine), lerp(y, CY, mine), lerp(s, 1.3, mine)
            out.append(S(i, x, y, s * pop, math.sin(t + i) * 4 * (1 - mine), z=mine * 10 + i * 0.01))
        return out, 0, None
    return dur, n, f

@anim("picture-tunnel", "Each photo flies toward the viewer and past the frame while the next appears behind it.")
def picture_tunnel():
    n, dur, gap, life = 8, 6.4, 0.8, 3.2                       # dur = n*gap -> seamless loop
    g = math.log(6.2 / 0.2)
    def f(t):
        out = []
        for i in range(n):
            for rep in (-1, 0, 1):
                age = t - i * gap + rep * dur + 1.6
                p = age / life
                if not 0 <= p <= 1: continue
                s = 0.2 * math.exp(g * p ** 2.2)      # slow approach, quick pass
                a = clamp(p / 0.1) if s < 6.0 else 0     # stays solid; vanishes once it fills the frame
                out.append(S(i, CX + math.sin(i * 2.4) * 340 * (1 - p) ** 1.3, CY + math.cos(i * 2.4) * 500 * (1 - p) ** 1.3,
                             s, (-4 if i % 2 else 4) * (1 - p), a=a, z=s))
        return out, 0, None
    return dur, n, f

@anim("domino-flips", "Cards flip from thin edges to full photos in a staggered wave, then fold away in reverse.")
def domino_flips():
    n, dur = 6, 4.8
    def f(t):
        out = []
        for i in range(n):
            col, row = i % 2, i // 2
            x, y = CX + (col - 0.5) * 330, CY + (row - 1) * 400
            t_in = 0.3 + i * 0.13; t_out = 3.0 + (n - 1 - i) * 0.13
            edge = window(t, t_in - 0.2, t_in)                # thin edge fades in first
            sx = ease_out_back(window(t, t_in, t_in + 0.45), 1.8) * (1 - ease_in_back(window(t, t_out, t_out + 0.35)))
            gone = t > t_out + 0.35
            a = 0 if gone else edge
            shade = 0.55 + 0.45 * clamp(sx)
            out.append(S(i, x, y, 0.95, 0, sx=max(sx, 0.025), a=a, z=i, shade=shade))
        return out, 0, None
    return dur, n, f

@anim("photo-ribbon", "Photos glide along a gentle curve, slow down through the centre, then gather into a neat stack.")
def photo_ribbon():
    n, dur = 8, 5.8
    P = [(-320, 1450), (260, 620), (820, 1320), (1420, 520)]       # cubic bezier
    def bez(u):
        a, b, c, d = P; m = 1 - u
        x = m**3 * a[0] + 3 * m * m * u * b[0] + 3 * m * u * u * c[0] + u**3 * d[0]
        y = m**3 * a[1] + 3 * m * m * u * b[1] + 3 * m * u * u * c[1] + u**3 * d[1]
        return x, y
    def warp(s): return s + 0.55 / (2 * math.pi) * math.sin(2 * math.pi * s)   # slow through the middle
    def f(t):
        gather = ease_in_out_cubic(window(t, 3.9, 4.75))
        out = []
        for i in range(n):
            s = t * 0.235 - i * 0.105
            if s < 0 and gather == 0: continue
            u = warp(clamp(s))
            x, y = bez(u)
            x2, y2 = bez(clamp(u + 0.01))
            tang = math.degrees(math.atan2(y2 - y, x2 - x)) * 0.35
            off = (i - n / 2)
            sx_, sy_, sr = CX + off * 4, CY - off * 5, off * 1.5
            if s < 0: x, y = bez(0)
            out.append(S(i, lerp(x, sx_, gather), lerp(y, sy_, gather), lerp(0.62, 0.85, gather), lerp(tang, sr, gather),
                         a=1 if s >= 0 else gather, z=i if gather > 0.5 else -i))
        return out, 0, None
    return dur, n, f

# ---------------------------------------------------------------- render
def build(name, photos, label):
    fn, _ = ANIMS[name]
    dur, n, frame_fn = fn()
    sprites = [card_sprite(im) for im in load_images(photos, n)]
    def content(t):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        states, la, lxy = frame_fn(t)
        if la and lxy: draw_label(layer, label, *lxy, la)
        for st in sorted(states, key=lambda s: s.z):
            draw_card(layer, sprites[st.i], st)
        return layer
    return dur, content

def hex_rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def render(name, args):
    dur, content = build(name, args.photos, args.label)
    os.makedirs(args.out, exist_ok=True)
    if args.check:
        for s in [float(x) for x in args.check.split(",")]:
            bg = Image.new("RGBA", (W, H), (*hex_rgb(args.bg), 255)); bg.alpha_composite(content(s))
            bg.convert("RGB").save(os.path.join(args.out, f"{name}-{s:.2f}.png"))
        return
    nfr = int(round(dur * FPS))
    base = os.path.join(args.out, name)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", f"color=c=0x{args.bg.lstrip('#')}:s={W}x{H}:r={FPS}",
           "-filter_complex", ("[0:v]split=3[a][b][c];" if args.mov else "[0:v]split=2[a][b];")
                              + "[1:v][a]overlay=shortest=1,format=yuv420p[mp4]",
           "-map", "[mp4]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-movflags", "+faststart", base + ".mp4",
           "-map", "[b]", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "30", "-row-mt", "1",
           "-auto-alt-ref", "0", "-deadline", "realtime", "-cpu-used", "5", base + "-transparent.webm"]
    if args.mov:
        cmd += ["-map", "[c]", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                "-alpha_bits", "16", "-vendor", "apl0", base + "-transparent.mov"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in range(nfr):
        proc.stdin.write(content(fr / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0: sys.exit(f"ffmpeg failed for {name}")
    print(f"{name}: {base}.mp4, {base}-transparent.webm" + (f", {base}-transparent.mov" if args.mov else ""))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("animation", help="animation name, 'all' or 'list'")
    ap.add_argument("--photos", default=os.path.join(HERE, "photos"), help="folder of photos (placeholders if empty)")
    ap.add_argument("--label", default="Made to stand out", help="headline (photo-bloom)")
    ap.add_argument("--bg", default="#F8F8F8", help="background colour of the preview mp4")
    ap.add_argument("--mov", action="store_true", help="also export transparent ProRes 4444 .mov")
    ap.add_argument("--out", default="out")
    ap.add_argument("--check", help="comma-separated seconds: save PNG frames instead of video")
    args = ap.parse_args()
    if args.animation == "list":
        for k, (_, d) in ANIMS.items(): print(f"{k:20s} {d}")
        return
    names = list(ANIMS) if args.animation == "all" else [args.animation]
    for nm in names:
        if nm not in ANIMS: sys.exit(f"unknown animation '{nm}'. Try: {', '.join(ANIMS)}")
        render(nm, args)

if __name__ == "__main__":
    main()
