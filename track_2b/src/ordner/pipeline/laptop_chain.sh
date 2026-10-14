#!/usr/bin/env bash
# laptop: after OCR, ship OCR to macstudio, route all pages with d1, then validate extractions as they arrive.
set -u
cd "$(dirname "$0")/../../.."
export PYTHONPATH=src TOKENIZERS_PARALLELISM=false
PY=.venv/bin/python
until grep -q OCR_ALL_DONE work/ocr_laptop_rest.log; do sleep 30; done
rsync -a work/ocr.*.jsonl macstudio:ordner/track_2b/work/ && ssh macstudio 'touch ~/ordner/track_2b/work/OCR_ALL_DONE'
$PY -m ordner.pipeline.d1_batch --tag route
while :; do
  rsync -a macstudio:ordner/track_2b/work/extract.apertus-*.jsonl work/ 2>/dev/null
  for t in apertus-base apertus-lora; do [ -f work/extract.$t.jsonl ] && $PY -m ordner.pipeline.d1_batch --tag $t; done
  ssh macstudio 'test -f ~/ordner/track_2b/work/EXTRACT_DONE' && break
  sleep 120
done
rsync -a macstudio:ordner/track_2b/work/extract.apertus-*.jsonl work/
for t in apertus-base apertus-lora; do $PY -m ordner.pipeline.d1_batch --tag $t; done
rsync -a macstudio:ordner/track_2b/work/acts work/
touch work/PIPELINE_DONE
