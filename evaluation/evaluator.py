import os
import sys
import json
import time
import re
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Add parent directory to sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.core.ocr_engine import parse_question_structure
from ghostline.core.llm_client import OllamaClient, AnswerResult
from ghostline.ui.presentation import build_answer_presentation


def normalize_numeric_string(s: str) -> Optional[float]:
    """Extracts first valid number from string for numerical equivalence checking."""
    if not s:
        return None
    # Strip variables e.g. "x = 9" -> "9", "f'(3) = 24" -> "24"
    m = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", s)
    if m:
        try:
            return float(m[-1])  # Usually the final number is the answer
        except ValueError:
            pass
    return None


def evaluate_single(item: Dict[str, Any], ans: AnswerResult, pres: Any) -> Tuple[bool, str]:
    """
    Evaluates whether the generated answer satisfies ground truth criteria.
    Returns (is_correct, reason).
    """
    eval_type = item.get("eval_type", "exact_option")
    expected_badge = item.get("expected_badge", "")
    expected_text = item.get("expected_text", "")

    # Check uncertainty / error state
    if not ans.is_validated or ans.validation_status in ["error", "hallucination_rejected"] or ans.tray_badge in ["?", "!"]:
        return False, f"Uncertain or unvalidated response: {ans.error or ans.explanation[:80]}"

    if eval_type == "exact_option":
        badge_match = (
            ans.tray_badge.strip().upper() == expected_badge.strip().upper() or
            ans.answer_option.strip().upper() == expected_badge.strip().upper() or
            ans.source_option_label.strip().upper() == expected_badge.strip().upper()
        )
        if badge_match:
            return True, f"Exact badge match '{ans.tray_badge}'"

        # Content match fallback
        if expected_text and ans.option_text:
            if expected_text.strip().lower() == ans.option_text.strip().lower():
                return True, f"Option text match '{ans.option_text}'"

        return False, f"Option mismatch: got badge '{ans.tray_badge}' ({ans.option_text}), expected '{expected_badge}' ({expected_text})"

    elif eval_type == "numerical":
        exp_num = normalize_numeric_string(expected_text)
        # Check answer text, direct answer, option text
        got_candidates = [
            ans.direct_answer,
            ans.option_text,
            ans.answer_option,
            ans.explanation
        ]
        for cand in got_candidates:
            cand_num = normalize_numeric_string(cand)
            if cand_num is not None and exp_num is not None:
                if abs(cand_num - exp_num) < 1e-4:
                    return True, f"Numerical match: {cand_num} == {exp_num}"

        return False, f"Numerical mismatch: expected {exp_num}, candidates={got_candidates[:2]}"

    elif eval_type == "code_contains":
        keywords = item.get("keywords", [expected_text])
        text_to_search = (ans.code_snippet or "") + " " + (ans.answer_option or "") + " " + (ans.explanation or "")
        text_lower = text_to_search.lower()
        matched = [kw for kw in keywords if kw.lower() in text_lower]
        if matched and len(matched) >= min(len(keywords), 1):
            return True, f"Code keyword match: {matched}"
        return False, f"Code missing required patterns {keywords}. Extracted: {text_to_search[:100]}"

    elif eval_type == "semantic_theory":
        keywords = item.get("keywords", [])
        text_to_search = (ans.direct_answer or "") + " " + (ans.explanation or "") + " " + (ans.answer_option or "")
        text_lower = text_to_search.lower()
        matched = [kw for kw in keywords if kw.lower() in text_lower]
        ratio = len(matched) / len(keywords) if keywords else 0.0
        if ratio >= 0.5 or (expected_text.lower() in text_lower):
            return True, f"Theory semantic match: {matched} ({ratio*100:.0f}%)"
        return False, f"Theory missing core concepts {keywords}. Matched only: {matched}"

    return False, "Unknown evaluation type"


def run_benchmark(
    dataset_name: str = "dev",
    model_name: Optional[str] = None,
    ollama_url: str = "http://127.0.0.1:11434",
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Executes benchmark on chosen dataset and model, collecting rigorous telemetry.
    """
    eval_dir = Path(__file__).resolve().parent
    datasets_to_load = []
    if dataset_name in ["dev", "all"]:
        datasets_to_load.append(eval_dir / "dataset_dev.json")
    if dataset_name in ["heldout", "all"]:
        datasets_to_load.append(eval_dir / "dataset_heldout.json")

    items = []
    for dpath in datasets_to_load:
        if dpath.exists():
            with open(dpath, "r", encoding="utf-8") as f:
                items.extend(json.load(f))

    if not items:
        raise RuntimeError(f"No benchmark questions found for dataset '{dataset_name}'.")

    client = OllamaClient(base_url=ollama_url, default_model=model_name or "phi3:mini")
    active_model = model_name or client.default_model

    if verbose:
        print("=" * 70)
        print("  Ghostline AI Accuracy & Inference Evaluation Suite")
        print("=" * 70)
        print(f"[*] Dataset: {dataset_name} ({len(items)} questions)")
        print(f"[*] Model:   {active_model}")
        print(f"[*] Endpoint: {ollama_url}")
        print("=" * 70)

    category_stats: Dict[str, Dict[str, Any]] = {}
    difficulty_stats: Dict[str, Dict[str, Any]] = {}
    results = []
    total_start = time.time()

    for idx, item in enumerate(items, 1):
        q_id = item["id"]
        cat = item["category"]
        diff = item.get("difficulty", "medium")
        raw_ocr = item["raw_ocr"]

        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "correct": 0, "latencies": [], "failures": []}
        if diff not in difficulty_stats:
            difficulty_stats[diff] = {"total": 0, "correct": 0, "latencies": []}

        category_stats[cat]["total"] += 1
        difficulty_stats[diff]["total"] += 1

        t0 = time.time()
        # 1. OCR parsing stage
        pq = parse_question_structure({"text": raw_ocr})

        # 2. Local AI inference stage
        try:
            ans = client.solve_question(
                question_text=pq.question_text,
                options=pq.options,
                is_unlabelled_mcq=pq.is_unlabelled_mcq,
                model=active_model
            )
            pres = build_answer_presentation(pq, ans)
            duration_ms = (time.time() - t0) * 1000.0
            is_correct, reason = evaluate_single(item, ans, pres)
        except Exception as e:
            duration_ms = (time.time() - t0) * 1000.0
            is_correct = False
            reason = f"Exception: {str(e)}"
            ans = AnswerResult(
                answer_option="!",
                validation_status="error",
                is_validated=False,
                error=str(e)
            )
            pres = None

        category_stats[cat]["latencies"].append(duration_ms)
        difficulty_stats[diff]["latencies"].append(duration_ms)

        if is_correct:
            category_stats[cat]["correct"] += 1
            difficulty_stats[diff]["correct"] += 1
            status_glyph = "✓ PASS"
        else:
            status_glyph = "✗ FAIL"
            category_stats[cat]["failures"].append({"id": q_id, "reason": reason})

        if verbose:
            print(f"[{idx:02d}/{len(items):02d}] {status_glyph:6} | {cat:15} | {duration_ms:6.1f}ms | {q_id}: {reason}")

        results.append({
            "id": q_id,
            "category": cat,
            "difficulty": diff,
            "is_correct": is_correct,
            "reason": reason,
            "duration_ms": duration_ms,
            "badge": getattr(ans, "tray_badge", "?"),
            "proposed": getattr(ans, "proposed_option", None),
            "validated": getattr(ans, "is_validated", False)
        })

    total_duration = time.time() - total_start
    total_correct = sum(1 for r in results if r["is_correct"])
    overall_accuracy = (total_correct / len(items)) * 100.0 if items else 0.0

    report = {
        "dataset": dataset_name,
        "model": active_model,
        "total_questions": len(items),
        "total_correct": total_correct,
        "accuracy_pct": overall_accuracy,
        "total_duration_sec": total_duration,
        "avg_latency_ms": sum(r["duration_ms"] for r in results) / len(results) if results else 0.0,
        "category_metrics": {},
        "difficulty_metrics": {},
        "failures": [r for r in results if not r["is_correct"]]
    }

    for cat, s in category_stats.items():
        acc = (s["correct"] / s["total"] * 100.0) if s["total"] else 0.0
        avg_lat = sum(s["latencies"]) / len(s["latencies"]) if s["latencies"] else 0.0
        report["category_metrics"][cat] = {
            "total": s["total"],
            "correct": s["correct"],
            "accuracy_pct": acc,
            "avg_latency_ms": avg_lat,
            "failure_count": len(s["failures"])
        }

    for diff, s in difficulty_stats.items():
        acc = (s["correct"] / s["total"] * 100.0) if s["total"] else 0.0
        avg_lat = sum(s["latencies"]) / len(s["latencies"]) if s["latencies"] else 0.0
        report["difficulty_metrics"][diff] = {
            "total": s["total"],
            "correct": s["correct"],
            "accuracy_pct": acc,
            "avg_latency_ms": avg_lat
        }

    if verbose:
        print("\n" + "=" * 70)
        print("  EVALUATION SUMMARY REPORT")
        print("=" * 70)
        print(f"Overall Accuracy:  {total_correct}/{len(items)} ({overall_accuracy:.1f}%)")
        print(f"Average Latency:   {report['avg_latency_ms']:.1f} ms / query")
        print(f"Total Benchmark:   {total_duration:.2f} s")
        print("-" * 70)
        print(f"{'Category':<18} {'Correct':<10} {'Total':<8} {'Accuracy':<10} {'Avg Latency'}")
        print("-" * 70)
        for cat, m in report["category_metrics"].items():
            print(f"{cat:<18} {m['correct']:<10} {m['total']:<8} {m['accuracy_pct']:>5.1f}%     {m['avg_latency_ms']:>6.1f}ms")
        print("-" * 70)
        print(f"{'Difficulty':<18} {'Correct':<10} {'Total':<8} {'Accuracy':<10} {'Avg Latency'}")
        print("-" * 70)
        for diff, m in report["difficulty_metrics"].items():
            print(f"{diff:<18} {m['correct']:<10} {m['total']:<8} {m['accuracy_pct']:>5.1f}%     {m['avg_latency_ms']:>6.1f}ms")
        print("=" * 70)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghostline AI Accuracy Benchmark")
    parser.add_argument("--dataset", choices=["dev", "heldout", "all"], default="dev", help="Dataset to evaluate")
    parser.add_argument("--model", type=str, default=None, help="Ollama model to evaluate")
    parser.add_argument("--output", type=str, default=None, help="Path to save JSON benchmark results")
    args = parser.parse_args()

    rep = run_benchmark(dataset_name=args.dataset, model_name=args.model)
    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2)
        print(f"[*] Benchmark report written to {args.output}")
