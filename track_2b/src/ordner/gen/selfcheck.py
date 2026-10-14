"""python -m ordner.gen.selfcheck  (asserts; ~10 s)"""

import tempfile
from collections import Counter
from decimal import Decimal
from pathlib import Path

import numpy as np
from opensteuerauszug.calculate.base import CalculationMode
from opensteuerauszug.calculate.total import TotalCalculator
from opensteuerauszug.model.ech0196 import TaxStatement
from PIL import Image

from . import build, oracle, synth
from .degrade import degrade


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # totals: our sums == independent recomputation == OSA verification
        for i in range(40):
            xml, truth, _ = synth.make_statement(11, i)
            assert synth.make_statement(11, i)[0] == xml, "generator not deterministic"
            rc = synth.recompute_totals(xml)
            assert all(Decimal(truth[k]) == v for k, v in rc.items()), (i, truth, rc)
            p = Path(tmp) / "x.xml"
            p.write_bytes(xml)
            calc = TotalCalculator(mode=CalculationMode.VERIFY)
            calc.calculate(TaxStatement.from_xml_file(str(p)))
            assert not calc.errors, calc.errors

        # round-trip oracle on 3 docs
        for i in range(3):
            xml, truth, meta = synth.make_statement(11, i)
            x, pdf = Path(tmp) / f"{i}.xml", Path(tmp) / f"{i}.pdf"
            x.write_bytes(xml)
            build.render_a(x, pdf, meta["language"])
            assert not oracle.mismatches(oracle.fields_from_xml(oracle.decode_pdf417(pdf)), truth), i

        # degradations deterministic per key
        img = Image.fromarray(np.full((200, 300), 255, np.uint8))
        assert np.array_equal(np.asarray(degrade(img, 3, "k")), np.asarray(degrade(img, 3, "k")))

        # mini build: page count per split, files present, totals visible on the page
        docs, pages = build.main(["--n", "10", "--seed", "3", "--out", str(Path(tmp) / "w"), "--workers", "4"])
        stmts = Counter(d["split"] for d in docs if d["layout"] == "A")
        per_split = Counter(p["split"] for p in pages)
        assert per_split == Counter({"train": stmts["train"], "dev": stmts["dev"], "test": 8 * stmts["test"]}), per_split
        assert all(Path(p["png_path"]).exists() for p in pages)
        assert not any(d["oracle_mismatches"] for d in docs)
        assert all(all(d["page_check"].values()) for d in docs)
    print("gen selfcheck ok")


if __name__ == "__main__":
    main()
