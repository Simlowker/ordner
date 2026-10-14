"""Distillation pipeline (W12, PREREG Addendum 2 / H7): dev-only synthetic variants -> teacher trajectories through the
same coordinator loop -> metric filter -> Apertus-template LoRA data -> mlx-lm LoRA. Self-check:
`PYTHONPATH=src .venv/bin/python -m ordner.distill.selfcheck`."""
import json
from pathlib import Path

from ordner.eval.scenarios import ROOT

OUT = ROOT / "work" / "distill"


def read_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows)
