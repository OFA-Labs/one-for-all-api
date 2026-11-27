"""Screenshots for the vision providers: masked, marked with numbers, scaled down, never written to disk."""
from __future__ import annotations

import numpy as np

from ..engine.base import RedactedImage
from ..harness.api import Harness
from .scene import Scene

MAX_WIDTH = 1600         # keeps one request small for the provider; coordinates are scaled back
BOX = (0, 200, 255)      # BGR: orange outline
LABEL_BG, LABEL_FG = (0, 0, 0), (255, 255, 255)

# 3×5 digits, one string per row, enough to number marks without a font dependency.
DIGITS = {
    "0": ("111", "101", "101", "101", "111"), "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"), "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"), "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"), "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"), "9": ("111", "101", "111", "001", "111"),
}


def _draw_number(img: np.ndarray, x: int, y: int, text: str, scale: int = 2) -> None:
    h, w = img.shape[:2]
    width = len(text) * 4 * scale + scale
    x0, y0, x1, y1 = max(0, x), max(0, y), min(w, x + width), min(h, y + 6 * scale + scale)
    if x1 <= x0 or y1 <= y0:
        return
    img[y0:y1, x0:x1, :3] = LABEL_BG
    for i, ch in enumerate(text):
        for r, row in enumerate(DIGITS[ch]):
            for c, bit in enumerate(row):
                if bit == "1":
                    px, py = x + scale + (i * 4 + c) * scale, y + scale + r * scale
                    img[max(0, py):min(h, py + scale), max(0, px):min(w, px + scale), :3] = LABEL_FG


def draw_marks(img: np.ndarray, scene: Scene, origin: tuple[int, int]) -> None:
    ox, oy = origin
    h, w = img.shape[:2]
    for m in scene.marks:
        l, t, r, b = m.bbox[0] - ox, m.bbox[1] - oy, m.bbox[2] - ox, m.bbox[3] - oy
        l, t, r, b = max(0, l), max(0, t), min(w - 1, r), min(h - 1, b)
        if r <= l or b <= t:
            continue
        img[t, l:r, :3] = BOX
        img[b, l:r, :3] = BOX
        img[t:b, l, :3] = BOX
        img[t:b, r, :3] = BOX
        _draw_number(img, l, max(0, t - 13), m.id[1:])


def look_image(h: Harness, scene: Scene, marked: bool = True) -> tuple[RedactedImage, float]:
    """Masked (and optionally numbered) capture of the scene's area. Returns the image and its scale factor."""
    left, top, right, bottom = scene.origin
    bgra, width, height = h.b.capture((left, top, right, bottom))
    boxes = [m.bbox for m in scene.marks if m.is_password or (m.hwnd, m.id) in h.filled_refs]
    img = np.frombuffer(bgra, dtype=np.uint8).reshape(height, width, 4).copy()
    if marked:
        draw_marks(img, scene, (left, top))
    step = max(1, -(-width // MAX_WIDTH))           # ceil: nearest-neighbour downscale keeps it dependency-free
    small = np.ascontiguousarray(img[::step, ::step])
    sh, sw = small.shape[:2]
    scaled = [(l // step, t // step, r // step, b // step) for l, t, r, b in
              ((b[0] - left, b[1] - top, b[2] - left, b[3] - top) for b in boxes)]
    image = h.redact_capture(small.tobytes(), sw, sh, (0, 0), scaled, f"{len(boxes)} regions masked, {len(scene.marks)} marks")
    return image, float(step)
