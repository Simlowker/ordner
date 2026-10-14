"""document.read (PDF text layer, LightOnOCR-3 or its replay cache) and document.decode (eCH-0196 PDF417, Swiss QR-bill)."""
import io
import json
from functools import lru_cache
from pathlib import Path

from ordner.core.schema import ToolSpec

from .base import ROOT, ToolError, mode, need, work

IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
MIN_TEXT_LAYER = 50  # characters: below this a PDF is treated as a scan
MAX_CHARS = 6000


def jsonl(path):
    with open(path) as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                pass  # blank line or partial last line of a file still being written


@lru_cache(maxsize=4)
def pages(work_dir: Path) -> dict:
    f = work_dir / "pages.jsonl"
    return {p["page_id"]: p for p in jsonl(f)} if f.exists() else {}


@lru_cache(maxsize=4)
def ocr_cache(work_dir: Path) -> dict:
    return {r["page_id"]: r for f in sorted(work_dir.glob("ocr.*.jsonl")) for r in jsonl(f)}


def resolve(ref: str, ctx, trusted=False) -> dict:
    """Dossier document id, file path, replay document id or page id -> {"path": Path|None, "page_ids": replay pages
    (cleanest scan first), "record": the dossier Document when ref is one}."""
    if ref.startswith("doc_") and ctx.get("store") is not None:
        rec = ctx["store"].get_document(ref)
        if ctx.get("subject_id") and rec.subject_id != ctx["subject_id"]:
            raise ToolError(f"document {ref} belongs to another dossier")
        if rec.path.startswith("placeholder:"):
            return {"path": None, "page_ids": [], "record": rec}
        return {**resolve(rec.path, ctx, trusted=True), "record": rec}
    w = work(ctx)
    pg = pages(w)
    if ref in pg:
        return {"path": ROOT / pg[ref]["png_path"], "page_ids": [ref]}
    path = next((p for p in (Path(ref).expanduser(), ROOT / ref, w / ref) if p.is_file()), None)
    if path is not None and ctx.get("subject_id") and not trusted and not path.resolve().is_relative_to(ROOT):
        raise ToolError("in a dossier session only dossier documents (doc_...) are read, not other files")
    if path is not None and path.suffix.lower() not in IMAGES | {".pdf"}:
        raise ToolError(f"unsupported file type '{path.suffix}': PDF or image only")
    doc_id = path.stem if path else ref
    if doc_id in pg:  # a page image of the replay set
        return {"path": path, "page_ids": [doc_id]}
    ids = sorted((p for p in pg.values() if p["doc_id"] == doc_id), key=lambda p: (p["page_no"], p["degradation"]))
    if path is None and (w / "pdf" / f"{doc_id}.pdf").is_file():
        path = w / "pdf" / f"{doc_id}.pdf"
    if path is None and not ids:
        raise ToolError(f"unknown document '{ref}': give a file path, a document id or a page id")
    return {"path": path, "page_ids": [p["page_id"] for p in ids]}


def _native(path, wanted):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        return [{"page": i + 1, "text": pdf[i].get_textpage().get_text_bounded().replace("\r\n", "\n").strip()}
                for i in range(len(pdf)) if not wanted or i + 1 in wanted]
    finally:
        pdf.close()


def _images(path, wanted=None, scale=2):
    if path.suffix.lower() in IMAGES:
        from PIL import Image

        return [(1, Image.open(path).convert("RGB"))]
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        return [(i + 1, pdf[i].render(scale=scale).to_pil()) for i in range(len(pdf)) if not wanted or i + 1 in wanted]
    finally:
        pdf.close()


def _cap(pages_, limit, warnings):
    out, left = [], limit
    for p in pages_:
        if left <= 0:
            warnings.append(f"stopped before page {p['page']}: max_chars={limit} reached, ask for specific pages")
            break
        if len(p["text"]) > left:
            p = {**p, "text": p["text"][:left]}
            warnings.append(f"page {p['page']} truncated at max_chars={limit}")
        out.append(p)
        left -= len(p["text"])
    return {"pages": out}


def replay_pages(d, ctx, wanted=None):
    """Cached OCR of the cleanest scan of each page."""
    cache, pg = ocr_cache(work(ctx)), pages(work(ctx))
    out, seen = [], set()
    for pid in d["page_ids"]:
        n = pg[pid]["page_no"]
        if pid in cache and n not in seen and (not wanted or n in wanted):
            seen.add(n)
            out.append({"page": n, "text": cache[pid]["text"], "page_id": pid})
    return out


def _record(rec):
    return {k: getattr(rec, k) for k in ("id", "kind", "year", "issuer", "read_path", "fields", "doubt")}


def read(args, ctx):
    d = resolve(args["doc"], ctx)
    try:
        data, warnings, prov = _read(d, args, ctx)
    except ToolError as e:
        if not d.get("record"):
            raise
        warning = f"{e}: only the fields recorded at import are available"
        return {"pages": [], "recorded": _record(d["record"])}, [warning], {"source": "ordner.case document"}
    if d.get("record"):
        data["recorded"] = _record(d["record"])
    return data, warnings, prov


def _read(d, args, ctx):
    path, method, wanted = d["path"], args.get("method", "auto"), set(args.get("pages") or [])
    limit, warnings = args.get("max_chars", MAX_CHARS), []
    if path is None and not d["page_ids"]:
        raise ToolError("no original file in the dossier")
    if path is not None and path.suffix.lower() == ".pdf" and method != "ocr":
        out = _native(path, wanted)
        if sum(len(p["text"]) for p in out) >= MIN_TEXT_LAYER:
            return _cap(out, limit, warnings), warnings, {"source": "pdf_text_layer", "file": str(path)}
        if method == "native":
            raise ToolError("this PDF has no text layer: call again with method='ocr'")
        warnings.append("no text layer (scan): read by OCR")
    if mode(ctx) == "replay":
        out = replay_pages(d, ctx, wanted)
        if not out:
            raise ToolError("replay mode: no cached OCR for this document (live mode runs LightOnOCR-3)")
        model = ocr_cache(work(ctx))[out[0]["page_id"]].get("model")
        warnings.append("OCR text may contain recognition errors: check values against the original")
        return _cap(out, limit, warnings), warnings, {"source": "replay_ocr_cache", "model": model,
                                                      "cache": "work/ocr.*.jsonl"}
    from ordner.models import ocr

    out = []
    for n, img in _images(path, wanted):
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        out.append({"page": n, "text": ocr.ocr_page(buf)})
    warnings.append("OCR text may contain recognition errors: check values against the original")
    return _cap(out, limit, warnings), warnings, {"source": "ocr", "model": ocr.MODEL_ID, "file": str(path)}


def state_text(args, ctx):
    """Text a model works on: args.text, else page 1 of args.doc -> (text, page_id or None, source)."""
    if args.get("text"):
        return args["text"], None, "args.text"
    if not args.get("doc"):
        raise ToolError("give 'text' or 'doc'")
    d = resolve(args["doc"], ctx)
    if mode(ctx) == "replay":
        out = replay_pages(d, ctx, {1})
        if out:
            return out[0]["text"], out[0]["page_id"], "replay_ocr_cache"
    data, _, prov = _read(d, {"pages": [1]}, ctx)
    page = data["pages"][0]
    return page["text"], page.get("page_id"), prov["source"]


def decode(args, ctx):
    path = resolve(args["doc"], ctx)["path"]
    if path is None:
        raise ToolError("no original file for this document")
    data, warnings, prov = {"ech0196": None, "qr_bill": None}, [], {"source": "barcode", "file": str(path)}
    if path.suffix.lower() == ".pdf":
        import zlib

        from ordner.gen import oracle

        try:
            xml = oracle.decode_pdf417(path)
            data["ech0196"] = {"fields": oracle.fields_from_xml(xml), "xml_bytes": len(xml)}
            prov["ech0196"] = "ordner.gen.oracle (Macro-PDF417 -> zlib -> eCH-0196 XML)"
        except ValueError:
            warnings.append("no eCH-0196 PDF417 barcode")
        except zlib.error:
            warnings.append("PDF417 barcodes found but their data does not decompress (incomplete or damaged)")
    qrbill = need("ordner.connectors.qrbill", "W6 QR-bill parser")
    bills = qrbill.decode_images([img for _, img in _images(path)])
    if bills:
        data["qr_bill"] = qrbill.parse(bills[0])
        prov["qr_bill"] = "ordner.connectors.qrbill (SIX IG QR-bill v2.3)"
        warnings += [f"QR-bill: {e}" for e in data["qr_bill"].get("errors", [])]
        if len(bills) > 1:
            warnings.append(f"{len(bills)} QR-bills found, only the first is returned")
    if not (data["ech0196"] or data["qr_bill"]):
        warnings.append("no machine-readable code found: use document.read")
    return data, warnings, prov


DOC = {"type": "string", "description": "dossier document id (doc_...), file path or page id"}
TOOLS = [
    (ToolSpec(
        "document.read",
        "Get the text of a document, page by page. PDF with a text layer: exact text. Scan or photo: OCR "
        "(LightOnOCR-3), may contain recognition errors.",
        {"type": "object", "properties": {
            "doc": DOC,
            "pages": {"type": "array", "items": {"type": "integer"}, "description": "1-based page numbers; default all"},
            "method": {"type": "string", "enum": ["auto", "native", "ocr"],
                       "description": "auto = text layer if present, else OCR"},
            "max_chars": {"type": "integer", "description": f"text budget, default {MAX_CHARS}"}},
         "required": ["doc"]},
        {"type": "object", "properties": {"pages": {"type": "array", "items": {"type": "object", "properties": {
            "page": {"type": "integer"}, "text": {"type": "string"}, "page_id": {"type": "string"}}}}}},
    ), read),
    (ToolSpec(
        "document.decode",
        "Decode machine-readable codes, exact values: eCH-0196 tax statement barcode (PDF417 -> 8 summary fields) "
        "and Swiss QR-bill (IBAN, amount, reference, creditor, validated against SIX rules). Prefer this over reading.",
        {"type": "object", "properties": {"doc": DOC}, "required": ["doc"]},
        {"type": "object", "properties": {
            "ech0196": {"type": ["object", "null"], "description": "{fields: {totalTaxValue, totalGrossRevenueA, "
                        "totalGrossRevenueB, totalWithHoldingTaxClaim, institution, canton, taxPeriod, "
                        "client_last_name}, xml_bytes}"},
            "qr_bill": {"type": ["object", "null"], "description": "{iban, iban_valid, qr_iban, amount, currency, "
                        "reference_type, reference, creditor, debtor, message, errors, warnings}"}}},
    ), decode),
]
