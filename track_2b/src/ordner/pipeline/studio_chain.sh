#!/usr/bin/env bash
# macstudio: base extraction on all pages, then LoRA extraction on dev+test (both resumable).
set -u
cd "$(dirname "$0")/../../.."
export PYTHONPATH=src TOKENIZERS_PARALLELISM=false
PY=../.venv/bin/python
$PY -m ordner.pipeline.extract_batch --tag apertus-base >> work/extract.apertus-base.log 2>&1
$PY -m ordner.pipeline.extract_batch --tag apertus-lora --adapter work/adapters/lora-v1 --splits dev,test >> work/extract.apertus-lora.log 2>&1
touch work/EXTRACT_DONE
