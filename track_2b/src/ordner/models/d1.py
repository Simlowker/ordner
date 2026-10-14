import torch
from PIL import Image
from transformers import AutoModel

from . import DEVICE, FIELDS, free_memory

MODEL_ID = "LiquidAI/d1-3B"
REVISION = "051bcc464b01b9f92942b364d9586b0ef5912432"  # pinned: the repo ships remote code
DOC_TYPES = {
    "swiss_tax_statement_eCH0196": "Swiss tax statement of a bank or broker (Steuerauszug / relevé fiscal, eCH-0196)",
    "qr_bill_invoice": "Invoice or payment slip with a Swiss QR-bill (QR-Rechnung / QR-facture)",
    "health_insurance_premium_letter": "Health insurance (LAMal / KVG) premium notice or policy letter",
    "other": "Any other document",
}
_model = None


def load(device=DEVICE, dtype=torch.float32):
    """fp32 by default: in bf16 the answer logits are quantised (steps of 0.125), so P(yes) takes few distinct
    values (ties hurt calibration/AUROC). fp32 on MPS: 13 GB, same speed. Pass torch.bfloat16 to halve memory."""
    global _model
    _model = AutoModel.from_pretrained(MODEL_ID, revision=REVISION, trust_remote_code=True, dtype=dtype).to(device)


def unload():
    global _model
    _model = None
    free_memory()


def _images(images):
    return [Image.open(i).convert("RGB") if isinstance(i, str) else i for i in images] if images else None


def route(state=None, images=None) -> dict:
    """{doc_type: prob}. state = OCR text (or None when the page image is the whole state)."""
    if _model is None:
        load()
    q = {"type": "choice", "instructions": "What kind of document is this?", "criteria": DOC_TYPES}
    return _model.system_one(state, {"doc": q}, images=_images(images))["answers"]["doc"]["probabilities"]


def validate_all(state, values, images=None) -> dict:
    """{field: P(yes)} that each value is that field in the document; one pass, state read once."""
    if _model is None:
        load()
    qs = {f: {"type": "noul", "instructions": f"Is {v} the {FIELDS.get(f, f)} shown in this document?"}
          for f, v in values.items()}
    answers = _model.system_one(state, qs, images=_images(images))["answers"]
    return {f: a["noul"] for f, a in answers.items()}


def validate(state, field, value, images=None) -> float:
    return validate_all(state, {field: value}, images)[field]
