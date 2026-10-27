#!/usr/bin/env python3
"""cards-animations 3D — cinematic photo-card scenes: perspective camera, depth of field, light.

Usage:
  python3 cardfx3d.py <animation|all|list> [--photos DIR] [--bg HEX] [--out DIR] [--check 0.5,2,4]

Outputs (1080x1920, 30 fps):
  out/<animation>.mp4                 with the dark room, light beams and glows
  out/<animation>-transparent.webm    cards only, alpha background
"""
import argparse, math, os, random, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops

import cardfx as flat   # shared photo loading + placeholders + easing
from cardfx import clamp, lerp, window, ease_in_out_cubic, ease_out_cubic, ease_in_cubic, ease_out_back

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
FOV = 50.0
CARD_W, CARD_H = 1.0, 1.25           # world units at size 1 (4:5)
SPR_W, SPR_H = 936, 1170             # sprite resolution (3x of 312x390)
NEAR = 0.12

PURPLE = (160, 0, 255); GREEN = (150, 255, 112); SKY = (126, 232, 252)
YELLOW = (254, 255, 97); ORANGE = (254, 135, 68); WHITE_BASE = (248, 248, 248)
ROOM = (8, 8, 12)

# ------------------------------------------------------------------ math
def norm(v): v = np.asarray(v, float); return v / (np.linalg.norm(v) + 1e-9)
def Rx(a): c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def Ry(a): c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def Rz(a): c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def rot(yaw=0, pitch=0, roll=0):
    """degrees; card faces -z (toward a camera at -z) when all zero."""
    return Ry(math.radians(yaw)) @ Rx(math.radians(pitch)) @ Rz(math.radians(roll))

class Camera:
    def __init__(self, pos, target, fov=FOV, roll=0.0):
        self.pos = np.asarray(pos, float)
        f = norm(np.asarray(target, float) - self.pos)
        up = np.array([0.0, 1.0, 0.0])
        if abs(f @ up) > 0.999: up = np.array([0.0, 0.0, 1.0])
        r = norm(np.cross(up, f)); u = np.cross(f, r)
        if roll:
            c, s = math.cos(math.radians(roll)), math.sin(math.radians(roll))
            r, u = c * r + s * u, -s * r + c * u
        self.r, self.u, self.f = r, u, f
        self.F = (H / 2) / math.tan(math.radians(fov) / 2)
    def to_cam(self, p):
        d = np.asarray(p, float) - self.pos
        return np.stack([d @ self.r, d @ self.u, d @ self.f], -1)
    def project(self, pc):
        return W / 2 + self.F * pc[..., 0] / pc[..., 2], H / 2 - self.F * pc[..., 1] / pc[..., 2]

def perspective_coeffs(dst, src):
    """coefficients for PIL PERSPECTIVE mapping output points dst -> input points src."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()

# ------------------------------------------------------------------ sprites
def rounded(img, radius):
    big = Image.new("L", (img.width * 2, img.height * 2), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius * 2, 255)
    out = img.convert("RGBA"); out.putalpha(big.resize(img.size, Image.LANCZOS)); return out

def mips(img):
    levels = [img]
    while levels[-1].height > 80:
        im = levels[-1]; levels.append(im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.LANCZOS))
    return levels

def back_sprite():
    a = np.full((SPR_H, SPR_W, 3), 52, np.int16)
    a += np.random.default_rng(1).normal(0, 3, (SPR_H, SPR_W, 1)).astype(np.int16)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im); d.rounded_rectangle((6, 6, SPR_W - 7, SPR_H - 7), 120, outline=(120, 120, 135), width=8)
    return rounded(im, 132)

def rim_sprite():
    im = Image.new("RGBA", (SPR_W, SPR_H), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((2, 2, SPR_W - 3, SPR_H - 3), 130, outline=(255, 255, 255, 255), width=10)
    return im

class Library:
    def __init__(self, photos, n):
        flat.RES = 3
        imgs = flat.load_images(photos, n)
        self.has_photos = bool(photos and os.path.isdir(photos) and any(
            f.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) for f in os.scandir(photos)))
        self.raw = imgs
        self.photo = [mips(rounded(im.resize((SPR_W, SPR_H), Image.LANCZOS), 132)) for im in imgs]
        self.back = mips(back_sprite())
        self.rim = mips(rim_sprite())
        self.extra = {}
    def add(self, key, img): self.extra[key] = mips(img.convert("RGBA"))
    def get(self, key):
        if isinstance(key, int): return self.photo[key % len(self.photo)]
        if key == "back": return self.back
        if key == "rim": return self.rim
        return self.extra[key]

# ------------------------------------------------------------------ card instances
class Card:
    __slots__ = ("img", "pos", "R", "size", "shade", "alpha", "rim", "aspect", "two_sided", "sharp", "glow")
    def __init__(self, img, pos, R=None, size=1.0, shade=1.0, alpha=1.0, rim=0.0, aspect=1.25, two_sided=True,
                 sharp=False, glow=0.0):
        self.img, self.pos, self.R, self.size = img, np.asarray(pos, float), (R if R is not None else np.eye(3)), size
        self.shade, self.alpha, self.rim, self.aspect, self.two_sided, self.sharp, self.glow = \
            shade, alpha, rim, aspect, two_sided, sharp, glow

def shade_lut(k, a):
    k = max(0.0, k); a = clamp(a)
    rgb = [min(255, int(i * k)) for i in range(256)]
    return rgb * 3 + [int(i * a) for i in range(256)]

def draw_cards(layer, cam, cards, lib, focus, aperture, glow_layer=None):
    items = []
    for c in cards:
        hw, hh = 0.5 * c.size * CARD_W, 0.5 * c.size * CARD_W * c.aspect
        local = np.array([[-hw, hh, 0], [hw, hh, 0], [hw, -hh, 0], [-hw, -hh, 0]])
        world = local @ c.R.T + c.pos
        pc = cam.to_cam(world)
        if (pc[:, 2] < NEAR).any(): continue
        sx, sy = cam.project(pc)
        if sx.max() < -50 or sx.min() > W + 50 or sy.max() < -50 or sy.min() > H + 50: continue
        normal = c.R @ np.array([0, 0, -1.0])
        front = normal @ (cam.pos - c.pos) > 0
        items.append((pc[:, 2].mean(), c, sx, sy, front, pc[:, 2].mean()))
    items.sort(key=lambda t: -t[0])
    for _, c, sx, sy, front, z in items:
        key = c.img if (front or not c.two_sided) else "back"
        if not front and not c.two_sided: continue
        pts = list(zip(sx, sy))
        if not front:  # mirror mapping so the back reads correctly
            pts = [pts[1], pts[0], pts[3], pts[2]]
        coc = 0 if c.sharp else aperture * cam.F * abs(1 / z - 1 / focus)
        im = warp(lib.get(key), pts)
        if im is None: continue
        img, (ox, oy) = im
        if c.shade != 1 or c.alpha != 1:
            img = img.point(shade_lut(c.shade, c.alpha))
        if c.rim > 0.01:
            rim = warp(lib.get("rim"), pts)
            if rim:
                r_img, _ = rim
                r_img = r_img.point(shade_lut(1, c.rim * c.alpha))
                img.alpha_composite(r_img)
        if c.glow > 0.01 and glow_layer is not None:
            g = img.getchannel("A").filter(ImageFilter.GaussianBlur(28))
            col = Image.new("RGBA", img.size, (255, 248, 225, 0)); col.putalpha(g.point(lambda v: int(min(255, v * 2.2 * c.glow))))
            paste(glow_layer, col, ox, oy)
        if coc > 1.2:
            img = blur(img, float(min(coc / 2, 60)))
        paste(layer, img, ox, oy)

def warp(levels, pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = max(int(math.floor(min(xs))) - 2, -40), min(int(math.ceil(max(xs))) + 2, W + 40)
    y0, y1 = max(int(math.floor(min(ys))) - 2, -40), min(int(math.ceil(max(ys))) + 2, H + 40)
    if x1 - x0 < 2 or y1 - y0 < 2: return None
    span = max(math.dist(pts[0], pts[3]), math.dist(pts[1], pts[2]), math.dist(pts[0], pts[1]) * 1.25)
    lv = levels[0]
    for L in levels:
        if L.height >= span * 0.9: lv = L
    src = [(0, 0), (lv.width, 0), (lv.width, lv.height), (0, lv.height)]
    dst = [(x - x0, y - y0) for x, y in pts]
    try:
        coeffs = perspective_coeffs(dst, src)
    except np.linalg.LinAlgError:
        return None
    return lv.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, coeffs, Image.BILINEAR), (x0, y0)

def blur(img, r):
    if r <= 3: return img.filter(ImageFilter.GaussianBlur(r))
    k = r / 3
    pad = int(r * 1.5)
    big = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0)); big.paste(img, (pad, pad))
    sm = big.resize((max(1, int(big.width / k)), max(1, int(big.height / k))), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    out = sm.resize(big.size, Image.BILINEAR)
    out.info["pad"] = pad
    return out

def paste(layer, img, ox, oy):
    pad = img.info.get("pad", 0); ox -= pad; oy -= pad
    x0, y0 = max(0, ox), max(0, oy); x1, y1 = min(W, ox + img.width), min(H, oy + img.height)
    if x1 <= x0 or y1 <= y0: return
    layer.alpha_composite(img.crop((x0 - ox, y0 - oy, x1 - ox, y1 - oy)), (x0, y0))

# ------------------------------------------------------------------ backgrounds & light
def room(color=ROOM, glow=(28, 26, 40), cy=0.45):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * cy) / H) ** 2)
    k = np.clip(1 - d * 1.6, 0, 1)[..., None]
    img = np.array(color, np.float32) + k * (np.array(glow, np.float32) - np.array(color, np.float32))
    return img

_ROOM_CACHE = {}
def room_bg(key="default", **kw):
    if key not in _ROOM_CACHE: _ROOM_CACHE[key] = room(**kw)
    return _ROOM_CACHE[key].copy()

def add_glow(arr, x, y, rx, ry, color, strength):
    if strength <= 0: return
    x0, x1 = int(max(0, x - rx * 2.5)), int(min(W, x + rx * 2.5)); y0, y1 = int(max(0, y - ry * 2.5)), int(min(H, y + ry * 2.5))
    if x1 <= x0 or y1 <= y0: return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    g = np.exp(-(((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2)) * strength / 100
    arr[y0:y1, x0:x1] += g[..., None] * np.array(color, np.float32)

def add_shaft(arr, x_top, x_bot, w_top, w_bot, color, strength, y0=0, y1=H):
    if strength <= 0: return
    yy, xx = np.mgrid[y0:y1, 0:W].astype(np.float32)
    k = (yy - y0) / max(1, (y1 - y0))
    cx = x_top + (x_bot - x_top) * k; w = w_top + (w_bot - w_top) * k
    g = np.exp(-((xx - cx) / w) ** 2) * strength / 100 * (0.55 + 0.45 * (1 - k))
    arr[y0:y1] += g[..., None] * np.array(color, np.float32)

def add_dust(arr, cam, pts, t, light_fn=None, size=3.0):
    pc = cam.to_cam(pts)
    ok = pc[:, 2] > 0.3
    sx, sy = cam.project(pc[ok]); z = pc[ok, 2]
    lit = light_fn(pts[ok]) if light_fn else np.full(len(z), 0.5)
    for x, y, zz, l in zip(sx, sy, z, lit):
        if 0 <= x < W and 0 <= y < H:
            r = max(1.0, size * 4 / zz)
            add_glow(arr, x, y, r, r, (255, 245, 225), 45 * l)

# ------------------------------------------------------------------ scenes
SCENES = {}
def scene(name, desc):
    def deco(fn): SCENES[name] = (fn, desc); return fn
    return deco

class Frame:
    def __init__(self, cam, cards, focus, aperture, bg=None, flash=0.0):
        self.cam, self.cards, self.focus, self.aperture, self.bg, self.flash = cam, cards, focus, aperture, bg, flash

def rnd(seed): return random.Random(seed)

@scene("frozen-storm", "Dozens of photos hang at different depths in a dark room; the camera drifts past blurred cards to one lit image, then they all rush past the lens.")
def frozen_storm(lib):
    dur, n = 8.0, 64
    r = rnd(3); hero = 0
    hero_pos = np.array([0.35, 0.25, 15.0])
    cards = []
    for i in range(1, n):
        while True:
            p = np.array([r.uniform(-5, 5), r.uniform(-7, 7), r.uniform(-3, 26)])
            if math.hypot(p[0] - 0.2 * (p[2] / 15), p[1]) > 1.0 and np.linalg.norm(p - hero_pos) > 1.6: break
        cards.append((i, p, (r.uniform(-45, 45), r.uniform(-35, 35), r.uniform(-30, 30)), r.uniform(0.8, 1.2), r.uniform(0, 6.28)))
    for j in range(46):
        p = np.array([r.uniform(-2.8, 2.8), r.uniform(-4.2, 4.2), r.uniform(16.8, 44)])
        cards.append((1 + j % (n - 1), p, (r.uniform(-45, 45), r.uniform(-35, 35), r.uniform(-30, 30)), r.uniform(0.8, 1.2), r.uniform(0, 6.28)))
    dust = np.array([[r.uniform(-5, 5), r.uniform(-7, 7), r.uniform(-4, 40)] for _ in range(140)])
    def f(t):
        k = ease_in_out_cubic(window(t, 0.0, 5.6))
        cam_pos = np.array([lerp(-0.8, hero_pos[0], k) + math.sin(t * 0.6) * 0.15, lerp(0.6, hero_pos[1], k), lerp(-9.0, hero_pos[2] - 3.0, k)])
        look = hero_pos + np.array([lerp(-1.5, 0, k), lerp(-0.5, 0, k), 0])
        cam = Camera(cam_pos, look)
        rush = window(t, 6.2, 8.0) ** 1.7 * 40
        out = []
        for i, p, (yw, pt, rl), s, ph in cards:
            pp = p + np.array([math.sin(t * 0.3 + ph) * 0.05, math.cos(t * 0.25 + ph) * 0.05, -rush])
            d = np.linalg.norm(pp - cam_pos)
            out.append(Card(i, pp, rot(yw + math.sin(t * 0.2 + ph) * 3, pt, rl), s, shade=0.42 + 0.25 * clamp(1 - d / 20)))
        hp = hero_pos + np.array([0, 0, -rush * 1.05])
        light = 0.45 + 0.6 * window(t, 4.2, 5.6)
        out.append(Card(hero, hp, rot(0, 0, math.sin(t * 0.4) * 2), 1.15, shade=light))
        focus = max(0.5, np.linalg.norm(hero_pos - cam_pos))
        def bg():
            a = room_bg("storm")
            hx, hy = cam.project(cam.to_cam(hp[None]))
            if cam.to_cam(hp[None])[0, 2] > 0.5:
                add_glow(a, hx[0], hy[0], 520, 620, (255, 240, 210), 40 * window(t, 4.2, 5.6) * (1 - window(t, 6.4, 7.0)))
            add_shaft(a, W * 0.62, W * 0.5, 60, 380, (255, 244, 220), 26 * window(t, 4.0, 5.6) * (1 - window(t, 6.4, 7.2)))
            add_dust(a, cam, dust - np.array([0, 0, rush]), t)
            return a
        return Frame(cam, out, focus, 0.06, bg)
    return dur, n, f

@scene("memory-corridor", "Photos line both sides of an endless corridor; the camera speeds up as each catches the light, then one turns to the lens and fills the screen.")
def memory_corridor(lib):
    dur, n = 8.0, 56
    r = rnd(7)
    slots = []
    for k in range(n):
        side = -1 if k % 2 else 1
        slots.append((k, np.array([side * r.uniform(1.35, 1.55), r.uniform(-0.45, 0.55), 2.2 + k * 0.95]), side * r.uniform(48, 56), r.uniform(-4, 4), r.uniform(1.35, 1.55)))
    ts = np.linspace(0, dur, int(dur * FPS) + 2)
    v = np.where(ts < 5.4, 1.2 + 1.35 * ts, 0)
    v_end = 1.2 + 1.35 * 5.4
    v = np.where(ts >= 5.4, v_end * (1 - ease_in_out_cubic_np((ts - 5.4) / 1.9)), v)
    zcam = np.concatenate([[0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(ts))])
    hero_k = int((zcam[-1] + 2.6 - 2.2) / 0.95); hero_k += hero_k % 2
    def f(t):
        cz = float(np.interp(t, ts, zcam))
        cam = Camera([0, 0.05, cz], [0, 0.0, cz + 10], fov=70)
        out = []
        for k, p, yaw, roll, s in slots:
            rel = p[2] - cz
            light = 0.3 + 0.85 * math.exp(-((rel - 6.0) / 2.4) ** 2)
            if k == hero_k:
                turn = ease_in_out_cubic(window(t, 6.0, 7.6))
                target = np.array([0, 0.03, cz + 1.0])
                pp = p + (target - p) * turn
                out.append(Card(k, pp, rot(lerp(yaw, 0, turn), 0, lerp(roll, 0, turn)), lerp(s, 1.02, turn),
                                shade=max(light, turn * 1.05), sharp=turn > 0.5))
            else:
                out.append(Card(k, p, rot(yaw, 0, roll), s, shade=light))
        def bg():
            a = room_bg("corridor", cy=0.5, glow=(34, 32, 50))
            add_glow(a, W / 2, H * 0.5, 200, 200, (255, 240, 215), 30)
            return a
        return Frame(cam, out, 6.0, 0.03, bg)
    return dur, n, f

def ease_in_out_cubic_np(x):
    x = np.clip(x, 0, 1); return np.where(x < .5, 4 * x ** 3, 1 - (-2 * x + 2) ** 3 / 2)

@scene("falling-photos", "Photos fall slowly through a spotlight, tumbling like paper; the camera follows one as it turns face-up and lands on a growing pile.")
def falling_photos(lib):
    dur, n = 8.5, 16
    r = rnd(11); floor = -3.2; hero = 0; T_hero = 6.0
    specs = []
    for i in range(n):
        if i == hero:
            specs.append(dict(i=i, x0=0.15, z0=0.1, t_land=T_hero, y0=5.4, spin=0, ph=0.0, pile=(0.05, 0.0, 12)))
        else:
            tl = r.uniform(1.2, 7.4) if i < 12 else r.uniform(7.0, 8.3)
            specs.append(dict(i=i, x0=r.uniform(-1.6, 1.6), z0=r.uniform(-1.0, 1.4), t_land=tl, y0=r.uniform(4.5, 7.5),
                              spin=r.uniform(-90, 90), ph=r.uniform(0, 6.28), pile=(r.uniform(-0.6, 0.6), r.uniform(-0.5, 0.5), r.uniform(-60, 60))))
    order = sorted(range(n), key=lambda j: specs[j]["t_land"])
    for h, j in enumerate(order): specs[j]["h"] = floor + 0.012 * h
    dust = np.array([[r.uniform(-2, 2), r.uniform(-3.2, 7), r.uniform(-1.5, 1.8)] for _ in range(90)])
    def light_at(p): return 0.16 + 0.95 * np.exp(-((p[..., 0]) ** 2 + (p[..., 2] - 0.2) ** 2) / 2.2 ** 2)
    def state(sp, t):
        fall_t = 3.8
        u = (t - (sp["t_land"] - fall_t)) / fall_t
        px, pz, pr = sp["pile"]
        if u < 0: return None
        if u >= 1:
            return np.array([px, sp["h"], pz]), rot(pr, 90, 0)
        y = lerp(sp["y0"], sp["h"], u)
        x = sp["x0"] + math.sin(u * 6 + sp["ph"]) * 0.45 * (1 - u) + (px - sp["x0"]) * ease_in_out_cubic(u)
        z = sp["z0"] + (pz - sp["z0"]) * ease_in_out_cubic(u)
        if sp["i"] == hero:
            pitch = lerp(180, 90, ease_in_out_cubic(window(u, 0.25, 0.95)))       # turns face-up while falling
            yaw = math.sin(u * 5) * 18 * (1 - u); roll = math.sin(u * 4) * 20 * (1 - u)
        else:
            pitch = lerp(sp["ph"] * 57 + u * 420, 90, ease_in_cubic(window(u, 0.75, 1.0)))
            yaw = sp["spin"] * u + math.sin(u * 5 + sp["ph"]) * 25 * (1 - u); roll = math.sin(u * 4 + sp["ph"]) * 35 * (1 - u)
        land = ease_in_cubic(window(u, 0.85, 1.0))
        return np.array([x, y, z]), rot(lerp(yaw, pr, land), pitch, roll * (1 - land))
    def f(t):
        hs = state(specs[hero], t)
        hp = hs[0] if hs is not None else np.array([0.15, 5.4, 0.1])
        follow = ease_in_out_cubic(window(t, 1.2, 2.6))
        settle = ease_in_out_cubic(window(t, T_hero - 0.6, T_hero + 0.9))
        cy = lerp(1.0, hp[1] + 0.9, follow)
        cy = lerp(cy, floor + 3.4, settle)
        cam_pos = np.array([0.0, cy, lerp(-7.5, -4.2, follow)])
        cam_pos = cam_pos + (np.array([0.0, floor + 3.4, -2.6]) - cam_pos) * settle
        look = np.array([0, lerp(0.6, hp[1], follow), 0.0])
        look = look + (np.array([0, floor, 0.4]) - look) * settle
        cam = Camera(cam_pos, look)
        out = []
        for sp in specs:
            s = state(sp, t)
            if s is None: continue
            p, R = s
            out.append(Card(sp["i"], p, R, 0.95, shade=float(light_at(p[None])[0]), sharp=sp["i"] == hero))
        focus = float(np.linalg.norm(hp - cam_pos))
        def bg():
            a = room_bg("fall", glow=(16, 15, 22))
            top = cam.to_cam(np.array([[0, 9.0, 0.2]])); bot = cam.to_cam(np.array([[0, floor, 0.2]]))
            tx, ty = cam.project(top); bx, by = cam.project(bot)
            add_shaft(a, float(tx[0]), float(bx[0]), 60, 520, (255, 242, 215), 30, 0, H)
            if bot[0, 2] > 0.3:
                add_glow(a, float(bx[0]), float(by[0]), 620 * 4.5 / bot[0, 2], 200 * 4.5 / bot[0, 2], (255, 240, 210), 38)
            add_dust(a, cam, dust + np.array([0, -t * 0.12, 0]), t, light_at)
            return a
        return Frame(cam, out, focus, 0.05, bg)
    return dur, n, f

@scene("bullet-time", "A burst of photos freezes in mid-air while the camera circles it; time resumes and they scatter outward.")
def bullet_time(lib):
    dur, n = 7.0, 42
    r = rnd(5); cards = []
    for i in range(n):
        d = norm([r.gauss(0, 1), r.gauss(0, 1) * 1.2, r.gauss(0, 1)]); rad = r.uniform(0.6, 3.0)
        cards.append((i, d, rad, (r.uniform(-65, 65), r.uniform(-40, 40), r.uniform(-90, 90)), r.uniform(0.7, 1.0),
                      (r.uniform(-400, 400), r.uniform(-300, 300))))
    L = norm([-0.4, 0.7, -0.6])
    T_GO = 4.7
    def f(t):
        ang = math.radians(lerp(-70, 55, ease_in_out_cubic(window(t, 0, T_GO + 0.3))) + 8 * window(t, T_GO, dur))
        R = lerp(8.0, 7.2, window(t, 0, T_GO))
        cam_pos = np.array([math.sin(ang) * R, 0.6 + math.sin(t * 0.7) * 0.3, -math.cos(ang) * R])
        cam = Camera(cam_pos, [0, 0, 0])
        go = window(t, T_GO, dur)
        burst = 1 + 1.7 * (1 - (1 - go) ** 2.4)
        out = []
        for i, d, rad, (yw, pt, rl), s, (sy_, sp_) in cards:
            frozen = rad * (1 + 0.01 * t)
            p = d * frozen * burst
            Rm = rot(yw + sy_ * 0.5 * go, pt + sp_ * 0.5 * go, rl)
            n_ = Rm @ np.array([0, 0, -1.0])
            lit = 0.35 + 0.75 * abs(float(n_ @ L))
            out.append(Card(i, p, Rm, s, shade=lit))
        flash = math.exp(-((t - T_GO) / 0.06) ** 2) * 0.35
        def bg():
            a = room_bg("bt", glow=(26, 24, 36))
            add_glow(a, W / 2, H / 2, 420, 420, (255, 245, 225), 18 + 120 * flash)
            return a
        return Frame(cam, out, float(np.linalg.norm(cam_pos)), 0.045, bg, flash)
    return dur, n, f

def layers_for(lib, idx):
    """(background, subject, foreground) RGBA layers for one photo."""
    if lib.has_photos:
        ph = lib.raw[idx].resize((SPR_W, SPR_H), Image.LANCZOS)
        bgl = ph.filter(ImageFilter.GaussianBlur(10)).convert("RGBA")
        m = Image.new("L", (SPR_W, SPR_H), 0)
        ImageDraw.Draw(m).ellipse((SPR_W * 0.18, SPR_H * 0.12, SPR_W * 0.82, SPR_H * 1.05), 255)
        sub = ph.convert("RGBA"); sub.putalpha(m.filter(ImageFilter.GaussianBlur(40)))
    else:
        combos = [(PURPLE, WHITE_BASE), (SKY, (0, 0, 0)), (ORANGE, WHITE_BASE), (GREEN, (0, 0, 0))]
        bgc, fig = combos[idx % len(combos)]
        g = Image.radial_gradient("L").resize((SPR_W * 2, SPR_H * 2)).crop((0, 0, SPR_W, SPR_H))
        bgl = Image.composite(Image.new("RGB", (SPR_W, SPR_H), bgc), Image.new("RGB", (SPR_W, SPR_H), tuple(min(255, c + 45) for c in bgc)), g).convert("RGBA")
        sub = Image.new("RGBA", (SPR_W, SPR_H), (0, 0, 0, 0)); d = ImageDraw.Draw(sub)
        w, h = SPR_W, SPR_H; cx = w / 2
        d.rounded_rectangle((cx - 0.38 * w, h * 0.66, cx + 0.38 * w, h * 1.3), radius=int(0.35 * w), fill=(*fig, 255))
        d.ellipse((cx - 0.2 * w, h * 0.25, cx + 0.2 * w, h * 0.25 + 0.45 * w), fill=(*fig, 255))
    fg = Image.new("RGBA", (SPR_W, SPR_H), (0, 0, 0, 0)); d = ImageDraw.Draw(fg); r = rnd(idx)
    for _ in range(14):
        x, y, rr = r.uniform(0, SPR_W), r.uniform(0, SPR_H), r.uniform(18, 70)
        col = r.choice([YELLOW, SKY, WHITE_BASE, GREEN])
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(*col, 150))
    fg = fg.filter(ImageFilter.GaussianBlur(6))
    return bgl, sub, fg

ARGS_PHOTOS = ""

@scene("through-the-photo", "The camera pushes into a photo, which splits into background, subject and foreground layers; it travels between them to a second photo waiting behind.")
def through_the_photo(lib):
    dur, n = 8.0, 2
    b, s, fg = layers_for(lib, 0)
    lib.add("L_bg", b); lib.add("L_sub", s); lib.add("L_fg", fg)
    T_FILL, T_END = 2.2, 7.0
    ZB, ZS, ZF, Z2 = 7.0, 2.4, 0.7, 11.5
    def f(t):
        out = []
        push = ease_in_cubic(window(t, 0.2, T_FILL)) * 0.9 + 0.1 * window(t, 0.2, T_FILL)
        if t < T_FILL:
            cz = lerp(-6.5, -1.0, push)
            cam = Camera([0, 0, cz], [0, 0, cz + 5])
            out.append(Card(0, [0, 0, 0], np.eye(3), 1.0, shade=0.95 + 0.05 * push, sharp=True))
            return Frame(cam, out, 5, 0.0, lambda: room_bg("ttp"))
        u = ease_in_out_cubic(window(t, T_FILL, T_END))
        cz = lerp(-1.0, 4.6, ease_in_out_cubic(window(t, T_FILL + 0.7, T_END)))
        side = math.sin(u * math.pi)
        cam = Camera([side * 1.5, side * -0.6, cz], [side * 0.5, side * -0.2, cz + 6])
        sep = ease_in_out_cubic(window(t, T_FILL, T_FILL + 1.4))
        zb, zs, zf = ZB * sep, ZS * sep, ZF * sep
        def plane(key, z, alpha=1.0, extra=1.0):
            scale = (z + 1.0) / 1.0          # same apparent size as the card at the moment it filled the frame
            return Card(key, [0, 0, z], np.eye(3), scale * 1.06 * extra, alpha=alpha, sharp=True)
        bg_a = 1 - ease_in_out_cubic(window(t, 5.0, 6.3))
        if bg_a > 0.01: out.append(plane("L_bg", zb, bg_a, 1.15))
        sub_a = clamp((zs - cz - 0.35) / 0.9) if sep > 0.5 else 1.0
        if sub_a > 0.01: out.append(plane("L_sub", zs, sub_a, 0.8))
        fg_a = clamp((zf - cz - 0.2) / 0.6) if sep > 0.5 else 1.0
        if fg_a > 0.01: out.append(plane("L_fg", zf, fg_a))
        reveal = window(t, 5.0, 6.5)
        if reveal > 0: out.append(Card(1, [0, 0.0, Z2], rot(math.sin(t) * 4, 0, math.sin(t * 0.7) * 2), 2.1, shade=0.2 + 0.85 * reveal))
        def bg():
            a = room_bg("ttp")
            add_glow(a, W / 2, H / 2, 420, 520, (255, 242, 220), 26 * reveal)
            return a
        return Frame(cam, out, 5, 0.0, bg)
    return dur, n, f

@scene("light-sweep", "In near darkness only card edges show; a narrow beam sweeps across, revealing each photo, and the last one turns fully into the light.")
def light_sweep(lib):
    dur, n = 7.5, 7
    xs = np.linspace(-6.6, 6.6, n)
    yaws = [30, -24, 32, -28, 26, -32, 42]
    T_END = 5.4
    def f(t):
        bx = lerp(-9.0, xs[-1], ease_in_out_cubic(window(t, 0.5, T_END)))
        cx = lerp(-5.0, xs[-1], ease_in_out_cubic(window(t, 0.0, T_END + 1.0)))
        cam = Camera([cx, 0.15, -2.0], [cx + 0.4, 0.0, 6])
        out = []
        for i, x in enumerate(xs):
            beam = math.exp(-((x - bx) / 0.9) ** 2)
            passed = 0.14 if bx > x + 1.0 else 0.0
            yaw = yaws[i]; lit = max(beam * 1.08, passed, 0.03)
            if i == n - 1:
                turn = ease_in_out_cubic(window(t, T_END - 0.8, T_END + 1.0)); yaw = lerp(yaw, 0, turn); lit = max(lit, turn * 1.05)
            out.append(Card(i, [x, (i % 2) * 0.15 - 0.05, 6 + (i % 3) * 0.35], rot(yaw, 0, (-1) ** i * 3), 1.9,
                            shade=lit, rim=0.6 * (1 - min(1, lit * 1.5)) + 0.04))
        def bg():
            a = room_bg("sweep", color=(4, 4, 7), glow=(10, 10, 16))
            pc = cam.to_cam(np.array([[bx, 6.0, 6.0], [bx, -6.0, 6.0]]))
            if (pc[:, 2] > 0.3).all():
                px, py = cam.project(pc); add_shaft(a, float(px[0]), float(px[1]), 80, 190, (255, 244, 220), 30)
            return a
        return Frame(cam, out, 8.0, 0.025, bg)
    return dur, n, f

@scene("reverse-explosion", "Photos scattered on the floor lift, spin and fly backward into a floating collage; the camera slowly pulls back to reveal it.")
def reverse_explosion(lib):
    dur, n = 8.0, 20
    r = rnd(21); floor = -2.6
    cols, rows = 5, 4
    specs = []
    for i in range(n):
        c, rw = i % cols, i // cols
        slot = np.array([(c - 2) * 1.12 + r.uniform(-0.15, 0.15), (1.5 - rw) * 1.3 + 0.6 + r.uniform(-0.15, 0.15), 4.0 + r.uniform(-0.3, 0.3)])
        start = np.array([r.uniform(-4.5, 4.5), floor + 0.01 * i, r.uniform(-0.5, 8.0)])
        specs.append(dict(i=i, slot=slot, start=start, srot=r.uniform(-180, 180), roll=r.uniform(-8, 8), t0=0.7 + r.uniform(0, 1.3),
                          spin=r.choice([-360, 360]), arc=r.uniform(1.5, 3.5)))
    def f(t):
        view = ease_in_out_cubic(window(t, 0.4, 3.4))
        pull = ease_in_out_cubic(window(t, 3.6, dur))
        cam_pos = np.array([0, lerp(3.4, 0.9, view), lerp(-4.5, -2.6, view) - pull * 6.0])
        look = np.array([0, lerp(floor, 0.9, view), lerp(3.0, 4.0, view)])
        cam = Camera(cam_pos, look)
        out = []
        for sp in specs:
            u = ease_out_cubic(window(t, sp["t0"], sp["t0"] + 1.6))
            p = sp["start"] + (sp["slot"] - sp["start"]) * u
            p = p + np.array([0, math.sin(u * math.pi) * sp["arc"], 0])
            pitch = lerp(90, 0, u); yaw = lerp(sp["srot"], 0, u); roll = lerp(sp["spin"], sp["roll"], u)
            fl = math.sin(t * 0.8 + sp["i"]) * 0.04 * u
            out.append(Card(sp["i"], p + np.array([0, fl, 0]), rot(yaw if u < 1 else 0, pitch, roll), 0.95,
                            shade=0.55 + 0.5 * u))
        focus = float(np.linalg.norm(np.array([0, 0.9, 4.0]) - cam_pos))
        def bg():
            a = room_bg("rev", glow=(24, 22, 34))
            fc = cam.to_cam(np.array([[0, floor, 3.5]]))
            if fc[0, 2] > 0.3:
                fx, fy = cam.project(fc); add_glow(a, float(fx[0]), float(fy[0]), 2600 / fc[0, 2], 700 / fc[0, 2], (255, 240, 210), 16)
            return a
        return Frame(cam, out, focus, 0.03, bg)
    return dur, n, f

@scene("photo-spiral", "Photos form a tall spiral; the camera rises through its centre, then the spiral opens into a ring of photos around the viewer.")
def photo_spiral(lib):
    dur, n = 8.5, 44
    r = rnd(9)
    helix = [(k, k * 0.55, r.uniform(2.2, 3.2), -9 + k * 0.6) for k in range(n)]
    T_OPEN = 5.6
    ring = {}
    for j, (k, *_) in enumerate(helix):
        tier = j % 2; a = (j // 2) / (n / 2) * 2 * math.pi
        ring[k] = (a, 3.0, 8.7 + (tier - 0.5) * 1.45)
    def f(t):
        cy = lerp(-12, 8.7, ease_in_out_cubic(window(t, 0, T_OPEN)))
        yaw = math.radians(10 + t * 20)
        pitch = math.radians(lerp(62, 0, ease_in_out_cubic(window(t, T_OPEN - 1.0, T_OPEN + 1.2))))
        d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
        cam = Camera([0, cy, 0], np.array([0, cy, 0]) + d, fov=82)
        out = []
        for k, th, rad, y in helix:
            o = ease_in_out_cubic(window(t, T_OPEN - 0.9 + (k % 8) * 0.06, T_OPEN + 1.0 + (k % 8) * 0.06))
            a2, r2, y2 = ring[k]
            a2 = a2 + round((th - a2) / (2 * math.pi)) * 2 * math.pi
            ang = lerp(th, a2, o); rr = lerp(rad, r2, o); yy = lerp(y, y2, o)
            p = np.array([math.sin(ang) * rr, yy, math.cos(ang) * rr])
            out.append(Card(k, p, rot(math.degrees(ang), lerp(-25, 0, o), math.sin(k) * 4 * (1 - o)), lerp(1.0, 0.9, o),
                            shade=0.45 + 0.55 * clamp(1 - abs(yy - cy) / 10) + 0.15 * o))
        def bg():
            return room_bg("spiral", glow=(24, 22, 36), cy=0.5)
        return Frame(cam, out, 3.0, 0.03, bg)
    return dur, n, f

@scene("one-photo-many", "A single photo floats close to the lens; as the camera pulls back hundreds more appear behind it, softening into the distance.")
def one_photo_many(lib):
    dur, n = 8.0, 12
    r = rnd(17)
    field = []
    for k in range(230):
        z = r.uniform(2.6, 46)
        spread = 0.45 * z + 2
        field.append((1 + k % (n - 1), np.array([r.uniform(-spread, spread), r.uniform(-spread * 1.4, spread * 1.4), z]),
                      (r.uniform(-25, 25), r.uniform(-20, 20), r.uniform(-15, 15)), r.uniform(0.8, 1.15), r.uniform(0, 6.28)))
    hero_z = 1.5
    def f(t):
        pull = ease_in_out_cubic(window(t, 0.3, dur - 0.4))
        cz = lerp(hero_z - 1.2, hero_z - 16, pull)
        cam = Camera([0, 0, cz], [0, 0, cz + 10])
        out = [Card(0, [0, 0, hero_z], rot(0, 0, math.sin(t * 0.5) * 2), 1.0, shade=1.05, sharp=True)]
        for i, p, (yw, pt, rl), s, ph in field:
            reveal = clamp((t - 0.4 - (p[2] / 46) * 3.5) / 1.4)
            if reveal <= 0: continue
            fog = 1 - 0.55 * clamp((p[2] - cz) / 50)
            out.append(Card(i, p + np.array([0, math.sin(t * 0.4 + ph) * 0.06, 0]), rot(yw, pt, rl), s,
                            shade=0.85 * fog, alpha=reveal))
        focus = hero_z - cz
        def bg():
            a = room_bg("many", glow=(30, 28, 44))
            add_glow(a, W / 2, H / 2, 600, 760, (255, 245, 225), 10 * pull)
            return a
        return Frame(cam, out, focus, 0.02 + 0.06 * pull, bg)
    return dur, n, f

@scene("photo-eclipse", "A dark-backed card turns in front of a glowing light with a bright rim, reveals its photo, and smaller photos drift out into a weightless orbit.")
def photo_eclipse(lib):
    dur, n = 8.0, 7
    T_TURN0, T_TURN1 = 0.6, 4.0
    def f(t):
        cam = Camera([0, 0.1, -5.2], [0, 0, 3])
        turn = ease_in_out_cubic(window(t, T_TURN0, T_TURN1))
        yaw = lerp(180, 360, turn)
        bob = math.sin(t * 0.8) * 0.06
        front_light = 0.12 + 0.95 * clamp((turn - 0.5) * 2)
        big = Card(0, [0, bob, 3.0], rot(yaw, math.sin(t * 0.5) * 4, 0), 2.6, shade=front_light, glow=1.0, rim=0.0)
        out = [big]
        emerge = window(t, T_TURN1 - 0.2, T_TURN1 + 1.4)
        for j in range(1, n):
            a = 2 * math.pi * j / (n - 1) + t * 0.25
            rx, rz = 2.7 * ease_out_cubic(emerge), 1.4 * ease_out_cubic(emerge)
            p = np.array([math.cos(a) * rx, math.sin(a * 2) * 0.35 * emerge + 0.15 * math.sin(j) + bob, 3.6 + math.sin(a) * rz])
            out.append(Card(j, p, rot(math.degrees(math.cos(a)) * -0.35 + 0 * a, 0, math.sin(t + j) * 6), 0.62,
                            shade=0.4 + 0.6 * emerge, alpha=clamp(emerge * 3), glow=0.4 * emerge))
        def bg():
            a = room_bg("eclipse", color=(4, 4, 7), glow=(12, 11, 18))
            add_glow(a, W / 2, H * 0.49, 420, 420, (255, 236, 190), 120)
            add_glow(a, W / 2, H * 0.49, 900, 900, (255, 220, 170), 28)
            return a
        return Frame(cam, out, 8.2, 0.025, bg)
    return dur, n, f

# ------------------------------------------------------------------ render
def compose(fr, lib):
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cards = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_cards(cards, fr.cam, fr.cards, lib, max(fr.focus, 0.3), fr.aperture, glow)
    bg = fr.bg() if fr.bg else room_bg("default")
    bg = np.clip(bg, 0, 255).astype(np.uint8)
    full = Image.fromarray(bg).convert("RGBA")
    full.alpha_composite(glow)
    full.alpha_composite(cards)
    if fr.flash > 0.01:
        full = Image.blend(full, Image.new("RGBA", (W, H), (255, 250, 240, 255)), fr.flash)
    return full.convert("RGB"), cards

def render(name, args):
    global ARGS_PHOTOS
    ARGS_PHOTOS = args.photos
    fn, _ = SCENES[name]
    lib = Library(args.photos, 12)
    dur, n, f = fn(lib)
    os.makedirs(args.out, exist_ok=True)
    if args.check:
        for s in [float(x) for x in args.check.split(",")]:
            rgb, _ = compose(f(s), lib); rgb.save(os.path.join(args.out, f"{name}-{s:05.2f}.png"))
        return
    base = os.path.join(args.out, name)
    p1 = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", base + ".mp4"], stdin=subprocess.PIPE)
    p2 = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0",
                           "-crf", "30", "-row-mt", "1", "-auto-alt-ref", "0", "-deadline", "realtime", "-cpu-used", "5",
                           base + "-transparent.webm"], stdin=subprocess.PIPE)
    for fr in range(int(round(dur * FPS))):
        rgb, cards = compose(f(fr / FPS), lib)
        p1.stdin.write(rgb.tobytes()); p2.stdin.write(cards.tobytes())
    p1.stdin.close(); p2.stdin.close()
    if p1.wait() or p2.wait(): sys.exit(f"ffmpeg failed for {name}")
    print(f"{name}: {base}.mp4, {base}-transparent.webm")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("animation")
    ap.add_argument("--photos", default=os.path.join(HERE, "photos"))
    ap.add_argument("--out", default="out")
    ap.add_argument("--check")
    args = ap.parse_args()
    if args.animation == "list":
        for k, (_, d) in SCENES.items(): print(f"{k:20s} {d}")
        return
    for nm in (list(SCENES) if args.animation == "all" else [args.animation]):
        if nm not in SCENES: sys.exit(f"unknown animation '{nm}'. Try: {', '.join(SCENES)}")
        render(nm, args)

if __name__ == "__main__":
    main()
