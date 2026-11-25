#!/usr/bin/env python3
"""news-image-20261125: sum up Wednesday 25 November 2026's world news
in one 1024x1024 image. Pure standard library: the canvas, the 5x7
bitmap font, the world map and the PNG encoder are all written here.
No network, no randomness, no time: the same input always produces
the same bytes at /output/entry.png.
"""
from __future__ import annotations

import binascii
import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 234)
INK = (20, 24, 34)
NAVY = (20, 33, 61)
NAVY2 = (28, 48, 88)
RED = (192, 57, 43)
GOLD = (212, 160, 23)
TEAL = (27, 122, 110)
CREAM = (255, 250, 238)
GREY = (108, 112, 122)
LIGHT = (226, 228, 232)
SEA = (16, 52, 84)
SEA2 = (23, 74, 110)
SKY = (12, 32, 58)
ORANGE = (232, 116, 28)
YELLOW = (244, 196, 48)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

REGION_COLORS = {
    "EUROPE": (46, 90, 172),
    "N. AMERICA": (192, 57, 43),
    "MIDDLE EAST": (183, 121, 31),
    "ASIA": (27, 122, 110),
    "AFRICA": (125, 60, 152),
    "SPORT": (46, 125, 50),
    "TECH": (55, 71, 79),
    "WORLD": (93, 64, 55),
}

# ---------------------------------------------------------------- canvas
px = bytearray(W * H * 3)


def set_px(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        px[i] = c[0]
        px[i + 1] = c[1]
        px[i + 2] = c[2]


def rect(x, y, w, h, c):
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(c) * (x1 - x0)
    for yy in range(y0, y1):
        i = (yy * W + x0) * 3
        px[i:i + (x1 - x0) * 3] = row


def hline(x, y, w, c):
    rect(x, y, w, 1, c)


def vline(x, y, h, c):
    rect(x, y, 1, h, c)


def line(x0, y0, x1, y1, c):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        set_px(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def disc(cx, cy, r, c):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            if (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) <= r * r:
                set_px(xx, yy, c)


def ring(cx, cy, r, c, t=2):
    for yy in range(cy - r - t, cy + r + t + 1):
        for xx in range(cx - r - t, cx + r + t + 1):
            d2 = (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy)
            if (r - t) * (r - t) <= d2 <= (r + t) * (r + t):
                set_px(xx, yy, c)


def ellipse(cx, cy, rx, ry, c):
    for yy in range(cy - ry, cy + ry + 1):
        for xx in range(cx - rx, cx + rx + 1):
            if ((xx - cx) * (xx - cx)) / float(rx * rx) + \
               ((yy - cy) * (yy - cy)) / float(ry * ry) <= 1.0:
                set_px(xx, yy, c)


def poly(points, c):
    """Scanline fill of a polygon given as [(x, y), ...]."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    for y in range(max(0, min(ys)), min(H, max(ys) + 1)):
        xs = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) * (x1 - x0) / float(y1 - y0))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(xs[i])), min(W, int(xs[i + 1]) + 1)):
                set_px(x, y, c)


def starburst(cx, cy, r_out, r_in, points, c):
    import math
    pts = []
    for i in range(points * 2):
        ang = 3.141592653589793 * i / points - 1.5707963267948966
        r = r_out if i % 2 == 0 else r_in
        pts.append((int(cx + r * math.cos(ang)), int(cy + r * math.sin(ang))))
    poly(pts, c)


# ---------------------------------------------------------------- 5x7 font
# Each glyph is 7 rows of 5 bits written as strings; '#' is on.
def _g(rows):
    return tuple(rows)


FONT = {
    "A": _g(("01110", "10001", "10001", "11111", "10001", "10001", "10001")),
    "B": _g(("11110", "10001", "10001", "11110", "10001", "10001", "11110")),
    "C": _g(("01110", "10001", "10000", "10000", "10000", "10001", "01110")),
    "D": _g(("11110", "10001", "10001", "10001", "10001", "10001", "11110")),
    "E": _g(("11111", "10000", "10000", "11110", "10000", "10000", "11111")),
    "F": _g(("11111", "10000", "10000", "11110", "10000", "10000", "10000")),
    "G": _g(("01110", "10001", "10000", "10111", "10001", "10001", "01111")),
    "H": _g(("10001", "10001", "10001", "11111", "10001", "10001", "10001")),
    "I": _g(("01110", "00100", "00100", "00100", "00100", "00100", "01110")),
    "J": _g(("00111", "00010", "00010", "00010", "00010", "10010", "01100")),
    "K": _g(("10001", "10010", "10100", "11000", "10100", "10010", "10001")),
    "L": _g(("10000", "10000", "10000", "10000", "10000", "10000", "11111")),
    "M": _g(("10001", "11011", "10101", "10101", "10001", "10001", "10001")),
    "N": _g(("10001", "11001", "10101", "10011", "10001", "10001", "10001")),
    "O": _g(("01110", "10001", "10001", "10001", "10001", "10001", "01110")),
    "P": _g(("11110", "10001", "10001", "11110", "10000", "10000", "10000")),
    "Q": _g(("01110", "10001", "10001", "10001", "10101", "10010", "01101")),
    "R": _g(("11110", "10001", "10001", "11110", "10100", "10010", "10001")),
    "S": _g(("01111", "10000", "10000", "01110", "00001", "00001", "11110")),
    "T": _g(("11111", "00100", "00100", "00100", "00100", "00100", "00100")),
    "U": _g(("10001", "10001", "10001", "10001", "10001", "10001", "01110")),
    "V": _g(("10001", "10001", "10001", "10001", "10001", "01010", "00100")),
    "W": _g(("10001", "10001", "10001", "10101", "10101", "11011", "10001")),
    "X": _g(("10001", "10001", "01010", "00100", "01010", "10001", "10001")),
    "Y": _g(("10001", "10001", "01010", "00100", "00100", "00100", "00100")),
    "Z": _g(("11111", "00001", "00010", "00100", "01000", "10000", "11111")),
    "0": _g(("01110", "10001", "10011", "10101", "11001", "10001", "01110")),
    "1": _g(("00100", "01100", "00100", "00100", "00100", "00100", "01110")),
    "2": _g(("01110", "10001", "00001", "00110", "01000", "10000", "11111")),
    "3": _g(("11111", "00010", "00100", "00010", "00001", "10001", "01110")),
    "4": _g(("00010", "00110", "01010", "10010", "11111", "00010", "00010")),
    "5": _g(("11111", "10000", "11110", "00001", "00001", "10001", "01110")),
    "6": _g(("00110", "01000", "10000", "11110", "10001", "10001", "01110")),
    "7": _g(("11111", "00001", "00010", "00100", "01000", "01000", "01000")),
    "8": _g(("01110", "10001", "10001", "01110", "10001", "10001", "01110")),
    "9": _g(("01110", "10001", "10001", "01111", "00001", "00010", "01100")),
    " ": _g(("00000", "00000", "00000", "00000", "00000", "00000", "00000")),
    ".": _g(("00000", "00000", "00000", "00000", "00000", "01100", "01100")),
    ",": _g(("00000", "00000", "00000", "00000", "01100", "00100", "01000")),
    ":": _g(("00000", "01100", "01100", "00000", "01100", "01100", "00000")),
    ";": _g(("00000", "01100", "01100", "00000", "01100", "00100", "01000")),
    "'": _g(("00100", "00100", "01000", "00000", "00000", "00000", "00000")),
    '"': _g(("01010", "01010", "00000", "00000", "00000", "00000", "00000")),
    "!": _g(("00100", "00100", "00100", "00100", "00100", "00000", "00100")),
    "?": _g(("01110", "10001", "00001", "00110", "00100", "00000", "00100")),
    "-": _g(("00000", "00000", "00000", "01110", "00000", "00000", "00000")),
    "/": _g(("00001", "00010", "00010", "00100", "01000", "01000", "10000")),
    "(": _g(("00010", "00100", "01000", "01000", "01000", "00100", "00010")),
    ")": _g(("01000", "00100", "00010", "00010", "00010", "00100", "01000")),
    "&": _g(("01100", "10010", "10100", "01000", "10101", "10010", "01101")),
    "%": _g(("11001", "11010", "00010", "00100", "01000", "01011", "10011")),
    "+": _g(("00000", "00100", "00100", "11111", "00100", "00100", "00000")),
    "=": _g(("00000", "00000", "11111", "00000", "11111", "00000", "00000")),
    "$": _g(("00100", "01111", "10100", "01110", "00101", "11110", "00100")),
    "*": _g(("00000", "10101", "01110", "11111", "01110", "10101", "00000")),
    "[": _g(("01110", "01000", "01000", "01000", "01000", "01000", "01110")),
    "]": _g(("01110", "00010", "00010", "00010", "00010", "00010", "01110")),
    "<": _g(("00010", "00100", "01000", "10000", "01000", "00100", "00010")),
    ">": _g(("01000", "00100", "00010", "00001", "00010", "00100", "01000")),
    "_": _g(("00000", "00000", "00000", "00000", "00000", "00000", "11111")),
    "#": _g(("01010", "01010", "11111", "01010", "11111", "01010", "01010")),
    "@": _g(("01110", "10001", "10111", "10101", "10110", "10000", "01110")),
    "|": _g(("00100", "00100", "00100", "00100", "00100", "00100", "00100")),
    "•": _g(("00000", "00000", "01110", "01110", "01110", "00000", "00000")),
}

BLANK = FONT[" "]


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(x, y, s, c, scale=2):
    s = s.upper()
    cx = x
    for ch in s:
        g = FONT.get(ch, BLANK)
        for r in range(7):
            row = g[r]
            for col in range(5):
                if row[col] == "1":
                    rect(cx + col * scale, y + r * scale, scale, scale, c)
        cx += 6 * scale
    return cx


def draw_text_centered(x0, x1, y, s, c, scale=2):
    w = text_width(s, scale)
    draw_text(x0 + max(0, (x1 - x0 - w) // 2), y, s, c, scale)


def wrap_text(s, max_w, scale):
    words = s.split(" ")
    lines = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_width(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_para(x, y, s, c, scale, max_w, leading):
    lines = wrap_text(s, max_w, scale)
    for ln in lines:
        draw_text(x, y, ln, c, scale)
        y += leading
    return y

# ---------------------------------------------------------------- world map
# Equirectangular land outline on a 96 x 40 cell grid (lon -180..180,
# lat 90..-60). Each entry: row -> list of (first_col, last_col) spans.
MAP_SPANS = {
    4: [(8, 28), (35, 40), (60, 90)],
    5: [(5, 30), (34, 41), (48, 52), (59, 92)],
    6: [(4, 31), (34, 40), (46, 54), (59, 93)],
    7: [(4, 32), (35, 39), (45, 55), (58, 94)],
    8: [(5, 32), (45, 56), (58, 94), (90, 92)],
    9: [(6, 31), (46, 57), (58, 93), (91, 93)],
    10: [(7, 30), (46, 58), (57, 92), (91, 92)],
    11: [(8, 28), (47, 58), (57, 90)],
    12: [(9, 26), (48, 56), (57, 89)],
    13: [(10, 24), (49, 54), (58, 88)],
    14: [(12, 22), (50, 53), (46, 56), (58, 87)],
    15: [(14, 20), (44, 58), (59, 86)],
    16: [(16, 19), (43, 59), (60, 85)],
    17: [(43, 60), (62, 84), (66, 70)],
    18: [(44, 60), (64, 82), (66, 70)],
    19: [(44, 59), (66, 81), (67, 69)],
    20: [(45, 58), (68, 80), (67, 69)],
    21: [(28, 36), (46, 57), (70, 78), (67, 69)],
    22: [(27, 37), (46, 56), (72, 76), (78, 88)],
    23: [(27, 38), (47, 55), (79, 87)],
    24: [(28, 38), (47, 54)],
    25: [(28, 37), (48, 54)],
    26: [(29, 36), (48, 53), (79, 88)],
    27: [(29, 35), (49, 53), (78, 89)],
    28: [(30, 34), (49, 52), (78, 89)],
    29: [(30, 34), (50, 52), (79, 88)],
    30: [(30, 33), (50, 52), (80, 87)],
    31: [(31, 33), (50, 51), (81, 86)],
    32: [(31, 32), (51, 51), (82, 85), (92, 93)],
    33: [(31, 32), (51, 51), (92, 93)],
    34: [(31, 32)],
    35: [(32, 32)],
    36: [(32, 32)],
    37: [(32, 32)],
}


def draw_map(mx, my, cw, ch, land, sea_c):
    rect(mx - 6, my - 6, 96 * cw + 12, 40 * ch + 12, sea_c)
    for row, spans in MAP_SPANS.items():
        for a, b in spans:
            rect(mx + a * cw, my + row * ch, (b - a + 1) * cw, ch, land)


def lonlat_to_xy(mx, my, cw, ch, lon, lat):
    col = (lon + 180.0) / 360.0 * 96.0
    row = (90.0 - lat) / 150.0 * 40.0
    return int(mx + col * cw), int(my + row * ch)


# ---------------------------------------------------------------- PNG encoder
def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)
    return out


def encode_png():
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += px[y * W * 3:(y + 1) * W * 3]
    comp = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += _chunk(b"IHDR", ihdr)
    data += _chunk(b"IDAT", comp)
    data += _chunk(b"IEND", b"")
    return data


# ---------------------------------------------------------------- illustrations
def draw_hero_ship(x, y, w, h):
    """Night sea: a cargo ship, a drone, and an orange blast."""
    rect(x, y, w, h, SKY)
    # stars
    for sx, sy in [(30, 18), (90, 30), (160, 12), (240, 26), (320, 14),
                   (400, 30), (470, 16), (540, 28), (590, 12), (120, 44),
                   (280, 48), (450, 46), (520, 44)]:
        set_px(x + sx, y + sy, WHITE)
        set_px(x + sx + 1, y + sy, WHITE)
    # moon
    disc(x + w - 70, y + 34, 16, CREAM)
    disc(x + w - 76, y + 30, 13, SKY)
    # sea
    rect(x, y + h - 78, w, 78, SEA)
    rect(x, y + h - 78, w, 3, SEA2)
    # distant shoreline glow
    rect(x, y + h - 78, w, 2, (70, 110, 150))
    # waves
    for wx in range(10, w - 20, 46):
        ellipse(x + wx, y + h - 52, 18, 4, (120, 170, 210))
        ellipse(x + wx + 22, y + h - 26, 18, 4, (90, 140, 180))
    # ship hull
    poly([(x + 120, y + h - 78), (x + 480, y + h - 78),
          (x + 450, y + h - 34), (x + 150, y + h - 34)], (52, 58, 68))
    rect(x + 130, y + h - 74, 340, 6, (70, 78, 90))
    # containers
    for i, cc in enumerate([(196, 90, 46), (150, 60, 90), (232, 116, 28)]):
        rect(x + 170 + i * 96, y + h - 118, 84, 40, cc)
        for k in range(1, 6):
            vline(x + 170 + i * 96 + k * 14, y + h - 118, 40, (0, 0, 0))
    # bridge tower
    rect(x + 452, y + h - 150, 34, 72, CREAM)
    for r in range(3):
        rect(x + 457, y + h - 142 + r * 16, 24, 8, NAVY)
    # funnel with smoke (kept inside the panel: panel top is y)
    rect(x + 420, y + h - 140, 22, 50, RED)
    disc(x + 412, y + h - 146, 7, (140, 140, 140))
    disc(x + 400, y + h - 156, 9, (160, 160, 160))
    # drone
    dx, dy = x + 330, y + 42
    rect(dx - 14, dy - 4, 28, 8, INK)
    disc(dx - 18, dy - 6, 5, GREY)
    disc(dx + 18, dy - 6, 5, GREY)
    disc(dx - 18, dy + 6, 5, GREY)
    disc(dx + 18, dy + 6, 5, GREY)
    line(dx - 18, dy - 6, dx + 18, dy + 6, GREY)
    line(dx + 18, dy - 6, dx - 18, dy + 6, GREY)
    # blast at the bow
    bx, by = x + 500, y + h - 110
    starburst(bx, by, 52, 22, 10, ORANGE)
    starburst(bx, by, 34, 14, 10, YELLOW)
    disc(bx, by, 12, WHITE)
    # caption strip
    rect(x, y + h - 22, w, 22, (0, 0, 0))
    draw_text(x + 10, y + h - 18, "A RUSSIAN CARGO SHIP IN THE GULF OF FINLAND, AFTER THE DRONE STRIKE",
              (220, 220, 220), 1)


def draw_thumb_cia(x, y, w, h):
    rect(x, y, w, h, NAVY)
    # capitol-style building
    rect(x + 14, y + h - 26, w - 28, 26, CREAM)
    for i in range(5):
        rect(x + 18 + i * 13, y + h - 52, 7, 28, CREAM)
    ellipse(x + w // 2, y + h - 52, 20, 10, CREAM)
    rect(x + w // 2 - 2, y + 12, 4, 14, CREAM)
    # warning triangle
    poly([(x + w - 26, y + 12), (x + w - 6, y + 12), (x + w - 16, y + 30)], RED)
    draw_text(x + w - 19, y + 16, "!", WHITE, 1)
    draw_text(x + 6, y + 6, "CIA", GOLD, 2)


def draw_thumb_chip(x, y, w, h):
    rect(x, y, w, h, (30, 34, 44))
    # chip body
    rect(x + 18, y + 18, 44, 44, (70, 78, 90))
    rect(x + 26, y + 26, 28, 28, TEAL)
    draw_text(x + 30, y + 34, "5G", WHITE, 2)
    for i in range(5):
        hline(x + 8, y + 24 + i * 9, 10, GOLD)
        hline(x + w - 18, y + 24 + i * 9, 10, GOLD)
        vline(x + 24 + i * 9, y + 8, 10, GOLD)
        vline(x + 24 + i * 9, y + h - 18, 10, GOLD)
    draw_text(x + 6, y + 6, "GUILTY", RED, 1)


def draw_thumb_tower(x, y, w, h):
    rect(x, y, w, h, (44, 30, 34))
    # skyline
    for bx, bw, bh in [(4, 12, 18), (20, 10, 26), (58, 12, 20)]:
        rect(x + bx, y + h - bh, bw, bh, (90, 70, 80))
    # tallest tower
    poly([(x + 30, y + h), (x + 34, y + 14), (x + 46, y + 14), (x + 50, y + h)],
         (200, 180, 150))
    rect(x + 38, y + 6, 4, 10, (200, 180, 150))
    for r in range(5):
        rect(x + 34, y + 24 + r * 12, 12, 5, (60, 40, 44))
    # impact flash at the top
    starburst(x + 40, y + 16, 16, 7, 8, ORANGE)
    disc(x + 40, y + 16, 5, YELLOW)
    draw_text(x + 6, y + 6, "RIYADH", WHITE, 1)

# ---------------------------------------------------------------- the news
HERO_KICKER = "EUROPE  |  UKRAINE WAR  |  GULF OF FINLAND"
HERO_HEAD = "UKRAINE SAYS IT HIT A RUSSIAN SHIP IN THE GULF OF FINLAND"
HERO_BODY = ("President Zelenskiy confirmed Ukraine hit a Russian cargo "
             "ship in the Gulf of Finland. Norway urged Kyiv to show "
             "caution.")
HERO_BYLINE = "KYIV / HELSINKI - REUTERS, TUESDAY"

RAIL = [
    ("N. AMERICA", "CIA AND SPY CHIEF HIT BY CYBERATTACK",
     "CNN reports a breach at the CIA and the spy chief's office, "
     "hitting unclassified data.",
     "thumb_cia"),
    ("TECH", "HUAWEI GUILTY OF STEALING TRADE SECRETS",
     "A New York jury convicted the Chinese telecom giant on 10 of 12 "
     "counts after a three-month trial.",
     "thumb_chip"),
    ("MIDDLE EAST", "HOUTHI DRONE HITS RIYADH TOWER, 11 HURT",
     "Saudi civil defence says eleven were wounded. The Saudi-led "
     "coalition condemned the attack on the capital.",
     "thumb_tower"),
]

# (region, headline) cards for the grid; headlines fit two lines at scale 2
GRID = [
    ("EUROPE", "NATO EARLY-WARNING PLANES FOR POLAND"),
    ("MIDDLE EAST", "TANKERS MINED IN STRAIT OF HORMUZ"),
    ("AFRICA", "WHO EVACUATES STAFF IN DR CONGO"),
    ("N. AMERICA", "GIULIANI GETS MEDAL OF FREEDOM"),
    ("N. AMERICA", "TURKEYS PARDONED FOR THANKSGIVING"),
    ("EUROPE", "EU SANCTIONS RUSSIA AGAIN"),
    ("MIDDLE EAST", "UN WARNS OVER GAZA AID CRISIS"),
    ("SPORT", "ENGLAND LEVEL T20I SERIES"),
    ("TECH", "GTA VI TOPS THE CHARTS"),
    ("ASIA", "BJP AND AKALI DAL REUNITE FOR PUNJAB"),
    ("ASIA", "NEPAL PM'S FIRST INDIA VISIT ENDS"),
    ("TECH", "DELL UP, NVIDIA DOWN ON AI"),
]

# short items, one line each at scale 1, 4 columns x 3 rows
TICKER = [
    "FORT HOOD GUNMAN SEEKS EXECUTION STAY",
    "SARKOZY CORRUPTION CASE GOES TO TRIAL",
    "IRAQ PM SEEKS CONTROL OF KURDISH OIL",
    "PUTIN: RETALIATION 'INEVITABLE'",
    "ANTHROPIC SHARES SLIDE BELOW IPO PRICE",
    "DAY AGAINST VIOLENCE AGAINST WOMEN",
    "ARMY TO DETONATE EXPLOSIVES IN IOWA",
    "VENEZUELA REPORTS $237.5BN PUBLIC DEBT",
    "U.S. AND QATAR TALK STRATEGIC TIES",
    "MAN UTD FURY OVER YORO RED CARD",
    "'IMPOSSIBLE' STAR SYSTEM FOUND",
    "FASTEST LIST A DOUBLE HUNDRED EVER",
]

# (number, lat, lon, label, display offset x, display offset y)
# Offsets unclutter the Europe / Middle East cluster; dots stay close
# to their true place on the stylised map.
MAP_DOTS = [
    (1, 59.5, 24.0, "GULF OF FINLAND - UKRAINE DRONE STRIKE", -16, -10),
    (2, 39.0, -77.0, "WASHINGTON - CIA CYBERATTACK", -16, 12),
    (3, 24.7, 46.7, "RIYADH - HOUTHI DRONE STRIKE", 12, 10),
    (4, 40.7, -74.0, "NEW YORK - HUAWEI VERDICT", 14, -10),
    (5, 26.5, 56.0, "STRAIT OF HORMUZ - TANKERS MINED", 16, -2),
    (6, 52.0, 21.0, "POLAND - NATO EARLY-WARNING PLANES", 10, -12),
    (7, 1.5, 30.0, "DR CONGO - EBOLA TEAMS EVACUATED", 0, 14),
    (8, 31.5, 34.5, "GAZA - UN WARNS OVER AID", -12, 12),
]

TICKER_STRIP = ("UKRAINE HITS RUSSIAN SHIP  •  CIA BREACH  •  HUAWEI GUILTY  •  "
                "RIYADH TOWER HIT")


def section_head(y, text):
    rect(16, y, 992, 3, RED)
    draw_text(16, y + 8, text, RED, 2)


def build():
    rect(0, 0, W, H, PAPER)

    # ---- masthead
    rect(0, 0, W, 100, NAVY)
    rect(0, 96, W, 4, RED)
    draw_text(24, 14, "THE WORLD", CREAM, 8)
    draw_text(24, 72, "IN ONE IMAGE", GOLD, 3)
    draw_text(560, 12, "WEDNESDAY", CREAM, 4)
    draw_text(560, 46, "25 NOVEMBER 2026", GOLD, 4)
    draw_text(560, 78, "THE DAY'S WORLD NEWS, IN ONE PICTURE", (200, 205, 220), 2)

    # ---- red ticker strip
    rect(0, 100, W, 22, RED)
    draw_text_centered(0, W, 104, TICKER_STRIP, WHITE, 2)

    # ---- hero (left)
    hx, hy, hw = 16, 132, 580
    draw_text(hx, hy, HERO_KICKER, RED, 2)
    draw_hero_ship(hx, hy + 22, hw, 170)
    y = hy + 204
    y = draw_para(hx, y, HERO_HEAD, INK, 3, hw, 26)
    y += 6
    y = draw_para(hx, y, HERO_BODY, (40, 44, 54), 2, hw, 19)
    y += 6
    draw_text(hx, y, HERO_BYLINE, GREY, 2)

    # ---- right rail
    rx, rw = 612, 396
    ry = 132
    draw_text(rx, ry, "ALSO MAKING NEWS", RED, 2)
    ry += 24
    thumbs = {"thumb_cia": draw_thumb_cia, "thumb_chip": draw_thumb_chip,
              "thumb_tower": draw_thumb_tower}
    for region, head, body, thumb in RAIL:
        rect(rx, ry, rw, 100, WHITE)
        rect(rx, ry, 5, 100, REGION_COLORS[region])
        thumbs[thumb](rx + 12, ry + 12, 76, 76)
        tx = rx + 100
        draw_text(tx, ry + 8, region, REGION_COLORS[region], 1)
        y2 = draw_para(tx, ry + 20, head, INK, 2, rw - 112, 18)
        draw_para(tx, y2 + 3, body, (60, 64, 74), 1, rw - 112, 12)
        ry += 105

    # ---- map section
    my = 478
    section_head(my, "THE WORLD AT A GLANCE - WHERE TODAY'S NEWS HAPPENED")
    map_x, map_y, cw, ch = 30, 512, 6, 4
    draw_map(map_x, map_y, cw, ch, TEAL, NAVY2)
    for num, lat, lon, _label, ox, oy in MAP_DOTS:
        dx, dy = lonlat_to_xy(map_x, map_y, cw, ch, lon, lat)
        dx += ox
        dy += oy
        disc(dx, dy, 9, RED)
        ring(dx, dy, 9, WHITE, 1)
        draw_text(dx - 3, dy - 4, str(num), WHITE, 1)
    # legend
    lx = 640
    draw_text(lx, 512, "ON THE MAP", RED, 2)
    ly = 536
    for num, _lat, _lon, label, _ox, _oy in MAP_DOTS:
        disc(lx + 8, ly + 5, 8, RED)
        draw_text(lx + 4, ly + 1, str(num), WHITE, 1)
        draw_text(lx + 26, ly + 2, label, INK, 1)
        ly += 20

    # ---- grid section
    gy = 694
    section_head(gy, "MORE FROM AROUND THE WORLD")
    gx, gw, gh, gap = 16, 239, 56, 12
    for i, (region, head) in enumerate(GRID):
        col = i % 4
        row = i // 4
        cx = gx + col * (gw + gap)
        cy = gy + 30 + row * (gh + 6)
        rect(cx, cy, gw, gh, WHITE)
        rect(cx, cy, gw, 4, REGION_COLORS[region])
        draw_text(cx + 8, cy + 10, region, REGION_COLORS[region], 1)
        draw_para(cx + 8, cy + 22, head, INK, 2, gw - 16, 15)

    # ---- also today ticker
    ty = 914
    draw_text(16, ty, "ALSO TODAY", RED, 2)
    rect(150, ty + 2, 858, 2, LIGHT)
    tcol_w = 248
    for i, item in enumerate(TICKER):
        col = i % 4
        row = i // 4
        tx = 16 + col * tcol_w
        tyy = ty + 22 + row * 15
        disc(tx + 3, tyy + 4, 3, RED)
        draw_text(tx + 12, tyy, item, (40, 44, 54), 1)

    # ---- footer
    rect(0, 1000, W, 24, NAVY)
    draw_text_centered(0, W, 1007,
                        "SOURCES: REUTERS - BBC - CNN - AFP - AP  |  ALL STORIES FIRST REPORTED "
                        "WEDNESDAY 25 NOVEMBER 2026", (200, 205, 220), 1)


def main():
    out_dir = os.environ.get("OUTPUT_DIR") or "/output"
    try:
        os.makedirs(out_dir, exist_ok=True)
        probe = os.path.join(out_dir, ".write-test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
    except OSError:
        out_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(out_dir, exist_ok=True)
    build()
    data = encode_png()
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    sys.stdout.write("wrote %s (%d bytes)\n" % (path, len(data)))


if __name__ == "__main__":
    main()
