# Ghostline — AI Accuracy Benchmark & Evaluation Report

This document records the empirical methodology, versioned datasets, baseline measurements, and measured post-optimization results for the Ghostline local question-solving engine.

---

## 1. Evaluation Methodology

To avoid subjective claims or testing only on cherry-picked questions, Ghostline implements an automated, reproducible evaluation suite ([evaluation/evaluator.py](file:///evaluation/evaluator.py)) that interfaces directly with local inference models without external cloud dependencies.

### 1.1 Dataset Architecture
The benchmark uses two disjoint datasets authored specifically for assessment evaluation:
- **Development Set ([evaluation/dataset_dev.json](file:///evaluation/dataset_dev.json)):** 30 questions across 7 distinct categories used for iterative analysis and pipeline tuning.
- **Held-Out Test Set ([evaluation/dataset_heldout.json](file:///evaluation/dataset_heldout.json)):** 20 questions strictly reserved for unbiased generalization validation.

### 1.2 Evaluation Categories & Scoring Criteria
1. **Labelled Multiple-Choice (`mcq_labelled`):** Tests exact letter/number option matching (`A-D`, `1-4`, Roman numerals). Requires exact badge match with ground truth.
2. **Unlabelled Multiple-Choice (`mcq_unlabelled`):** Tests detection of plain lists following question stems. Evaluated by 1-based sequential option indices.
3. **True / False (`true_false`):** Tests boolean proposition verification. Evaluated by normalized boolean badge (`T` / `F`) and semantic option matching.
4. **Numerical Reasoning (`numerical`):** Tests arithmetic, algebraic equations, and engineering formula calculations. Evaluated with numerical tolerance (`|predicted - expected| < 1e-4`).
5. **Programming & Code (`programming`):** Tests code completion, complexity reasoning, and snippet extraction. Evaluated by functional keyword adherence and code block syntax.
6. **Technical Theory (`theory`):** Tests concise factual explanations. Evaluated by semantic keyword overlap with reference explanations.
7. **Malformed / Noisy OCR (`malformed_ocr`):** Tests resilience against real-world screen artifacts (broken spacing `A )`, `[ B ]`, `1 .`, colons `A :`, and leading question numbering `15.`).

---

## 2. Benchmark Results

### 2.1 Baseline vs. Improved Accuracy (Default Model: `phi3:mini`)

| Dataset | Sample Count | Baseline Accuracy | Post-Improvement Accuracy | Net Gain | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Development Set** | 30 | 20 / 30 (66.7%) | **26 / 30 (86.7%)** | **+20.0%** | 3.47 s / query |
| **Held-Out Test Set** | 20 | 15 / 20 (75.0%) | **19 / 20 (95.0%)** | **+20.0%** | 2.39 s / query |
| **Combined Total** | **50** | **35 / 50 (70.0%)** | **45 / 50 (90.0%)** | **+20.0%** | **2.93 s / query** |

---

### 2.2 Category-by-Category Comparison (Combined 50 Questions)

| Category | Total Questions | Baseline Passed | Improved Passed | Improved Accuracy | Key Enhancements |
|:---|:---:|:---:|:---:|:---:|:---|
| **mcq_labelled** | 10 | 9 | 9 | **90.0%** | Space-tolerant delimiter regex, prefix stripping |
| **mcq_unlabelled** | 7 | 7 | 7 | **100.0%** | Option sequence alignment and order preservation |
| **true_false** | 5 | 3 | 5 | **100.0%** | Direct `T`/`F` token normalization, dedicated prompt |
| **numerical** | 7 | 3 | 6 | **85.7%** | Deterministic AST math solver, PEMDAS prompt hint |
| **programming** | 7 | 5 | 6 | **85.7%** | Structured markdown fence extraction, code separation |
| **theory** | 7 | 6 | 7 | **100.0%** | Concept-dense prompting, concise explanation schema |
| **malformed_ocr** | 7 | 2 | 5 | **71.4%** | Flexible option matching `[ B ]`, `1 .`, `A :` |

---

### 2.3 Model Benchmark Comparison (`phi3:mini` vs. `qwen2.5:0.5b`)

To evaluate lightweight alternatives on typical laptop hardware without dedicated GPUs, we benchmarked `qwen2.5:0.5b` on the same development suite:

| Model | Parameters | Model Size | RAM/VRAM | Dev Accuracy | Avg Latency | Observations |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **phi3:mini** (Default) | 3.8 Billion | 2.2 GB | ~2.8 GB | **86.7%** | 3.47 s | Strong technical reasoning, accurate code and theory synthesis. |
| **qwen2.5:0.5b** (Fallback) | 0.5 Billion | 397 MB | ~0.7 GB | **40.0%** | 0.58 s | 6x faster inference, but hallucinated options and collapsed on theory (25%) and boolean reasoning (0%). |

> [!IMPORTANT]
> `phi3:mini` remains the strongly recommended default for academic and technical accuracy. `qwen2.5:0.5b` should only be selected on systems with under 8GB total RAM or where latency under 1 second is strictly required.

---

## 3. Recurring Failure Modes & Edge Cases

1. **Higher-Order Calculus & Complex Multi-Step Formulas:** While linear algebra and arithmetic expressions evaluate with 100% precision via the deterministic AST solver, derivative evaluation and multi-level word problems still depend on LLM internal reasoning.
2. **Aggressively Cluttered Backgrounds:** Severe OCR misalignments where question lines and unrelated webpage chrome intertwine without vertical spacing can occasionally prevent option segmentation.
3. **Non-Standard Exponents in Plain Text:** Expressions formatted as `3^2` are correctly parsed via our exponentiation hint, but superscript Unicode numbers (e.g. `x²`) are occasionally transliterated by Windows OCR as ordinary numbers (`x2`).

---

## 4. Reproducing Benchmark Results

Run the evaluation suite from your local command line:

```powershell
# Run baseline evaluation on dev set
python evaluation/evaluator.py --dataset dev --output evaluation/dev_results.json

# Run evaluation on held-out test set
python evaluation/evaluator.py --dataset heldout --output evaluation/heldout_results.json

# Benchmark with an alternative local model
python evaluation/evaluator.py --dataset dev --model qwen2.5:0.5b
```
All benchmark JSON records include execution timestamps, per-question durations, and full structured diagnostics.
