#!/usr/bin/env bash
# LoRA of the Apertus 8B coordinator on verified teacher turns (macstudio, from ~/ordner/track_2b).
# Needs work/distill/lora_data (python -m ordner.distill.prepare). Extra args override lora_config.yaml.
set -euo pipefail
cd "$(dirname "$0")/../../.."
export PYTHONPATH=src TOKENIZERS_PARALLELISM=false
PY=${PY:-../.venv/bin/python}
CFG=src/ordner/distill/lora_config.yaml
N=$(wc -l < work/distill/lora_data/train.jsonl)
ITERS=$(( 2 * N ))   # 2 epochs: mlx-lm counts iterations in batches of 1 (accumulation does not change it)
$PY -m ordner.distill.train --config $CFG --iters "$ITERS" "$@"
