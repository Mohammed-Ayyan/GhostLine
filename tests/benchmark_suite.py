import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict

app_dir = Path(__file__).resolve().parent.parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from ghostline.core.llm_client import OllamaClient

# Reproducible Labeled Benchmark Dataset (10 Ground-Truth Questions)
DATASET = [
    {
        "question": "What is the primary function of ribosomes in a biological cell?",
        "options": {
            "A": "DNA replication",
            "B": "Protein synthesis",
            "C": "Lipid storage",
            "D": "ATP generation"
        },
        "ground_truth": "B"
    },
    {
        "question": "In Python, which built-in data type is immutable?",
        "options": {
            "A": "List",
            "B": "Dictionary",
            "C": "Tuple",
            "D": "Set"
        },
        "ground_truth": "C"
    },
    {
        "question": "What is the speed of light in a vacuum (approximately)?",
        "options": {
            "A": "300,000 km/s",
            "B": "150,000 km/s",
            "C": "3,000 km/s",
            "D": "30,000 km/s"
        },
        "ground_truth": "A"
    },
    {
        "question": "Which layer of the OSI model is responsible for routing packets across networks?",
        "options": {
            "A": "Data Link Layer",
            "B": "Transport Layer",
            "C": "Network Layer",
            "D": "Session Layer"
        },
        "ground_truth": "C"
    },
    {
        "question": "What is the chemical formula for table salt?",
        "options": {
            "A": "KCl",
            "B": "NaCl",
            "C": "CaCl2",
            "D": "NaOH"
        },
        "ground_truth": "B"
    },
    {
        "question": "What is the output of 3 * 2 ** 3 in standard operator precedence?",
        "options": {
            "A": "216",
            "B": "18",
            "C": "24",
            "D": "72"
        },
        "ground_truth": "C"
    },
    {
        "question": "Which of the following is a symmetric key encryption algorithm?",
        "options": {
            "A": "RSA",
            "B": "AES",
            "C": "ECC",
            "D": "Diffie-Hellman"
        },
        "ground_truth": "B"
    },
    {
        "question": "Which gas is most abundant in Earth's atmosphere?",
        "options": {
            "A": "Oxygen",
            "B": "Carbon Dioxide",
            "C": "Nitrogen",
            "D": "Argon"
        },
        "ground_truth": "C"
    },
    {
        "question": "In database normalization, which normal form eliminates transitive dependencies?",
        "options": {
            "A": "1NF",
            "B": "2NF",
            "C": "3NF",
            "D": "BCNF"
        },
        "ground_truth": "C"
    },
    {
        "question": "What is the time complexity of searching in a balanced Binary Search Tree (AVL tree)?",
        "options": {
            "A": "O(1)",
            "B": "O(n)",
            "C": "O(log n)",
            "D": "O(n log n)"
        },
        "ground_truth": "C"
    }
]

def run_benchmark(model_name: str, warmup_runs: int = 2):
    client = OllamaClient(default_model=model_name)
    if not client.is_available():
        print(f"Error: Ollama daemon not reachable at {client.base_url}")
        return None

    print(f"\n=======================================================")
    print(f"  BENCHMARK: {model_name}")
    print(f"  Hardware: NVIDIA GeForce RTX 4050 6GB, 16GB RAM")
    print(f"  Dataset Size: {len(DATASET)} questions")
    print(f"  Warmup Runs:  {warmup_runs}")
    print(f"=======================================================")

    # Warmup runs
    for w in range(warmup_runs):
        print(f"[*] Executing Warmup Run {w+1}/{warmup_runs}...")
        client.solve_question("What is 2+2?\nA) 3\nB) 4", {"A": "3", "B": "4"}, model=model_name)

    latencies = []
    correct_count = 0

    print(f"[*] Executing Measured Benchmark ({len(DATASET)} labeled items)...")
    for idx, item in enumerate(DATASET):
        t0 = time.perf_counter()
        res = client.solve_question(item["question"], item["options"], model=model_name)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(latency_ms)

        is_correct = (res.answer_option.upper() == item["ground_truth"])
        if is_correct:
            correct_count += 1

        print(f"  [{idx+1:02d}/10] Expected: {item['ground_truth']} | Got: {res.answer_option:^3} | {latency_ms:6.1f} ms | {'PASS' if is_correct else 'FAIL'}")

    accuracy = (correct_count / len(DATASET)) * 100.0
    median_lat = statistics.median(latencies)
    sorted_lats = sorted(latencies)
    p95_idx = int(len(sorted_lats) * 0.95)
    p95_lat = sorted_lats[min(p95_idx, len(sorted_lats) - 1)]

    summary = {
        "model": model_name,
        "sample_count": len(DATASET),
        "warmup_runs": warmup_runs,
        "correct": correct_count,
        "accuracy_pct": accuracy,
        "median_ms": median_lat,
        "p95_ms": p95_lat,
        "min_ms": min(latencies),
        "max_ms": max(latencies)
    }

    print("\n--- Benchmark Summary ---")
    print(f"  Accuracy:   {accuracy:.1f}% ({correct_count}/{len(DATASET)})")
    print(f"  Median Lat: {median_lat:.1f} ms")
    print(f"  P95 Lat:    {p95_lat:.1f} ms")
    print(f"  Min Lat:    {min(latencies):.1f} ms")
    print(f"  Max Lat:    {max(latencies):.1f} ms")
    return summary

if __name__ == "__main__":
    s1 = run_benchmark("phi3:mini", warmup_runs=2)
    s2 = run_benchmark("qwen2.5:0.5b", warmup_runs=2)
