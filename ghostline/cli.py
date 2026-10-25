import sys
import os
from pathlib import Path

# Add parent directory to sys.path if run directly
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

import argparse
import time
from PIL import Image

from ghostline.config import load_config, save_config, get_config_path
from ghostline.core.ocr_engine import run_native_ocr, parse_question_structure, get_win_ocr_binary_path
from ghostline.core.llm_client import OllamaClient
from ghostline.core.pipeline import GhostlinePipeline

def cmd_status(args):
    config = load_config()
    client = OllamaClient(base_url=config.ollama_url)
    
    print("\n=== Ghostline System Diagnostics ===")
    print(f"[*] Configuration Path: {get_config_path()}")
    print(f"[*] Configured Model:   {config.model_name}")
    print(f"[*] Ollama Endpoint:    {config.ollama_url}")
    
    ollama_ok = client.is_available()
    print(f"[*] Ollama Status:      {'ONLINE (Localhost)' if ollama_ok else 'OFFLINE (Not reachable)'}")
    
    if ollama_ok:
        models = client.list_models()
        print(f"[*] Installed Models:   {', '.join(models) if models else 'None'}")
        has_target = any(config.model_name in m for m in models)
        print(f"[*] Target Model Ready: {'YES' if has_target else 'NO (Run: ollama pull ' + config.model_name + ')'}")
    
    # Test OCR binary
    try:
        bin_p = get_win_ocr_binary_path()
        print(f"[*] Windows OCR Binary: {bin_p} (EXISTS)")
    except Exception as e:
        print(f"[!] Windows OCR Binary: ERROR ({e})")

def cmd_solve_image(args):
    path = Path(args.image_path)
    if not path.exists():
        print(f"Error: Image not found: {path}")
        return 1
        
    config = load_config()
    pipeline = GhostlinePipeline(model_name=args.model or config.model_name)
    
    print(f"\n[*] Processing image: {path.name}")
    print(f"[*] Model: {pipeline.model_name}")
    
    img = Image.open(path)
    res = pipeline.process_from_image(img)
    
    print("\n--- Recognized Question ---")
    print(res.parsed_question.question_text)
    if res.parsed_question.options:
        print("Options:")
        for k, v in res.parsed_question.options.items():
            print(f"  {k}) {v}")
            
    print("\n--- Local AI Solution ---")
    print(f"Answer: {res.answer_result.answer_option}")
    print(f"Explanation:\n{res.answer_result.explanation}")
    
    print("\n--- Latency Breakdown ---")
    print(f"  OCR Extraction: {res.ocr_time_ms:.1f} ms")
    print(f"  Local AI Solve: {res.llm_time_ms:.1f} ms")
    print(f"  Total Pipeline: {res.total_time_ms:.1f} ms")
    return 0

def cmd_benchmark(args):
    config = load_config()
    client = OllamaClient(base_url=config.ollama_url)
    if not client.is_available():
        print("Error: Ollama daemon is offline.")
        return 1
        
    models = client.list_models()
    print(f"\n=== Benchmarking Local Models on RTX 4050 ===")
    
    test_q = "What is the capital of France?\nA) London\nB) Berlin\nC) Paris\nD) Madrid"
    test_opts = {"A": "London", "B": "Berlin", "C": "Paris", "D": "Madrid"}
    
    for m in models:
        print(f"\nTesting model: {m}...")
        t0 = time.perf_counter()
        res = client.solve_question(test_q, test_opts, model=m)
        dur = (time.perf_counter() - t0) * 1000.0
        print(f"  Selection:   {res.answer_option}")
        print(f"  Confidence:  {res.confidence}")
        print(f"  Latency:     {dur:.1f} ms")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Ghostline CLI Diagnostic & Solver Tool")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("status", help="Check local environment, GPU, and model status")
    
    solve_p = subparsers.add_parser("solve-image", help="Solve question in an image file")
    solve_p.add_argument("image_path", help="Path to screenshot or question image")
    solve_p.add_argument("--model", help="Override Ollama model")
    
    subparsers.add_parser("benchmark", help="Benchmark installed Ollama models")
    
    args = parser.parse_args()
    if args.command == "status":
        cmd_status(args)
    elif args.command == "solve-image":
        sys.exit(cmd_solve_image(args))
    elif args.command == "benchmark":
        sys.exit(cmd_benchmark(args))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
