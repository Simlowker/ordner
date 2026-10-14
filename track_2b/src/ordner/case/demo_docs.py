"""Regenerate the fictional eCH-0196 statements of Noa Keller into data/demo/noa/ (versioned; the seed only reads them).

python -m ordner.case.demo_docs      # needs the generator deps (opensteuerauszug, pypdfium2, zxingcpp, Pillow)

Two of the three declared institutions deliver: bank 1 as a clean PDF (barcode path), the broker as a phone photo at
degradation level 2 (AI path). Bank 2 is deliberately missing, for the completeness check.
"""
import hashlib
import json
import logging
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageFilter

from ordner.gen import build, oracle, synth
from ordner.gen.degrade import degrade

ROOT = Path(__file__).resolve().parents[3]  # track_2b/
OUT = ROOT / "data" / "demo" / "noa"
SEED = 2026
FIRST, LAST, CANTON = "Noa", "Keller", "VD"
BANK1, BANK2, BROKER = "Morvessa Banque SA", "Talbruck Banque Privée SA", "Zelfeld Courtage SA"  # fictional
PLAN = [  # (file, institution, wanted: n_securities range, tax value range, channel, read_path)
    ("releve_fiscal_2025_morvessa.pdf", BANK1, (0, 0), (3_000, 15_000), "inbox", "barcode"),
    ("releve_fiscal_2025_zelfeld_photo.png", BROKER, (2, 4), (5_000, 25_000), "scan", "ai"),
]


def _pick(n_sec, tv, start=0):
    """First synthetic statement (French layout, no debt) matching the wanted shape."""
    for idx in range(start, start + 5000):
        xml, truth, meta = synth.make_statement(SEED, idx)
        if (meta["language"] == "fr" and meta["n_liabilities"] == 0 and n_sec[0] <= meta["n_securities"] <= n_sec[1]
                and tv[0] <= float(truth["totalTaxValue"]) <= tv[1]):
            return idx, xml
    raise LookupError("no matching statement")


def _personalise(xml: bytes, institution: str) -> bytes:
    root = ET.fromstring(xml)
    n = {"e": synth.NS}
    root.set("canton", CANTON)
    sid = root.get("id")  # CH{org}{ABBR}{client}X... : keep the shape, swap the 4-letter institution code
    abbr = (institution.replace(" ", "").upper() + "XXXX")[:4]
    root.set("id", sid[:7] + abbr + sid[11:])
    root.find("e:institution", n).set("name", institution)
    client = root.find("e:client", n)
    client.set("firstName", FIRST)
    client.set("lastName", LAST)
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def _photo(pdf_path: Path, png_path: Path, key: str):
    pdf = pdfium.PdfDocument(str(pdf_path))
    img = pdf[0].render(scale=build.DPI / 72, grayscale=True).to_pil().convert("L")
    pdf.close()
    img = degrade(img, 2, key)
    img = img.resize((img.width * 13 // 20, img.height * 13 // 20), Image.LANCZOS)  # ~130 dpi
    img = img.filter(ImageFilter.MedianFilter(3)).point(lambda v: v if v < 200 else 255)  # paper noise -> white
    img.quantize(16).save(png_path, optimize=True)  # ponytail: needed to stay < 300 KB as PNG; JPEG would keep more


def main():
    logging.getLogger("opensteuerauszug").setLevel(logging.ERROR)
    OUT.mkdir(parents=True, exist_ok=True)
    docs, start = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, institution, n_sec, tv, channel, read_path in PLAN:
            idx, xml = _pick(n_sec, tv, start)
            start = idx + 1
            xml_path, pdf_path = Path(tmp) / f"{idx}.xml", Path(tmp) / f"{idx}.pdf"
            xml_path.write_bytes(_personalise(xml, institution))
            build.render_a(xml_path, pdf_path, "fr")
            truth = oracle.fields_from_xml(oracle.decode_pdf417(pdf_path))  # what the barcode really carries
            assert (truth["client_last_name"], truth["canton"], truth["institution"]) == (LAST, CANTON, institution)
            target = OUT / name
            if read_path == "barcode":
                target.write_bytes(pdf_path.read_bytes())
            else:
                _photo(pdf_path, target, f"noa:{name}")
            limit = 100_000 if target.suffix == ".pdf" else 300_000
            assert target.stat().st_size < limit, (target, target.stat().st_size)
            docs.append({"file": name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                         "kind": "swiss_tax_statement_eCH0196", "year": 2025, "issuer": institution,
                         "channel": channel, "read_path": read_path, "degradation": 2 if read_path == "ai" else 0,
                         "synth": {"seed": SEED, "idx": idx}, "truth": truth,
                         "page": build.at_page_precision("A", truth)})  # totals as printed (what OCR can read)
    manifest = {"subject": f"{FIRST} {LAST} (fictional)", "declared_institutions": [
        {"name": BANK1, "type": "bank"}, {"name": BANK2, "type": "bank"}, {"name": BROKER, "type": "broker"}],
        "missing": [{"issuer": BANK2, "kind": "swiss_tax_statement_eCH0196", "year": 2025}], "documents": docs}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    for d in docs:
        print(d["file"], (OUT / d["file"]).stat().st_size, "bytes", d["truth"])


if __name__ == "__main__":
    main()
