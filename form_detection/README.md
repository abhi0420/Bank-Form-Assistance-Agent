# Form Field Detection — Research

Experimental pipeline for automatically detecting question-answer field pairs in scanned bank forms, intended to remove the need for manually mapping field coordinates.

## Approach

**LayoutLMv3 + YOLOv8 hybrid:**
- LayoutLMv3 (fine-tuned) — detects question label tokens using OCR + layout
- YOLOv8n (fine-tuned) — detects blank answer box regions visually
- Spatial cost matching — pairs each question region to its nearest answer box

See `layoutlm.ipynb` for the full training and inference pipeline.

## Why this isn't in production

| Metric | Result |
|---|---|
| Question detection (LayoutLMv3) | ~80% |
| Answer box detection (YOLOv8) | ~70% |
| Training data | 22 annotated forms |

70–80% accuracy isn't reliable enough to auto-generate `field_coordinates.json` for new forms without significant manual correction. The core bottleneck is data — 22 forms is too few for the visual variety across banks and form layouts.

## Taking it forward

Training on a larger set of annotated forms (ideally 200+) would push accuracy to production grade. If you're interested in improving this pipeline, annotating more forms in Label Studio using the same `Question` / `Answer` / `Other` schema and retraining from the notebook is the most direct path.

## Model Weights

No pre-trained weights are provided. Since production-grade accuracy requires training on a much larger dataset anyway, run the notebook end-to-end on your own annotated forms to produce your own `best.pt` and `layoutlmv3-question-detector/` weights.
