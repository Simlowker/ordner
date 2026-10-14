"""Watched inbox folder and single-file share import: sha256 dedupe, type sniffing, hand-off to the right parser.

PDF -> eCH-0196 barcode, else QR-bill, else needs_ai_read. Image -> QR-bill, else needs_ai_read. XML -> camt.05x or
eCH-0196. Video -> frames (ffmpeg), sharpest frame per page, near-duplicate pages dropped, each page read as an image.
    python -m ordner.connectors.inbox <folder> --subject <id> [--watch]
"""
import argparse
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from ordner.connectors import Parsed, camt, ech0196, new_document, persist, qrbill, sha256

PAGES_DIR = Path(os.environ.get("ORDNER_HOME", "~/.ordner")).expanduser() / "pages"


def detect(path) -> str:
    with open(path, "rb") as f:
        head = f.read(4096)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*", b"GIF8")) or head[8:12] == b"WEBP":
        return "image"
    if head[4:8] == b"ftyp":
        return "heic" if head[8:12] in (b"heic", b"heix", b"mif1", b"msf1") else "video"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "video"
    text = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    if text.startswith(b"<"):
        if b"camt.05" in head:
            return "camt"
        if b"eCH-0196" in head:
            return "ech0196_xml"
        return "xml"
    return "unknown"


def known_hashes(store, subject_id) -> set:
    return {d.sha256 for d in store.documents(subject_id)} if store is not None else set()


def import_file(path, subject_id, channel="share", store=None, seen=None, pages_dir=PAGES_DIR) -> list[Parsed]:
    """One file in, one Parsed per logical document out (a video gives one per page). Writes via `store` if given."""
    seen = known_hashes(store, subject_id) if seen is None else seen
    digest = sha256(path)
    if digest in seen:
        return [Parsed(new_document(path, subject_id, channel, digest), status="duplicate",
                       message="same sha256 already imported")]
    seen.add(digest)
    kind = detect(path)
    if kind == "pdf":
        r = ech0196.read(path, subject_id, channel, digest)
        if r.status != "ok":
            q = qrbill.read(path, subject_id, channel, digest)
            r = q if q.status == "ok" else r
        out = [r]
    elif kind == "image":
        out = [qrbill.read(path, subject_id, channel, digest)]
    elif kind == "camt":
        out = [camt.read(path, subject_id, "camt", digest)]
    elif kind == "ech0196_xml":
        with open(path, "rb") as f:
            out = [ech0196.from_xml(f.read(), new_document(path, subject_id, channel, digest))]
        out[0].document.read_path = "structured"
    elif kind == "video":
        out = import_video(path, subject_id, Path(pages_dir) / digest[:12], digest)
    else:
        msg = "HEIC: export as JPEG/PDF first" if kind == "heic" else f"unsupported file type ({kind})"
        out = [Parsed(new_document(path, subject_id, channel, digest), status="unsupported", message=msg)]
    return [persist(r, store) for r in out]


def scan(folder, subject_id, store=None, seen=None, settle=2.0) -> list[Parsed]:
    """Import every file of `folder` (not recursive, hidden files skipped). Files modified less than `settle` seconds
    ago are left for the next pass, so a copy in progress is never read half-written."""
    seen = known_hashes(store, subject_id) if seen is None else seen
    out = []
    for p in sorted(Path(folder).iterdir()):
        if p.is_file() and not p.name.startswith(".") and time.time() - p.stat().st_mtime >= settle:
            out += import_file(p, subject_id, "inbox", store, seen)
    return out


def watch(folder, subject_id, store=None, interval=5.0):
    # ponytail: polling that re-hashes every file per pass; remember (path, mtime) or use FSEvents for big folders
    seen = known_hashes(store, subject_id)
    while True:
        for r in scan(folder, subject_id, store, seen):
            if r.status != "duplicate":
                print(f"{r.status:<14} {r.document.kind or '-':<30} {Path(r.document.path).name}  {r.message}")
        time.sleep(interval)


# --- video -------------------------------------------------------------------------------------------------------

def sharpness(img) -> float:
    """Variance of the Laplacian on a grayscale copy at most 1000 px wide (scale-independent ranking)."""
    g = img.convert("L")
    if g.width > 1000:
        g = g.resize((1000, round(g.height * 1000 / g.width)))
    a = np.asarray(g, dtype=np.float32)
    lap = a[1:-1, :-2] + a[1:-1, 2:] + a[:-2, 1:-1] + a[2:, 1:-1] - 4 * a[1:-1, 1:-1]
    return float(lap.var())


def _load(f):
    if isinstance(f, Image.Image):
        return f
    with Image.open(f) as im:
        return im.convert("RGB")


def _thumb(img, size=128):
    g = img.convert("L").resize((size, size), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1))
    a = np.asarray(g, dtype=np.float32)
    return (a - a.mean()) / (a.std() + 1e-6)


def _dist(a, b) -> float:
    """Mean absolute difference after removing the best translation (phase correlation): hand jitter ~ 0."""
    f = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    r = np.fft.ifft2(f / (np.abs(f) + 1e-6)).real
    dy, dx = np.unravel_index(np.argmax(r), r.shape)
    n, m = a.shape[0], a.shape[0] // 16
    b = np.roll(b, (dy - n if dy > n // 2 else dy, dx - n if dx > n // 2 else dx), axis=(0, 1))
    return float(np.abs(a[m:-m, m:-m] - b[m:-m, m:-m]).mean())


def pick_pages(frames, still=0.12, min_frames=2, same=0.03, maybe_same=0.09) -> list[dict]:
    """frames: PIL images or image paths in time order (paths keep long videos out of RAM)
    -> [{"index", "sharpness", "image", "possible_duplicate_of"}], one per page.
    A page = a run of still frames (consecutive distance < `still`); shorter runs are page turns and are dropped;
    the sharpest frame of each run is kept. A page closer than `same` to a sharper kept page is dropped; closer than
    `maybe_same` it is kept and flagged, because near-blank pages with the same header look alike at this scale.
    ponytail: tuned on synthetic frames of real statement pages; calibrate on real phone videos."""
    thumbs = [_thumb(_load(f)) for f in frames]
    runs = [[0]] if frames else []
    for i in range(1, len(frames)):
        if _dist(thumbs[i], thumbs[i - 1]) < still:
            runs[-1].append(i)
        else:
            runs.append([i])
    pages = [max((sharpness(_load(frames[i])), i) for i in run) for run in runs if len(run) >= min_frames]
    kept = []
    for s, i in sorted(pages, reverse=True):
        d = [(_dist(thumbs[i], thumbs[k["index"]]), k["index"]) for k in kept]
        near = min(d) if d else (np.inf, None)
        if near[0] >= same:
            kept.append({"index": i, "sharpness": s, "possible_duplicate_of": near[1] if near[0] < maybe_same else None})
    kept.sort(key=lambda p: p["index"])
    return [{**p, "image": _load(frames[p["index"]])} for p in kept]


def extract_frames(video, out_dir, fps=4.0) -> list | None:
    """Frame PNG paths written by ffmpeg into `out_dir`, or None when ffmpeg is not installed."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    subprocess.run([ffmpeg, "-loglevel", "error", "-i", str(video), "-vf", f"fps={fps}",
                    str(Path(out_dir) / "f%05d.png")], check=True)
    return sorted(Path(out_dir).glob("f*.png"))


def import_video(path, subject_id, out_dir=None, digest=None) -> list[Parsed]:
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(path, tmp)
        pages = pick_pages(frames) if frames else []
    if frames is None:
        return [Parsed(new_document(path, subject_id, "video", digest), status="skipped",
                       message="ffmpeg not installed: video skipped (brew install ffmpeg), or share photos/PDF instead")]
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix="ordner_pages_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    video = new_document(path, subject_id, "video", digest, kind="video_capture", read_path="frames",
                         fields={"frames": len(frames), "pages": len(pages), "pages_dir": str(out_dir)})
    out = [Parsed(video, status="ok" if pages else "needs_ai_read",
                  message=f"{len(pages)} page(s) kept from {len(frames)} frames")]
    payloads = set()
    for n, page in enumerate(pages, 1):
        png = out_dir / f"page_{n:02d}.png"
        page["image"].save(png)
        r = qrbill.read(png, subject_id, "video", images=[page["image"]])
        if r.status == "ok" and r.document.fields["payload"] in payloads:     # same QR content: exact duplicate
            r.status, r.facts, r.message = "duplicate", [], "same QR-bill payload as an earlier page"
        payloads.add(r.document.fields.get("payload"))
        r.document.fields.update(source_video=str(Path(path).resolve()), frame=page["index"],
                                 sharpness=round(page["sharpness"], 1),
                                 possible_duplicate_of_frame=page["possible_duplicate_of"])
        out.append(r)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m ordner.connectors.inbox")
    ap.add_argument("path", help="folder to scan/watch, or one file to import (share)")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=float, default=5.0)
    a = ap.parse_args(argv)
    try:
        from ordner.case.store import Store
        store = Store()
    except ImportError:
        store = None
        print("ordner.case not available: results are printed, not stored")
    if a.watch:
        watch(a.path, a.subject, store, a.interval)
    results = import_file(a.path, a.subject, "share", store) if Path(a.path).is_file() else scan(a.path, a.subject, store)
    for r in results:
        print(f"{r.status:<14} {r.document.kind or '-':<30} {Path(r.document.path).name}  facts={len(r.facts)}  {r.message}")


if __name__ == "__main__":
    main()
