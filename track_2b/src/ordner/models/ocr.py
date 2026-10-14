import torch
from PIL import Image
from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor

from . import DEVICE, free_memory

MODEL_ID = "lightonai/LightOnOCR-3-1B"
_model = _processor = None


def load(device=DEVICE, dtype=None, longest_edge=1540):
    """dtype default: float32 on MPS (model card), bf16 elsewhere. bf16 also works on MPS (~2x faster, same totals).
    longest_edge: image resize target (card: 1540); 1024-1280 is faster."""
    global _model, _processor
    dtype = dtype or (torch.float32 if device == "mps" else torch.bfloat16)
    # Checkpoint ships the mistral3/llava key layout; without this mapping the text decoder stays randomly
    # initialised in transformers 5.19 and the output is garbage ("users users ...").
    _model = LightOnOcrForConditionalGeneration.from_pretrained(
        MODEL_ID, dtype=dtype, key_mapping={r"^language_model\.model\.": "model.language_model."}
    ).to(device).eval()
    _processor = LightOnOcrProcessor.from_pretrained(MODEL_ID)
    _processor.image_processor.size = {"longest_edge": longest_edge}


def unload():
    global _model, _processor
    _model = _processor = None
    free_memory()


@torch.inference_mode()
def ocr_page(png_path, max_new_tokens=2048, prompt="") -> str:
    """Transcribe a page image to markdown. prompt="" = transcription mode, "grounding" = with boxes.
    ponytail: one page per call; batching 4-8 pages on MPS was slower per page (18-24 s vs 14 s)."""
    if _model is None:
        load()
    content = [{"type": "image", "image": Image.open(png_path).convert("RGB")}]
    if prompt:
        content.append({"type": "text", "text": prompt})
    inputs = _processor.apply_chat_template(
        [{"role": "user", "content": content}],
        add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt",
    )
    inputs = {k: v.to(_model.device, _model.dtype) if v.is_floating_point() else v.to(_model.device)
              for k, v in inputs.items()}
    out = _model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return _processor.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
