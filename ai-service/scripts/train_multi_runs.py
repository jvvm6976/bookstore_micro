#!/usr/bin/env python3
"""
Multi-run training coordinator: RNN, LSTM, BiLSTM (3 runs each)
Collects all results and selects best model by avg F1-score
"""
import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

MODELS = ["rnn", "lstm", "bilstm"]
RUNS = 3


def run_command(cmd: list) -> dict:
    """Execute command and parse JSON output"""
    print(f"\n{'='*70}")
    print(f"RUN: {' '.join(cmd)}")
    print(f"{'='*70}")
    
    try:
        # Set PYTHONPATH to /app for module imports
        import os
        env = os.environ.copy()
        env['PYTHONPATH'] = '/app'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd='/app', env=env)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)
        
        if result.returncode != 0:
            print(f"❌ Command failed with code {result.returncode}")
            return {}
        
        return {}
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return {}


def read_model_results(model_name: str) -> dict:
    """Read model metrics from meta file"""
    meta_path = ARTIFACTS_DIR / f"{model_name}_model_meta.json"
    if not meta_path.exists():
        print(f"⚠ {meta_path} not found")
        return {}
    
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Error reading {meta_path}: {e}", file=sys.stderr)
        return {}


def main():
    print("\n" + "="*70)
    print("MULTI-RUN TRAINING: RNN + LSTM + BiLSTM (3 runs each)")
    print("="*70)
    
    all_runs = {model: {"runs": []} for model in MODELS}
    
    # Run each model 3 times
    for model in MODELS:
        print(f"\n{'#'*70}")
        print(f"# TRAINING {model.upper()} - 3 RUNS")
        print(f"{'#'*70}\n")
        
        for run_num in range(1, RUNS + 1):
            print(f"\n>>> RUN {run_num}/{RUNS} for {model.upper()}")
            
            # Run directly as script with PYTHONPATH set
            script_path = BASE_DIR / "app" / "ml" / f"train_{model}.py"
            cmd = [sys.executable, str(script_path)]
            env = os.environ.copy()
            env['PYTHONPATH'] = str(BASE_DIR)
            
            print(f"\n{'='*70}")
            print(f"RUN: {' '.join(cmd)}")
            print(f"{'='*70}")
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env, cwd=str(BASE_DIR))
                print(result.stdout)
                if result.stderr:
                    print("STDERR:", result.stderr, file=sys.stderr)
            except Exception as e:
                print(f"❌ Error: {e}", file=sys.stderr)
            
            # Read results from meta file
            meta = read_model_results(model)
            if meta:
                metrics = meta.get("metrics", {})
                print(f"\n✓ {model.upper()} Run {run_num} completed:")
                print(f"  - F1-Score: {metrics.get('f1_score', 'N/A'):.4f}" if 'f1_score' in metrics else f"  - F1-Score: N/A")
                print(f"  - Accuracy: {metrics.get('accuracy', 'N/A'):.4f}" if 'accuracy' in metrics else f"  - Accuracy: N/A")
                all_runs[model]["runs"].append(metrics)
            else:
                print(f"⚠ Could not read metrics for {model} run {run_num}")
                all_runs[model]["runs"].append({})
    
    # Calculate averages
    print(f"\n{'='*70}")
    print("SUMMARY OF ALL RUNS")
    print(f"{'='*70}\n")
    
    results_summary = {}
    for model in MODELS:
        runs = all_runs[model]["runs"]
        if runs and any(runs):
            f1_scores = [r.get("f1_score", 0) for r in runs if r]
            accuracies = [r.get("accuracy", 0) for r in runs if r]
            
            avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0
            avg_acc = sum(accuracies) / len(accuracies) if accuracies else 0
            
            results_summary[model] = {
                "runs": runs,
                "avg_f1": avg_f1,
                "avg_accuracy": avg_acc,
                "num_runs": len([r for r in runs if r])
            }
            
            print(f"{model.upper()}:")
            print(f"  Runs completed: {results_summary[model]['num_runs']}/{RUNS}")
            print(f"  Avg F1-Score: {avg_f1:.4f}")
            print(f"  Avg Accuracy: {avg_acc:.4f}")
            if runs:
                for i, r in enumerate(runs, 1):
                    if r:
                        print(f"    Run {i}: F1={r.get('f1_score', 0):.4f}, Acc={r.get('accuracy', 0):.4f}")
        else:
            print(f"{model.upper()}: ❌ NO RUNS COMPLETED")
    
    # Select best model by avg F1
    best_model = max(results_summary.items(), 
                    key=lambda x: x[1].get("avg_f1", 0),
                    default=(None, {}))[0]
    
    print(f"\n{'='*70}")
    print(f"MODEL SELECTION")
    print(f"{'='*70}")
    print(f"Best model (by avg F1-score): {best_model.upper() if best_model else 'NONE'}")
    if best_model:
        print(f"  Avg F1: {results_summary[best_model]['avg_f1']:.4f}")
    
    # Save full results
    multi_run_report = {
        "timestamp": datetime.now().isoformat(),
        "training_config": {
            "epochs": 15,
            "batch_size": 64,
            "learning_rate": 0.001,
            "runs_per_model": RUNS
        },
        "models": results_summary,
        "best_model": best_model
    }
    
    report_path = ARTIFACTS_DIR / "multi_run_training_report.json"
    report_path.write_text(json.dumps(multi_run_report, indent=2), encoding="utf-8")
    print(f"\n✓ Multi-run report saved: {report_path}")
    
    # Evaluate all models
    print(f"\n{'='*70}")
    print("RUNNING FULL EVALUATION")
    print(f"{'='*70}\n")
    evaluate_script = BASE_DIR / "app" / "ml" / "evaluate_models.py"
    env = os.environ.copy()
    env['PYTHONPATH'] = str(BASE_DIR)
    subprocess.run([sys.executable, str(evaluate_script)], env=env, cwd=str(BASE_DIR))
    
    # Select best
    print(f"\n{'='*70}")
    print("SELECTING BEST MODEL")
    print(f"{'='*70}\n")
    select_script = BASE_DIR / "app" / "ml" / "select_best_model.py"
    subprocess.run([sys.executable, str(select_script)], env=env, cwd=str(BASE_DIR))
    
    print(f"\n{'='*70}")
    print("✓ TRAINING PIPELINE COMPLETED")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
