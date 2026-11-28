#!/usr/bin/env python3
"""SAT in 30 Seconds - scene-based reel engine. usage: python3 -I engine.py <reel_dir> stills|video"""
import math, subprocess, sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
HERE = os.path.abspath(sys.argv[1]); MODE = sys.argv[2]
sys.path.insert(0, HERE)
import cfg
SEG = HERE + "/seg"
INK = (10, 8, 24); CYAN = (40, 225, 255); VIOLET = (125, 95, 255); PINK = (255, 70, 165)
ORANGE = (255, 175, 60); GREEN = (60, 230, 140); YELLOW = (255, 225, 90); WHITE = (255, 255, 255); PAPER = (249, 248, 243)
COL = dict(CYAN=CYAN, PINK=PINK, ORANGE=ORANGE, GREEN=GREEN, YELLOW=YELLOW, WHITE=WHITE, VIOLET=VIOLET)
F_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
F_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
F_SERIF_I = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
F_HAND = "/usr/share/fonts/truetype/google-fonts/ofl/comicrelief/ComicRelief-Bold.ttf"
def font(p, s): return ImageFont.truetype(p, s)

def seg_len(i):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"{SEG}/s{i}.wav"], capture_output=True, text=True).stdout
    return float(out.strip())
GAP = 0.15
LEN = [seg_len(i) for i in range(1, 7)]
START = []; t = 0.15
for L in LEN:
    START.append(t); t += L + GAP
TOTAL = START[-1] + LEN[-1] + 0.7
NFRAMES = int(round(TOTAL * FPS))
S1, S2, S3, S4, S5, S6 = START
OFF = json.load(open(HERE + "/offs.json"))
C = cfg.build(START, OFF, LEN)
FAST = os.environ.get("FAST") == "1"
if FAST:
    C["card_in"] = -1.0; C["hook_end"] = START[2] - 0.2
    cfg.HOOK1 = getattr(cfg, "FAST_HOOK1", [("CAN YOU", "WHITE"), ("SOLVE IT?", "CYAN")]); cfg.HOOK2 = getattr(cfg, "FAST_HOOK2", [("PAUSE &", "PINK"), ("TRY IT!", "GREEN")])
C.setdefault("q_hi", 9999)
CARD_X0, CARD_X1, CARD_Y0, PAD = 50, 1030, 255, 44
PW = CARD_X1 - CARD_X0
PH = 640

def ease_out(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3
def ease_back(x):
    x = max(0.0, min(1.0, x)); c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def radial(w, h, cx, cy, r, color, strength):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** 2 * strength
    return a[..., None] * np.array(color, np.float32)[None, None, :]
def make_bg():
    base = np.zeros((H, W, 3), np.float32) + np.array(INK, np.float32)
    TH = {"violet": (VIOLET, PINK, CYAN, ORANGE), "teal": ((20, 160, 170), (40, 90, 220), (120, 255, 200), VIOLET),
          "sunset": ((230, 90, 60), (200, 40, 120), ORANGE, VIOLET), "ocean": ((30, 90, 230), (20, 170, 220), CYAN, PINK),
          "ember": ((200, 60, 30), ORANGE, (255, 200, 80), VIOLET), "forest": ((30, 150, 80), (20, 110, 150), GREEN, ORANGE),
          "crimson": ((190, 20, 60), VIOLET, PINK, ORANGE)}[getattr(cfg, "THEME", "violet")]
    for (cx, cy, r, col, s) in [(160, 330, 900, TH[0], 0.55), (980, 1500, 1000, TH[1], 0.40), (900, 260, 650, TH[2], 0.22), (200, 1700, 700, TH[3], 0.16)]:
        base += radial(W, H, cx, cy, r, col, s) * 0.55
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = 1 - 0.35 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) * 0.5
    base *= vig[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
def conic_ring_image(size):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    ang = (np.degrees(np.arctan2(yy - size / 2, xx - size / 2)) + 90) % 360
    stops = [(0, CYAN), (110, VIOLET), (205, PINK), (300, ORANGE), (360, CYAN)]
    out = np.zeros((size, size, 3), np.float32)
    for (a0, c0), (a1, c1) in zip(stops[:-1], stops[1:]):
        m = (ang >= a0) & (ang < a1)
        f = ((ang - a0) / (a1 - a0))[m][:, None]
        out[m] = np.array(c0, np.float32) * (1 - f) + np.array(c1, np.float32) * f
    return Image.fromarray(out.astype(np.uint8), "RGB")
def draw_multicolor_center(img, y, parts, f):
    d = ImageDraw.Draw(img)
    total = sum(d.textlength(p, font=f) for p, _ in parts); x = W / 2 - total / 2
    for p, col in parts:
        d.text((x, y), p, font=f, fill=col, anchor="ls"); x += d.textlength(p, font=f)

def parse_markup(s):
    words, cur, it, sup, buf = [], [], False, False, ""
    def flush():
        nonlocal buf
        if buf: cur.append((buf, it, sup)); buf = ""
    for ch in s:
        if ch == "*": flush(); it = not it
        elif ch == "^": flush(); sup = not sup
        elif ch == " ":
            flush()
            if cur: words.append(list(cur)); cur.clear()
        else: buf += ch
    flush()
    if cur: words.append(list(cur))
    return words
class MathFont:
    def __init__(self, size):
        self.n = font(F_SERIF, size); self.i = font(F_SERIF_I, size)
        self.sn = font(F_SERIF, int(size * 0.66)); self.si = font(F_SERIF_I, int(size * 0.66)); self.size = size
    def run_w(self, text, it, sup):
        f = (self.si if it else self.sn) if sup else (self.i if it else self.n); return f.getlength(text)
    def word_w(self, word): return sum(self.run_w(*r) for r in word)
    def draw_word(self, d, x, y, word, fill):
        for text, it, sup in word:
            f = (self.si if it else self.sn) if sup else (self.i if it else self.n)
            yy = y - (self.size * 0.36 if sup else 0)
            d.text((x, yy), text, font=f, fill=fill, anchor="ls"); x += f.getlength(text)
        return x
def wrap_words(mf, words, maxw):
    space = mf.n.getlength(" "); lines, cur, w = [], [], 0.0
    for wd in words:
        ww = mf.word_w(wd)
        if cur and w + space + ww > maxw: lines.append(cur); cur, w = [wd], ww
        else: w = w + (space if cur else 0) + ww; cur.append(wd)
    if cur: lines.append(cur)
    return lines

def build_card():
    FS = cfg.CARD_FS
    mf = MathFont(FS); lines, cflags = [], []
    for pi, para in enumerate(cfg.QUESTION.split("|")):
        ls = wrap_words(mf, parse_markup(para), PW - 2 * PAD); lines += ls; cflags += [pi == 0 and "|" in cfg.QUESTION] * len(ls)
    tab = getattr(cfg, "TABLE", None); tabo = (len(tab) * 46 + 24) if tab else 0
    line_h = int(FS * 1.48); q_h = len(lines) * line_h; box_h, gap = 70, 14; ch_h = (4 * box_h + 3 * gap) if cfg.CHOICES else box_h
    card_h = PAD + tabo + q_h + 26 + ch_h + PAD - 6; cw = PW; S = 2
    img = Image.new("RGBA", (cw * S, card_h * S), (0, 0, 0, 0))
    ring = conic_ring_image(max(cw, card_h) * S).resize((cw * S, card_h * S))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw * S - 1, card_h * S - 1), radius=44 * S, fill=255)
    img.paste(ring, (0, 0), mask)
    inner = Image.new("L", img.size, 0)
    ImageDraw.Draw(inner).rounded_rectangle((7 * S, 7 * S, cw * S - 8 * S, card_h * S - 8 * S), radius=38 * S, fill=255)
    img.paste(Image.new("RGBA", img.size, PAPER + (255,)), (0, 0), inner)
    d = ImageDraw.Draw(img); mfS = MathFont(FS * S); y = (PAD + tabo + int(FS * 0.95)) * S; geo = {}
    if tab:
        cwid, rh = 170, 46
        for ri, row in enumerate(tab):
            for ci, cell in enumerate(row):
                x0 = (PAD + ci * cwid) * S; y0 = (PAD + ri * rh) * S
                d.rectangle((x0, y0, x0 + cwid * S, y0 + rh * S), fill=(236, 236, 240) if ri == 0 else (255, 255, 255), outline=(30, 30, 30), width=2 * S)
                d.text((x0 + cwid * S // 2, y0 + rh * S // 2), cell, font=font(F_SERIF_I if ri == 0 else F_SERIF, 30 * S), fill=(22, 22, 30), anchor="mm")
    for li, ln in enumerate(lines):
        x = PAD * S
        if cflags[li]:
            tot = sum(mfS.word_w(w) for w in ln) + mfS.n.getlength(" ") * (len(ln) - 1); x = (cw * S - tot) / 2
        for wd in ln:
            x = mfS.draw_word(d, x, y, wd, (22, 22, 30)); x += mfS.n.getlength(" ")
        y += line_h * S
    by = (PAD + tabo + q_h + 26) * S; fch = font(F_SERIF, 40 * S); fl = font(F_B, 30 * S); geo["choice_boxes"] = {}
    if not cfg.CHOICES:
        d.rounded_rectangle((PAD * S, by, (cw - PAD) * S, by + box_h * S), radius=20 * S, outline=(70, 70, 85), width=3 * S, fill=(255, 255, 255))
        d.text(((PAD + 30) * S, by + box_h * S // 2 + 2 * S), "Answer:  ?", font=fch, fill=(90, 90, 105), anchor="lm")
        geo["choice_boxes"]["box"] = (PAD, by / S, cw - PAD, by / S + box_h)
    for letter, val in cfg.CHOICES:
        d.rounded_rectangle((PAD * S, by, (cw - PAD) * S, by + box_h * S), radius=20 * S, outline=(70, 70, 85), width=3 * S, fill=(255, 255, 255))
        cx, cy = (PAD + 46) * S, by + box_h * S // 2
        d.ellipse((cx - 22 * S, cy - 22 * S, cx + 22 * S, cy + 22 * S), outline=(70, 70, 85), width=3 * S)
        d.text((cx, cy + S), letter, font=fl, fill=(40, 40, 55), anchor="mm")
        if "*" in val or "^" in val:
            mfc = MathFont(40 * S); xx = (PAD + 100) * S
            for wd in parse_markup(val): xx = mfc.draw_word(d, xx, cy + 14 * S, wd, (22, 22, 30)) + mfc.n.getlength(" ")
        else: d.text(((PAD + 100) * S, cy + 2 * S), val, font=fch, fill=(22, 22, 30), anchor="lm")
        geo["choice_boxes"][letter] = (PAD, by / S, cw - PAD, by / S + box_h); by += (box_h + gap) * S
    return img.resize((cw, card_h), Image.LANCZOS), geo
def shadowed(card):
    pad = 60; sh = Image.new("RGBA", (card.width + 2 * pad, card.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", sh.size, 0)
    ImageDraw.Draw(a).rounded_rectangle((pad, pad + 18, pad + card.width, pad + card.height + 18), radius=44, fill=150)
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(26))); sh.paste(card, (pad, pad), card); return sh, pad

BG = make_bg(); CARD, GEO = build_card(); CARD_SH, SH_PAD = shadowed(CARD)
CARD_Y1 = CARD_Y0 + CARD.height; PANEL_Y0 = CARD_Y1 + 30; PANEL_Y1 = PANEL_Y0 + PH
HEADER = BG.copy(); draw_multicolor_center(HEADER, 150, [("SAT ", CYAN), ("IN ", WHITE), ("30 ", WHITE), ("SECONDS", ORANGE)], font(F_BLACK, 56))
RAINBOW_BAR = None
def rainbow_bar(w, h):
    arr = np.zeros((h, w, 3), np.float32); stops = [(0, CYAN), (0.35, VIOLET), (0.65, PINK), (1.0, ORANGE)]; xs = np.linspace(0, 1, w)
    for (a0, c0), (a1, c1) in zip(stops[:-1], stops[1:]):
        m = (xs >= a0) & (xs <= a1); f = ((xs[m] - a0) / (a1 - a0))[:, None]
        arr[:, m, :] = (np.array(c0) * (1 - f) + np.array(c1) * f)[None, :, :]
    return Image.fromarray(arr.astype(np.uint8), "RGB")
RAINBOW_BAR = rainbow_bar(900, 10); RING_IMG = conic_ring_image(1060)

def paste_progress(frame, t):
    d = ImageDraw.Draw(frame); x0, x1, y = 90, 990, 205
    d.rounded_rectangle((x0, y, x1, y + 10), radius=5, fill=(50, 45, 90)); frac = max(0.0, min(1.0, t / TOTAL))
    if frac > 0.01:
        w = int((x1 - x0) * frac); mask = Image.new("L", (w, 10), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, 9), radius=5, fill=255); frame.paste(RAINBOW_BAR.crop((0, 0, w, 10)), (x0, y), mask)

def hook_text(frame, t):
    p1, p2, end = 0.15, C["hook2"], C.get("hook_end", C["card_in"] + 0.25)
    if t >= end: return
    block, t0 = (cfg.HOOK1, p1) if t < p2 else (cfg.HOOK2, p2)
    f = font(F_BLACK, 104)
    for k, (s, cname) in enumerate(block):
        col = COL[cname]; tk = t - t0 - k * 0.16
        if tk < 0: continue
        sc = 0.7 + 0.3 * ease_back(tk / 0.35); alpha = min(1.0, tk / 0.15); w = int(f.getlength(s)) + 40
        tmp = Image.new("RGBA", (w, 180), (0, 0, 0, 0)); ImageDraw.Draw(tmp).text((20, 140), s, font=f, fill=col + (255,), anchor="ls")
        tmp2 = Image.alpha_composite(tmp.filter(ImageFilter.GaussianBlur(12)), tmp)
        tmp2 = tmp2.resize((max(1, int(tmp2.width * sc)), max(1, int(tmp2.height * sc))), Image.LANCZOS)
        a = tmp2.getchannel("A")
        if alpha < 1: a = a.point(lambda v: int(v * alpha))
        if t > end - 0.3 and t >= p2: fo = max(0.0, (end - t) / 0.3); a = a.point(lambda v: int(v * fo))
        tmp2.putalpha(a); cy = (PANEL_Y0 + 230 + k * 170) if FAST else (800 + k * 150)
        frame.paste(tmp2, (W // 2 - tmp2.width // 2, cy - tmp2.height // 2), tmp2)
def hook_extra(frame, t):
    if not FAST: return
    st = getattr(cfg, "HOOK_STYLE", "pop"); p2, end = C["hook2"], C["hook_end"]
    if st == "countdown" and p2 <= t < end:
        seg = (end - p2) / 3; k = min(2, int((t - p2) / seg)); n = 3 - k; lt = (t - p2 - k * seg) / seg
        f = font(F_BLACK, 230); s = str(n); col = [GREEN, YELLOW, PINK][k]
        tmp = Image.new("RGBA", (400, 320), (0, 0, 0, 0)); ImageDraw.Draw(tmp).text((200, 160), s, font=f, fill=col + (255,), anchor="mm")
        tmp = Image.alpha_composite(tmp.filter(ImageFilter.GaussianBlur(16)), tmp); sc = 1.35 - 0.35 * ease_out(min(1, lt / 0.3))
        tmp = tmp.resize((int(400 * sc), int(320 * sc)), Image.LANCZOS); a = tmp.getchannel("A").point(lambda v: int(v * max(0, 1 - max(0, lt - 0.75) / 0.25))); tmp.putalpha(a)
        frame.paste(tmp, (W // 2 - tmp.width // 2, PANEL_Y0 + 610 - tmp.height // 2), tmp)
    if st == "stamp":
        h1 = getattr(cfg, "STAMP_AT", "h2") == "h1"; t0 = 0.4 if h1 else C["hook2"] + 0.1; end = C["hook2"] if h1 else end
        if t0 <= t < end:
            q = ease_back(min(1, (t - t0) / 0.3)); txt = getattr(cfg, "STAMP", "TRAP!"); f = font(F_BLACK, 96)
            tw = int(f.getlength(txt)) + 80; st_img = Image.new("RGBA", (tw, 170), (0, 0, 0, 0)); d = ImageDraw.Draw(st_img)
            d.rounded_rectangle((6, 6, tw - 6, 164), radius=24, outline=(255, 60, 80, 255), width=12)
            d.text((tw // 2, 88), txt, font=f, fill=(255, 60, 80, 255), anchor="mm")
            sc = 2.2 - 1.2 * q; st_img = st_img.rotate(-12, expand=True, resample=Image.BICUBIC)
            st_img = st_img.resize((max(1, int(st_img.width * sc)), max(1, int(st_img.height * sc))), Image.LANCZOS)
            fo = 1 if t < end - 0.3 else max(0, (end - t) / 0.3); st_img.putalpha(st_img.getchannel("A").point(lambda v: int(v * min(1, q) * fo)))
            frame.paste(st_img, (W // 2 - st_img.width // 2, PANEL_Y0 + 600 - st_img.height // 2), st_img)
def hook_ring(frame, t):
    end = C["card_in"] + 0.25
    if FAST: return
    if t >= end: return
    prog = max(0.0, min(1.0, (t - 0.1) / (end - 0.1))); fade = 1.0 if t < end - 0.3 else max(0.0, (end - t) / 0.3)
    S = 2; size = 1060; mask = Image.new("L", (size * S, size * S), 0); pad = 40 * S
    ImageDraw.Draw(mask).arc((pad, pad, size * S - pad, size * S - pad), start=-90, end=-90 + 360 * prog, fill=255, width=34 * S)
    mask = mask.resize((size, size), Image.LANCZOS)
    glow = mask.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.6 * fade)); mask = mask.point(lambda v: int(v * fade))
    frame.paste(RING_IMG, (W // 2 - size // 2, 900 - size // 2), glow); frame.paste(RING_IMG, (W // 2 - size // 2, 900 - size // 2), mask)
def paste_card(frame, t):
    tin = C["card_in"]
    if t < tin: return
    p = ease_out((t - tin) / 0.55); y = CARD_Y0 - SH_PAD + int((1 - p) * 260); layer = CARD_SH
    if p < 1: layer = layer.copy(); layer.putalpha(layer.getchannel("A").point(lambda v: int(v * p)))
    frame.paste(layer, (CARD_X0 - SH_PAD, y), layer)
    if t >= C["ans"] and p >= 1:
        q = ease_out((t - C["ans"]) / 0.4); bx0, by0, bx1, by1 = GEO["choice_boxes"][cfg.ANS if cfg.CHOICES else "box"]
        x0, y0 = CARD_X0 + bx0, CARD_Y0 + by0; w, h = int(bx1 - bx0), int(by1 - by0); S = 2
        ov = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=20 * S, fill=GREEN + (int(90 * q),), outline=GREEN + (int(255 * q),), width=6 * S)
        if not cfg.CHOICES:
            d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=20 * S, fill=(185, 245, 208, int(255 * q)), outline=GREEN + (int(255 * q),), width=6 * S)
            d.text((30 * S, h * S // 2 + 2 * S), "Answer:  " + cfg.ANS_TEXT, font=font(F_XB, 40 * S), fill=(8, 90, 50, int(255 * q)), anchor="lm")
        cx, cy = (w - 60) * S, h * S // 2
        d.line([(cx - 18 * S, cy), (cx - 5 * S, cy + 14 * S), (cx + 20 * S, cy - 14 * S)], fill=(20, 140, 80, int(255 * q)), width=8 * S, joint="curve")
        ov = ov.resize((w, h), Image.LANCZOS); glow = ov.filter(ImageFilter.GaussianBlur(10))
        frame.paste(glow, (int(x0), int(y0)), glow); frame.paste(ov, (int(x0), int(y0)), ov)

# ---------------- scenes ----------------
HANDF = {"s": font(F_HAND, 58), "m": font(F_HAND, 70), "big": font(F_HAND, 88)}
def chip(layer, text, x, y, fill=YELLOW, fg=(40, 28, 0), size=44):
    d = ImageDraw.Draw(layer); fl = font(F_BLACK, size); tw = int(d.textlength(text, font=fl)) + 52
    d.rounded_rectangle((x, y, x + tw, y + int(size * 1.6)), radius=int(size * 0.8), fill=fill)
    d.text((x + tw // 2, y + int(size * 0.8) + 1), text, font=fl, fill=fg, anchor="mm")
def panel_base(label):
    S = 2; big = Image.new("RGBA", (PW * S, PH * S), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius=40 * S, fill=(22, 18, 52, 235), outline=(120, 100, 255, 160), width=3 * S)
    base = big.resize((PW, PH), Image.LANCZOS); chip(base, label, 44, 34); return base
def line_layer(text, fk):
    tmp = Image.new("L", (940, 140), 0); ImageDraw.Draw(tmp).text((0, 105), text, font=HANDF[fk], fill=255, anchor="ls")
    w = int(tmp.getbbox()[2] + 8); glow = tmp.filter(ImageFilter.GaussianBlur(7))
    return tmp.crop((0, 0, w, 140)), glow.crop((0, 0, w, 140)), w
def prep_text_scene(sc):
    sc["_base"] = panel_base(sc["label"]); n = len(sc["lines"]); sc["ys"] = [200 + i * 92 for i in range(n)]
    if sc["lines"][-1][2] == "big": sc["ys"][-1] += 30
    sc["_ll"] = [line_layer(l[0], l[2]) for l in sc["lines"]]
def render_text_scene(sc, t):
    layer = sc["_base"].copy()
    for i, (text, cname, fk, cue) in enumerate(sc["lines"]):
        if t < cue: continue
        p = (t - cue) / 0.7; prog = ease_out(p); mask, glow, w = sc["_ll"][i]; reveal = int(w * prog) + 1
        m = mask.copy(); m.paste(0, (reveal, 0, w, 140)); g = glow.copy(); g.paste(0, (reveal, 0, w, 140))
        colimg = Image.new("RGB", m.size, COL[cname]); y = sc["ys"][i] - 105 + int((1 - prog) * 10)
        layer.paste(colimg, (44, y), g.point(lambda v: int(v * 0.55))); layer.paste(colimg, (44, y), m)
        if p < 1: ImageDraw.Draw(layer).ellipse((44 + reveal - 7, y + 85 - 7, 44 + reveal + 7, y + 85 + 7), fill=(255, 255, 255, 255))
    if sc.get("badge") and t >= sc["badge"][1]:
        s = "ANSWER: " + sc["badge"][0]; f = font(F_BLACK, 50); sc_ = ease_back((t - sc["badge"][1]) / 0.45); tw = int(f.getlength(s)) + 60
        b = Image.new("RGBA", (tw, 90), (0, 0, 0, 0)); bd = ImageDraw.Draw(b)
        bd.rounded_rectangle((0, 0, tw - 1, 89), radius=30, fill=GREEN + (255,)); bd.text((tw // 2, 47), s, font=f, fill=(8, 40, 24), anchor="mm")
        b = b.resize((max(1, int(tw * sc_)), max(1, int(90 * sc_))), Image.LANCZOS)
        layer.paste(b, (PW - 50 - b.width, ((PH - 130) if sc.get("badge_low") else (sc["ys"][-1] - 62)) + (90 - b.height) // 2), b)
    if sc.get("tip") and t >= sc["tip"][1]:
        q = ease_out((t - sc["tip"][1]) / 0.35); tl = Image.new("RGBA", (PW, 100), (0, 0, 0, 0)); chip(tl, sc["tip"][0], 44, 8, fill=(255, 225, 90, 255), size=34)
        tl.putalpha(tl.getchannel("A").point(lambda v: int(v * q))); layer.paste(tl, (0, PH - 108), tl)
    return layer

# graph scene (generic function plot)
PX0, PX1, PY0, PY1 = 30, PW - 30, 120, PH - 28
G = {}
def gmap(x, y): return PX0 + (x - G["x0"]) / (G["x1"] - G["x0"]) * (PX1 - PX0), PY1 - (y - G["y0"]) / (G["y1"] - G["y0"]) * (PY1 - PY0)
def prep_graph_scene(sc):
    x0, x1, y0, y1 = sc["rng"]; ys = sc["ystep"]; G.update(x0=x0, x1=x1, y0=y0, y1=y1)
    S = 2; img = Image.new("RGBA", (PW * S, PH * S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, PW * S - 1, PH * S - 1), radius=40 * S, fill=(252, 252, 250, 255), outline=(120, 100, 255, 200), width=3 * S)
    gxs = list(range(math.ceil(x0), math.floor(x1) + 1)); gys = list(range(int(math.ceil(y0 / ys) * ys), int(y1) + 1, ys))
    for gx in gxs:
        x, _ = gmap(gx, 0); d.line([(x * S, PY0 * S), (x * S, PY1 * S)], fill=(226, 226, 226, 255), width=2 * S)
    for gy in gys:
        _, y = gmap(0, gy); d.line([(PX0 * S, y * S), (PX1 * S, y * S)], fill=(226, 226, 226, 255), width=2 * S)
    ax, ay = gmap(0, 0); d.line([(PX0 * S, ay * S), (PX1 * S, ay * S)], fill=(70, 70, 70, 255), width=3 * S); d.line([(ax * S, PY0 * S), (ax * S, PY1 * S)], fill=(70, 70, 70, 255), width=3 * S)
    fl = font(F_B, 21 * S)
    for gx in gxs:
        if gx == 0: continue
        x, _ = gmap(gx, 0); d.text((x * S, (ay + 8) * S), str(gx).replace("-", "\u2212"), font=fl, fill=(110, 110, 110, 255), anchor="mt")
    for gy in gys:
        if gy == 0: continue
        _, y = gmap(0, gy); d.text(((ax - 8) * S, y * S), str(gy).replace("-", "\u2212"), font=fl, fill=(110, 110, 110, 255), anchor="rm")
    base = img.resize((PW, PH), Image.LANCZOS); chip(base, sc["label"], 30, 30)
    ImageDraw.Draw(base).text((PW - 34, 74), sc["eq"], font=font(F_B, 30), fill=(199, 68, 64, 255), anchor="rm")
    sc["_base"] = base; xs = np.arange(x0, x1 + 1e-9, 0.02); sc["_pts"] = [(x, sc["fn"](x)) for x in xs]
def render_graph_scene(sc, t):
    layer = sc["_base"].copy(); S = 2; ov = Image.new("RGBA", (PW * S, PH * S), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    G.update(x0=sc["rng"][0], x1=sc["rng"][1], y0=sc["rng"][2], y1=sc["rng"][3]); GY0, GY1 = G["y0"], G["y1"]
    prog = max(0.0, min(1.0, (t - sc["curve0"]) / sc["curve_dur"])); xr = G["x0"] + prog * (G["x1"] - G["x0"]); seg = []
    def flush():
        if len(seg) > 1: d.line(seg, fill=(199, 68, 64, 255), width=7 * S, joint="curve")
        seg.clear()
    if prog > 0:
        for x, y in sc["_pts"]:
            if x > xr: break
            if GY0 <= y <= GY1: px, py = gmap(x, y); seg.append((px * S, py * S))
            else: flush()
        flush()
    layer.alpha_composite(ov.resize((PW, PH), Image.LANCZOS))
    dd = ImageDraw.Draw(layer)
    for dot in sc["dots"]:
        x, cue, dx = dot[:3]; yv = dot[3] if len(dot) > 3 else 0
        if t < cue: continue
        k = ease_back((t - cue) / 0.4); px, py = gmap(x, yv); r = 12 * max(0.1, k)
        dd.ellipse((px - r - 3, py - r - 3, px + r + 3, py + r + 3), fill=(255, 255, 255, 255)); dd.ellipse((px - r, py - r, px + r, py + r), fill=(60, 60, 60, 255))
        lab = "(%s, %s)" % (str(x).replace("-", "\u2212"), str(yv).replace("-", "\u2212")); fl = font(F_B, 28); tw = int(dd.textlength(lab, font=fl)) + 26; cx, cy = px + dx, py - 56
        dd.rounded_rectangle((cx - tw / 2, cy - 22, cx + tw / 2, cy + 22), radius=12, fill=(255, 255, 255, 255), outline=(120, 120, 120, 255), width=2)
        dd.text((cx, cy), lab, font=fl, fill=(40, 40, 40, 255), anchor="mm")
    return layer
# Desmos-style calculator scene
def prep_calc_scene(sc):
    S = 2; img = Image.new("RGBA", (PW * S, PH * S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, PW * S - 1, PH * S - 1), radius=40 * S, fill=(252, 252, 250, 255), outline=(120, 100, 255, 200), width=3 * S)
    base = img.resize((PW, PH), Image.LANCZOS); chip(base, sc["label"], 30, 22); sc["_base"] = base
    mf = MathFont(54); sc["_imgs"] = []
    for r in sc["rows"]:
        words = parse_markup(r["m"]); w = int(sum(mf.word_w(x) for x in words) + mf.n.getlength(" ") * (len(words) - 1)) + 12
        im = Image.new("RGBA", (w, 70), (0, 0, 0, 0)); dd = ImageDraw.Draw(im); x = 0
        for wd in words: x = mf.draw_word(dd, x, 56, wd, (25, 25, 30, 255)) + mf.n.getlength(" ")
        sc["_imgs"].append(im)
def _mtext(layer, x, y, markup, size, fill):
    mf = MathFont(size); dd = ImageDraw.Draw(layer)
    for wd in parse_markup(markup): x = mf.draw_word(dd, x, y, wd, fill) + mf.n.getlength(" ")
def render_calc_scene(sc, t):
    layer = sc["_base"].copy(); dd = ImageDraw.Draw(layer); cols = [(199, 68, 64), (45, 112, 179), (130, 130, 130)]
    sl = sc.get("slider")
    if sl and sl[0] <= t < sl[1]:
        top = 182; q = ease_out((t - sl[0]) / 0.3); pulse = 0.5 + 0.5 * math.sin((t - sl[0]) * 7)
        dd.rectangle((0, top, PW, top + 82), fill=(255, 246, 214, 255)); dd.line([(0, top + 82), (PW, top + 82)], fill=(228, 228, 228, 255), width=2)
        dd.ellipse((24, top + 20, 68, top + 64), fill=(130, 130, 130, 255)); dd.polygon([(40, top + 31), (40, top + 53), (58, top + 42)], fill=(255, 255, 255, 255))
        _mtext(layer, 84, top + 56, "*a* = 1", 48, (25, 25, 30, 255))
        dd.line([(300, top + 44), (PW - 300, top + 44)], fill=(170, 170, 170, 255), width=6); dd.ellipse((520, top + 32, 544, top + 56), fill=(45, 112, 179, 255))
        cx, cy = PW - 80, top + 41; rr = 30 + int(8 * pulse)
        dd.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 90, 90, 255), width=5)
        dd.line([(cx - 14, cy - 14), (cx + 14, cy + 14)], fill=(90, 90, 90, 255), width=7); dd.line([(cx - 14, cy + 14), (cx + 14, cy - 14)], fill=(90, 90, 90, 255), width=7)
        dd.text((PW - 190, top + 41), "DELETE", font=font(F_BLACK, 26), fill=(200, 40, 40, 255), anchor="rm")
    for i, (r, im) in enumerate(zip(sc["rows"], sc["_imgs"])):
        if t < r["cue"]: continue
        top = 100 + 82 * i; dd.line([(0, top + 82), (PW, top + 82)], fill=(228, 228, 228, 255), width=2)
        dd.ellipse((24, top + 20, 68, top + 64), fill=cols[i] + (255,))
        prog = ease_out((t - r["cue"]) / r.get("dur", 1.3)); w = max(1, int(im.width * prog)); layer.paste(im.crop((0, 0, w, 70)), (84, top + 4), im.crop((0, 0, w, 70)))
    if t >= sc["pcue"]:
        q = ease_out((t - sc["pcue"]) / 0.4); ov = Image.new("RGBA", (PW, 150), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.text((84, 8), "REGRESSION PARAMETERS", font=font(F_B, 20), fill=(110, 110, 110, 255), anchor="lt")
        if t >= sc["ccue"]:
            k = ease_back((t - sc["ccue"]) / 0.4); hy = sc.get("hl_y", 94); od.rounded_rectangle((70, hy, 70 + int(sc.get("hl_w", 330) * k), hy + 48), radius=12, fill=(255, 232, 140, 255))
        for pm, px, py in sc.get("params", [("*a* = \u22123", 84, 66), ("*b* = 60", 390, 66), ("*c* = \u2212294", 84, 132)]): _mtext(ov, px, py, pm, 48, (25, 25, 30, 255))
        ov.putalpha(ov.getchannel("A").point(lambda v: int(v * q))); layer.paste(ov, (0, 350), ov)
    if t >= sc["r4cue"]:
        top = 500; dd.line([(0, top), (PW, top)], fill=(228, 228, 228, 255), width=2); dd.ellipse((24, top + 14, 68, top + 58), fill=(130, 130, 130, 255))
        prog = ease_out((t - sc["r4cue"]) / 0.6); RW = sc.get("r4w", 300); tmp = Image.new("RGBA", (RW, 70), (0, 0, 0, 0)); _mtext(tmp, 0, 52, sc.get("r4m", "*f*(0)"), sc.get("r4fs", 54), (25, 25, 30, 255))
        w = max(1, int(RW * prog)); layer.paste(tmp.crop((0, 0, w, 70)), (84, top - 2), tmp.crop((0, 0, w, 70)))
        if t >= sc["res"]:
            k = ease_back((t - sc["res"]) / 0.4); bw = int(sc.get("res_w", 190) * k); good = t >= sc["res"]
            dd.rounded_rectangle((PW - 60 - bw, top + 10, PW - 60, top + 62), radius=12, fill=(185, 245, 208, 255), outline=GREEN + (255,), width=4)
            if k > 0.8: dd.text((PW - 60 - sc.get("res_w", 190) // 2, top + 36), sc.get("res_t", "\u2212294"), font=font(F_B, 36), fill=(8, 90, 50, 255), anchor="mm")
            if sc.get("res_eq", True): dd.text((PW - 270, top + 36), "=", font=font(F_B, 40), fill=(90, 90, 90, 255), anchor="mm")
    return layer

def prep_shots_scene(sc):
    sc["_imgs"] = {}
    for k in sc["keys"]:
        p = k["img"]
        if p not in sc["_imgs"]: sc["_imgs"][p] = Image.open(p).convert("RGB")
    sc["_ph"] = sc.get("bottom", PANEL_Y0 + PH) - PANEL_Y0; ph = sc["_ph"]
    m = Image.new("L", (PW * 2, ph * 2), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, PW * 2 - 1, ph * 2 - 1), radius=36 * 2, fill=255)
    sc["_mask"] = m.resize((PW, ph), Image.LANCZOS)
def _view(sc, img, crop):
    x0, y0, x1, y1 = crop; src = sc["_imgs"][img]
    ph = sc["_ph"]; cw, ch = x1 - x0, y1 - y0; s = min(PW / cw, (ph - 110) / ch)
    vw, vh = PW / s, ph / s; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cy = cy + 55 / s; box = (cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2)
    out = src.transform((PW, ph), Image.EXTENT, box, Image.BICUBIC, fillcolor=(255, 255, 255)).filter(ImageFilter.UnsharpMask(1.2, 60, 2))
    return out, box
def render_shots_scene(sc, t):
    keys = sc["keys"]; i = max([j for j, k in enumerate(keys) if k["t"] <= t] or [0]); k = keys[i]; pk = keys[i - 1] if i > 0 else k
    u = ease_out(min(1, max(0, (t - k["t"]) / 0.7))) if i > 0 else 1
    crop = tuple(a + (b - a) * u for a, b in zip(pk["crop"], k["crop"]))
    cur, box = _view(sc, k["img"], crop)
    if k["img"] != pk["img"] and t - k["t"] < 0.35:
        prev, _ = _view(sc, pk["img"], crop); cur = Image.blend(prev, cur, max(0, (t - k["t"]) / 0.35))
    lay = cur.convert("RGBA"); d = ImageDraw.Draw(lay)
    sx = PW / (box[2] - box[0]); sy = sc["_ph"] / (box[3] - box[1])
    for h in sc.get("hl", []):
        if h["t0"] <= t < h["t1"]:
            q = ease_back(min(1, (t - h["t0"]) / 0.35)); x0, y0, x1, y1 = h["rect"]
            X0, Y0, X1, Y1 = (x0 - box[0]) * sx, (y0 - box[1]) * sy, (x1 - box[0]) * sx, (y1 - box[1]) * sy
            cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2; hw, hh = (X1 - X0) / 2 * (0.6 + 0.4 * q) + 10, (Y1 - Y0) / 2 * (0.6 + 0.4 * q) + 10
            pulse = 0.5 + 0.5 * math.sin((t - h["t0"]) * 6)
            d.rounded_rectangle((cx - hw, cy - hh, cx + hw, cy + hh), radius=14, outline=h.get("col", (255, 180, 0)) + (255,), width=int(6 + 3 * pulse))
    chip(lay, k.get("label", "REAL DESMOS"), 24, sc["_ph"] - 100, fill=(25, 25, 30), fg=YELLOW, size=38)
    lay.putalpha(sc["_mask"]); return lay
SCENE_PREP = {"shots": prep_shots_scene, "text": prep_text_scene, "graph": prep_graph_scene, "calc": prep_calc_scene}
SCENE_RENDER = {"shots": render_shots_scene, "text": render_text_scene, "graph": render_graph_scene, "calc": render_calc_scene}
for sc in C["scenes"]:
    SCENE_PREP[sc["kind"]](sc)

def scene_layer(sc, t):
    f = min(1.0, (t - sc["t0"]) / 0.25, (sc["t1"] - t) / 0.25)
    if f <= 0: return None
    lay = SCENE_RENDER[sc["kind"]](sc, t)
    if f < 1: lay.putalpha(lay.getchannel("A").point(lambda v: int(v * f)))
    return lay
import random
_rnd = random.Random(7)
CONF = [(_rnd.uniform(-1, 1), _rnd.uniform(0.5, 1.6), _rnd.uniform(-0.35, 0.35), _rnd.choice([CYAN, PINK, ORANGE, GREEN, YELLOW, VIOLET, WHITE]), _rnd.uniform(10, 24), _rnd.uniform(0, 6.28)) for _ in range(110)]
def paste_burst(frame, t):
    ta = t - C["ans"]
    if ta < 0 or ta > 2.2: return
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    cx, cy = W // 2, CARD_Y0 + CARD.height - 60
    for k in range(2):
        r = int((ta - 0.08 * k) * 1500)
        if r > 0: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, int(max(0, 1 - ta / 0.7) * 200)), width=14 - 5 * k)
    for vx, vy, sk, col, sz, ph in CONF:
        x = cx + vx * 900 * ease_out(ta / 1.1) + sk * 200; y = cy - vy * 900 * ease_out(ta / 0.55) + 1500 * max(0, ta - 0.3) ** 2 * 0.5 + 60
        a = int(255 * min(1, max(0, (2.2 - ta) / 0.7))); w2 = sz * (0.3 + abs(math.cos(ta * 9 + ph)))
        d.rectangle((x - w2, y - sz / 2, x + w2, y + sz / 2), fill=col + (a,))
    frame.alpha_composite(ov) if frame.mode == "RGBA" else frame.paste(ov, (0, 0), ov)
    if ta < 0.3:
        fl = Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - ta / 0.3)))); frame.paste(fl, (0, 0), fl)
def paste_cta(frame, t):
    if t < C["cta"]: return
    p = ease_out((t - C["cta"]) / 0.4); ov = Image.new("RGBA", (W, 330), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.rounded_rectangle((50, 0, W - 50, 300), radius=44, fill=(14, 10, 36, int(245 * p)), outline=(255, 70, 165, int(255 * p)), width=5)
    f1, f2 = font(F_BLACK, 66), font(F_XB, 44); tmp = Image.new("RGBA", ov.size, (0, 0, 0, 0)); td = ImageDraw.Draw(tmp)
    parts = [("FOLLOW ", WHITE), ("@sat30.uz", CYAN)]; tw = sum(td.textlength(s, font=f1) for s, _ in parts); x = W / 2 - tw / 2
    for s, col in parts: td.text((x, 120), s, font=f1, fill=col + (255,), anchor="ls"); x += td.textlength(s, font=f1)
    td.text((W / 2, 205), "A NEW SAT LESSON EVERY DAY", font=f2, fill=ORANGE + (255,), anchor="mm")
    td.text((W / 2, 262), "sat-platform.onrender.com", font=font(F_B, 36), fill=(200, 195, 235, 255), anchor="mm")
    tmp.putalpha(tmp.getchannel("A").point(lambda v: int(v * p))); ov = Image.alpha_composite(ov, tmp)
    frame.paste(ov, (0, PANEL_Y0 + 70 + int((1 - p) * 80)), ov)
def render(t):
    frame = HEADER.copy(); hook_ring(frame, t); hook_text(frame, t); paste_card(frame, t); hook_extra(frame, t)
    for sc in C["scenes"]:
        lay = scene_layer(sc, t)
        if lay is not None: frame.paste(lay, (CARD_X0, PANEL_Y0), lay)
    paste_burst(frame, t); paste_cta(frame, t); paste_progress(frame, t)
    if t > TOTAL - 0.4: frame = Image.blend(Image.new("RGB", frame.size, INK), frame, max(0.0, (TOTAL - t) / 0.4))
    return frame
def build_audio(path):
    inputs, filt, labels = [], [], []
    for i in range(6):
        inputs += ["-i", f"{SEG}/s{i + 1}.wav"]; ms = int(START[i] * 1000)
        filt.append(f"[{i}:a]aresample=44100,highpass=f=70,adelay={ms}|{ms}[a{i}]"); labels.append(f"[a{i}]")
    sfx = []
    def add(src, at, vol):
        i = 6 + len(sfx); inputs.extend(["-f", "lavfi", "-i", src]); ms = int(max(0, at) * 1000)
        filt.append(f"[{i}:a]volume={vol},adelay={ms}|{ms}[x{len(sfx)}]"); sfx.append(f"[x{len(sfx)}]")
    A = C["ans"]
    for sc in C["scenes"]:
        add("anoisesrc=d=0.35:c=pink:a=0.5,highpass=f=500,afade=t=in:d=0.15,afade=t=out:st=0.15:d=0.2", sc["t0"], 0.35)
    add("aevalsrc='0.6*sin(2*PI*(300*t+700*t*t))':d=0.7,afade=t=in:d=0.3", A - 0.7, 0.18)
    add("sine=f=60:d=0.5,afade=t=out:st=0.05:d=0.45", A, 0.9)
    add("aevalsrc='0.5*sin(2*PI*1046*t)+0.35*sin(2*PI*1568*t)+0.25*sin(2*PI*2093*t)':d=1.2,afade=t=out:st=0.05:d=1.15", A + 0.05, 0.35)
    add("anoisesrc=d=0.8:c=white:a=0.5,highpass=f=3000,afade=t=out:st=0.05:d=0.75", A, 0.25)
    n = 6 + len(sfx)
    fg = ";".join(filt) + ";" + "".join(labels) + "".join(sfx) + f"amix=inputs={n}:normalize=0,apad=whole_dur={TOTAL:.3f},atrim=0:{TOTAL:.3f},loudnorm=I=-15:TP=-1.5:LRA=7[out]"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", fg, "-map", "[out]", "-ac", "2", "-ar", "44100", path], check=True)
if __name__ == "__main__":
    print("timeline", [round(s, 2) for s in START], "total", round(TOTAL, 2))
    if MODE == "stills":
        if os.environ.get("AT"): C["still_times"] = [float(x) if x[0] != "h" else (C["hook2"] + float(x[1:])) for x in os.environ["AT"].split(",")]
        os.makedirs(HERE + "/stills", exist_ok=True)
        for f in os.listdir(HERE + "/stills"): os.remove(HERE + "/stills/" + f)
        for i, tt in enumerate(C["still_times"]): render(tt).save(f"{HERE}/stills/s{i:02d}_{tt:05.2f}.png")
    else:
        build_audio(HERE + "/voice_mix.wav"); out = f"{HERE}/sat30_{os.path.basename(HERE)}.mp4"
        p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", HERE + "/voice_mix.wav",
                              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        for n in range(NFRAMES):
            p.stdin.write(render(n / FPS).tobytes())
            if n % 200 == 0: print("frame", n, "/", NFRAMES, flush=True)
        p.stdin.close(); p.wait(); print("done", out)
