# Offline passport OCR postprocessing

## Installation

Python 3.10+; CPU; no network at inference. Install dependencies once before offline use:

```bash
python -m pip install -r requirements.txt
```

## Required invocation

```bash
python postprocess.py data/test_predictions.jsonl answers.jsonl
```

Run from the repository root. The models are loaded from `models_v029/` relative to the script, not the working directory. No training labels are needed for inference.

## Notes

* Accept only if all baseline MRZ, character-confidence, field format, age/replacement rules, and second-pass text checks pass; two field-level CatBoost classifiers must each return error risk < 0.05.
* Age-related passport replacement is screened with a 90-day grace period as of 2026-10-01. No OCR-only solution can verify revocation, loss reports, forgery, or government database status.
* The ML threshold was selected during exploratory development on overlapping subsets of the available training set. The observed error rates are not an independent prospective estimate.
* To reproduce without ML for comparison: `python postprocess.py data/test_predictions.jsonl answers_rules.jsonl --no-ml`.
