import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from . import DEVICE, free_memory

MODEL_ID = "google/embeddinggemma-2"
_model = None


def load(device=DEVICE, dtype=torch.bfloat16):
    """bf16 or fp32 only: fp16 silently returns NaN/degraded embeddings (model card)."""
    global _model
    assert dtype != torch.float16
    _model = SentenceTransformer(MODEL_ID, device=device, model_kwargs={"dtype": dtype},
                                 config_kwargs={"vision_config": None, "audio_config": None})


def unload():
    global _model
    _model = None
    free_memory()


def embed(texts, prompt_name=None) -> np.ndarray:
    """L2-normalised [n, 768] float32. prompt_name: "SearchQuery" / "Document" for retrieval, None = raw."""
    if _model is None:
        load()
    e = _model.encode(list(texts), prompt_name=prompt_name, convert_to_numpy=True).astype(np.float32)
    return e / np.linalg.norm(e, axis=1, keepdims=True)  # re-normalise in fp32 (bf16 output norms ~1.005)
