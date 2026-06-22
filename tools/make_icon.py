"""Generate the NOXLAB SEWIZARD Windows icon with only the standard library."""

from __future__ import annotations

import binascii
from pathlib import Path
import struct
import zlib


ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = ROOT / "assets" / "noxlab_sewizard.ico"
SHORTCUT_ICON_PATH = ROOT / "assets" / "noxlab_sewizard_wand.ico"
SIZE = 256


def main() -> None:
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    png = make_png(SIZE, SIZE)
    ico = make_ico(png)
    ICON_PATH.write_bytes(ico)
    SHORTCUT_ICON_PATH.write_bytes(ico)
    print(f"Icon written: {ICON_PATH}")
    print(f"Shortcut icon written: {SHORTCUT_ICON_PATH}")


def make_ico(png: bytes) -> bytes:
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    return header + entry + png


def make_png(width: int, height: int) -> bytes:
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)
        for x in range(width):
            pixels.extend(pixel_color(x, y, width, height))

    compressed = zlib.compress(bytes(pixels), 9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", compressed)
        + png_chunk(b"IEND", b"")
    )


def pixel_color(x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
    color = background_color(x, y, width, height)

    # Outer lab-style frame.
    if rounded_rect(x, y, 18, 18, 238, 238, 24):
        color = blend(color, (18, 9, 13, 255), 0.55)
    if rounded_rect_border(x, y, 18, 18, 238, 238, 24, 7):
        color = (190, 16, 28, 255)
    if rounded_rect_border(x, y, 31, 31, 225, 225, 18, 2):
        color = blend(color, (255, 64, 70, 255), 0.7)

    # Magic ring and arc glow inside the frame.
    if ring_arc(x, y, 128, 132, 58, 4, "upper"):
        color = (196, 22, 35, 255)
    if ring_arc(x, y, 128, 132, 42, 2, "lower"):
        color = blend(color, (255, 74, 80, 255), 0.85)
    if circle_border(x, y, 128, 132, 65, 1):
        color = blend(color, (120, 12, 22, 255), 0.55)

    # Wand and sparks for the SEWIZARD identity. No floppy/save-disk shape.
    if stroke_line(x, y, 76, 183, 181, 78, 9):
        color = (65, 13, 18, 255)
    if stroke_line(x, y, 83, 176, 188, 71, 6):
        color = (235, 222, 202, 255)
    if stroke_line(x, y, 91, 168, 192, 67, 2):
        color = (255, 67, 75, 255)
    if circle(x, y, 76, 183, 11):
        color = (230, 28, 40, 255)
    if circle(x, y, 76, 183, 5):
        color = (18, 18, 23, 255)
    if circle(x, y, 181, 78, 8):
        color = (255, 45, 54, 255)

    if star(x, y, 189, 69, 20):
        color = (255, 236, 210, 255)
    if star(x, y, 203, 112, 10) or star(x, y, 151, 52, 8) or star(x, y, 91, 105, 7):
        color = (255, 217, 194, 255)
    if star(x, y, 112, 192, 8) or star(x, y, 207, 174, 6):
        color = (255, 56, 64, 255)

    # Small magic motes.
    if circle(x, y, 107, 73, 4) or circle(x, y, 63, 137, 3) or circle(x, y, 167, 183, 3):
        color = (255, 63, 71, 255)

    return color


def background_color(x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
    cx = (x - width / 2) / (width / 2)
    cy = (y - height / 2) / (height / 2)
    distance = min(1.0, (cx * cx + cy * cy) ** 0.5)
    red_glow = int(58 * (1.0 - distance))
    color = (7 + red_glow, 8, 12, 255)
    if (x * 3 + y * 5) % 37 == 0 and 28 < x < 228 and 28 < y < 228:
        color = blend(color, (90, 20, 26, 255), 0.25)
    return color


def in_rect(x: int, y: int, left: int, top: int, right: int, bottom: int) -> bool:
    return left <= x <= right and top <= y <= bottom


def circle(x: int, y: int, cx: int, cy: int, radius: int) -> bool:
    return (x - cx) * (x - cx) + (y - cy) * (y - cy) <= radius * radius


def circle_border(x: int, y: int, cx: int, cy: int, radius: int, thickness: int) -> bool:
    distance_sq = (x - cx) * (x - cx) + (y - cy) * (y - cy)
    inner = max(0, radius - thickness)
    outer = radius + thickness
    return inner * inner <= distance_sq <= outer * outer


def ring_arc(x: int, y: int, cx: int, cy: int, radius: int, thickness: int, side: str) -> bool:
    if not circle_border(x, y, cx, cy, radius, thickness):
        return False
    if side == "upper":
        return y <= cy + 12 and not (x < cx - 44 and y > cy - 8)
    if side == "lower":
        return y >= cy - 8 and not (x > cx + 42 and y < cy + 10)
    return True


def rounded_rect(x: int, y: int, left: int, top: int, right: int, bottom: int, radius: int) -> bool:
    if not in_rect(x, y, left, top, right, bottom):
        return False
    if left + radius <= x <= right - radius or top + radius <= y <= bottom - radius:
        return True
    cx = left + radius if x < left + radius else right - radius
    cy = top + radius if y < top + radius else bottom - radius
    return circle(x, y, cx, cy, radius)


def rounded_rect_border(
    x: int,
    y: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
    radius: int,
    thickness: int,
) -> bool:
    return rounded_rect(x, y, left, top, right, bottom, radius) and not rounded_rect(
        x,
        y,
        left + thickness,
        top + thickness,
        right - thickness,
        bottom - thickness,
        max(0, radius - thickness),
    )


def stroke_line(x: int, y: int, x1: int, y1: int, x2: int, y2: int, width: int) -> bool:
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return False
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length_sq))
    px = x1 + t * dx
    py = y1 + t * dy
    return (x - px) * (x - px) + (y - py) * (y - py) <= width * width


def star(x: int, y: int, cx: int, cy: int, radius: int) -> bool:
    return (
        abs(x - cx) <= 1 and abs(y - cy) <= radius
        or abs(y - cy) <= 1 and abs(x - cx) <= radius
        or abs((x - cx) - (y - cy)) <= 1 and abs(x - cx) <= radius // 2
        or abs((x - cx) + (y - cy)) <= 1 and abs(x - cx) <= radius // 2
    )


def blend(base: tuple[int, int, int, int], top: tuple[int, int, int, int], amount: float) -> tuple[int, int, int, int]:
    return (
        int(base[0] * (1 - amount) + top[0] * amount),
        int(base[1] * (1 - amount) + top[1] * amount),
        int(base[2] * (1 - amount) + top[2] * amount),
        int(base[3] * (1 - amount) + top[3] * amount),
    )


def png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


if __name__ == "__main__":
    main()
