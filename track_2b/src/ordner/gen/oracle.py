"""Ground truth from the eCH-0196 Macro-PDF417 barcodes of a clean PDF."""

import itertools
import xml.etree.ElementTree as ET
import zlib
from decimal import Decimal

import pypdfium2 as pdfium
import zxingcpp

from .synth import FIELDS, NS, NUMERIC


def decode_pdf417(pdf_path, scale=3):
    """Return the XML bytes stored in the PDF417 barcodes (scanning pages from the end)."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    segs = []
    for i in reversed(range(len(pdf))):
        img = pdf[i].render(scale=scale).to_pil()
        found = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.PDF417)
        if not found and segs:
            break
        # OSA places segment 1 rightmost on each barcode page.
        segs += [(i, -r.position.top_left.x, bytes(r.bytes)) for r in found]
    pdf.close()
    if not segs:
        raise ValueError(f"no PDF417 in {pdf_path}")
    data = [b for _, _, b in sorted(segs)]
    try:
        return zlib.decompress(b"".join(data))
    except zlib.error:
        if len(data) > 6:
            raise
        for perm in itertools.permutations(data):
            try:
                return zlib.decompress(b"".join(perm))
            except zlib.error:
                continue
        raise


def fields_from_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)
    n = {"e": NS}
    out = {k: root.get(k) for k in NUMERIC}
    out["institution"] = root.find("e:institution", n).get("name")
    out["canton"] = root.get("canton")
    out["taxPeriod"] = root.get("taxPeriod")
    out["client_last_name"] = root.find("e:client", n).get("lastName")
    return out


def mismatches(oracle, truth):
    bad = []
    for k in FIELDS:
        a, b = oracle.get(k), truth.get(k)
        same = (a is not None and b is not None and Decimal(a) == Decimal(b)) if k in NUMERIC else a == b
        if not same:
            bad.append({"field": k, "oracle": a, "truth": b})
    return bad
