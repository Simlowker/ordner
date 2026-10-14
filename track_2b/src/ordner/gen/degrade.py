"""Phone-photo style degradations, levels 0 (clean) to 3 (hard), deterministic per key."""

import hashlib
import io

import numpy as np
from PIL import Image, ImageFilter

# per level: (rotation deg, perspective frac, blur px, jpeg q, contrast, brightness, noise sigma, shading)
LEVELS = {
    1: dict(rot=(0.3, 1.2), persp=(0.003, 0.01), blur=(0.3, 0.6), jpeg=(70, 85), contrast=(0.9, 1.0),
            bright=(-8, 8), noise=(2, 4), shade=(0.0, 0.08)),
    2: dict(rot=(1.0, 3.0), persp=(0.01, 0.025), blur=(0.7, 1.1), jpeg=(45, 65), contrast=(0.8, 0.95),
            bright=(-15, 15), noise=(4, 8), shade=(0.05, 0.15)),
    3: dict(rot=(2.5, 5.0), persp=(0.025, 0.045), blur=(1.1, 1.6), jpeg=(25, 40), contrast=(0.65, 0.85),
            bright=(-25, 20), noise=(8, 12), shade=(0.15, 0.3)),
}

PAD = {1: 0.03, 2: 0.06, 3: 0.10}


def _rng(key):
    return np.random.default_rng(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little"))


def _perspective_coeffs(src, dst):
    a = []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    b = np.array(src, dtype=float).reshape(8)
    return np.linalg.solve(np.array(a, dtype=float), b).tolist()


def degrade(img, level, key):
    """img: PIL 'L' image. Returns a new 'L' image."""
    if level == 0:
        return img.copy()
    p, r = LEVELS[level], _rng(key)
    u = lambda k: float(r.uniform(*p[k]))  # noqa: E731
    bg = int(r.integers(70, 200)) if level >= 2 else 255
    pad = int(max(img.size) * PAD[level])  # sheet stays in frame, like a photo with background around it
    framed = Image.new("L", (img.width + 2 * pad, img.height + 2 * pad), bg)
    framed.paste(img, (pad, pad))
    img = framed
    w, h = img.size

    f = u("persp")
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [(x + r.uniform(-f, f) * w, y + r.uniform(-f, f) * h) for x, y in src]
    img = img.transform((w, h), Image.PERSPECTIVE, _perspective_coeffs(src, dst), Image.BICUBIC, fillcolor=bg)
    img = img.rotate(u("rot") * r.choice([-1, 1]), Image.BICUBIC, expand=False, fillcolor=bg)

    a = np.asarray(img, dtype=np.float32)
    theta = r.uniform(0, 2 * np.pi)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    g = (xx / w - 0.5) * np.cos(theta) + (yy / h - 0.5) * np.sin(theta)
    a = a * (1 - u("shade") * (g - g.min()) / (np.ptp(g) + 1e-6))
    a = (a - 128) * u("contrast") + 128 + u("bright")
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.GaussianBlur(u("blur")))

    a = np.asarray(img, dtype=np.float32) + r.normal(0, u("noise"), (h, w)).astype(np.float32)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=int(r.integers(*p["jpeg"])))
    buf.seek(0)
    return Image.open(buf).convert("L")
