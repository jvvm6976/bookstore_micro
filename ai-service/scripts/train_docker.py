#!/usr/bin/env python3
"""
Multi-run training in Docker (RNN + LSTM + BiLSTM, 3 runs each)
Run from /app directory
"""
import json
import shutil
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# In Docker, /app is the working directory
os.chdir('/app')
sys.path.insert(0, '/app')

ARTIFACTS_DIR = Path('/app/artifacts')
ARTIFACTS_DIR.mkdir(exist_ok=True)

MODELS = ["rnn", "lstm", "bilstm"]
RUNS = 3
BASE_SEED = 42

print("\n" + "="*70)
print("MULTI-RUN TRAINING: RNN + LSTM + BiLSTM (3 runs each)")
print("="*70)

all_runs = {model: {"runs": []} for model in MODELS}

# Train each model 3 times
for model in MODELS:
    print(f"\n{'#'*70}")
    print(f"# TRAINING {model.upper()} - 3 RUNS")
    print(f"{'#'*70}\n")
    
    for run_num in range(1, RUNS + 1):
        print(f"\n>>> RUN {run_num}/{RUNS} for {model.upper()}")
        run_seed = BASE_SEED + (run_num - 1)
        
        cmd = [sys.executable, "-m", f"app.ml.train_{model}"]
        
        print(f"\n{'='*70}")
        print(f"CMD: {' '.join(cmd)}")
        print(f"CWD: /app")
        print(f"{'='*70}\n")
        
        try:
            env = os.environ.copy()
            env["TRAIN_SEED"] = str(run_seed)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd='/app', env=env)
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr, file=sys.stderr)
            
            if result.returncode == 0:
                # Read metrics
                meta_path = ARTIFACTS_DIR / f"{model}_model_meta.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    metrics = meta.get("metrics", {})
                    print(f"\n✓ {model.upper()} Run {run_num}:")
                    print(f"  Seed: {run_seed}")
                    print(f"  Precision: {metrics.get('precision', 0):.4f}")
                    print(f"  Recall: {metrics.get('recall', 0):.4f}")
                    print(f"  F1: {metrics.get('f1_score', 0):.4f}")
                    print(f"  Acc: {metrics.get('accuracy', 0):.4f}")
                    all_runs[model]["runs"].append(metrics)
                else:
                    print(f"⚠ No metrics file for {model} run {run_num}")
                    all_runs[model]["runs"].append({})
            else:
                print(f"❌ Training failed for {model} run {run_num}")
                all_runs[model]["runs"].append({})
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            all_runs[model]["runs"].append({})

# Summary
print(f"\n{'='*70}")
print("TRAINING SUMMARY")
print(f"{'='*70}\n")

results_summary = {}
for model in MODELS:
    runs = all_runs[model]["runs"]
    if runs and any(runs):
        f1_scores = [r.get("f1_score", 0) for r in runs if r]
        accuracies = [r.get("accuracy", 0) for r in runs if r]
        precisions = [r.get("precision", 0) for r in runs if r]
        recalls = [r.get("recall", 0) for r in runs if r]
        
        avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0
        avg_acc = sum(accuracies) / len(accuracies) if accuracies else 0
        avg_precision = sum(precisions) / len(precisions) if precisions else 0
        avg_recall = sum(recalls) / len(recalls) if recalls else 0
        
        results_summary[model] = {
            "runs": runs,
            "avg_f1": avg_f1,
            "avg_accuracy": avg_acc,
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "num_runs": len([r for r in runs if r])
        }
        
        print(f"{model.upper()}:")
        print(f"  Completed runs: {results_summary[model]['num_runs']}/{RUNS}")
        print(f"  Avg Precision: {avg_precision:.4f}")
        print(f"  Avg Recall: {avg_recall:.4f}")
        print(f"  Avg F1-Score: {avg_f1:.4f}")
        print(f"  Avg Accuracy: {avg_acc:.4f}")
        if runs:
            for i, r in enumerate(runs, 1):
                if r:
                    print(
                        f"    Run {i}: "
                        f"P={r.get('precision', 0):.4f}, "
                        f"R={r.get('recall', 0):.4f}, "
                        f"F1={r.get('f1_score', 0):.4f}, "
                        f"Acc={r.get('accuracy', 0):.4f}"
                    )
        else:
            print(f"  ⚠ No successful runs")
    else:
        print(f"{model.upper()}: ❌ NO RUNS COMPLETED")

# Save results
best_model = (
    max(
        results_summary.items(),
        key=lambda x: (x[1].get("avg_f1", 0), x[1].get("avg_accuracy", 0)),
        default=(None, {}),
    )[0]
    if results_summary
    else None
)

multi_run_report = {
    "timestamp": datetime.now().isoformat(),
    "training_config": {
        "epochs": 15,
        "batch_size": 64,
        "learning_rate": 0.001,
        "runs_per_model": RUNS
    },
    "models": results_summary,
    "best_model_preliminary": best_model
}

report_path = ARTIFACTS_DIR / "multi_run_training_report.json"
report_path.write_text(json.dumps(multi_run_report, indent=2), encoding="utf-8")
print(f"\n✓ Report: {report_path}")

# Final best-model materialization from multi-run average criteria
print(f"\n{'='*70}")
print("BEST MODEL SELECTION (AVG F1 -> AVG ACC)")
print(f"{'='*70}\n")

if best_model:
    src_model = ARTIFACTS_DIR / f"{best_model}_model.pt"
    dst_model = ARTIFACTS_DIR / "model_best.pt"
    if src_model.exists():
        shutil.copyfile(src_model, dst_model)

    best_summary = {
        "model_best": best_model,
        "model_type": best_model,
        "metrics_avg": {
            "precision": results_summary[best_model].get("avg_precision", 0),
            "recall": results_summary[best_model].get("avg_recall", 0),
            "f1_score": results_summary[best_model].get("avg_f1", 0),
            "accuracy": results_summary[best_model].get("avg_accuracy", 0),
        },
        "num_runs": results_summary[best_model].get("num_runs", 0),
        "reason": "Selected by highest AVG F1-score across runs; if tie, highest AVG accuracy.",
    }
    (ARTIFACTS_DIR / "model_best_summary.json").write_text(
        json.dumps(best_summary, indent=2), encoding="utf-8"
    )
    print(f"✓ model_best: {best_model}")
    print(
        f"  Avg P={best_summary['metrics_avg']['precision']:.4f}, "
        f"Avg R={best_summary['metrics_avg']['recall']:.4f}, "
        f"Avg F1={best_summary['metrics_avg']['f1_score']:.4f}, "
        f"Avg Acc={best_summary['metrics_avg']['accuracy']:.4f}"
    )

# Evaluate all (kept for reports/plots only)
print(f"\n{'='*70}")
print("EVALUATION & MODEL SELECTION")
print(f"{'='*70}\n")

subprocess.run([sys.executable, "-m", "app.ml.evaluate_models"], cwd='/app')
print("✓ Skip single-run select_best_model to avoid overriding multi-run best")

print(f"\n{'='*70}")
print("✓ TRAINING PIPELINE COMPLETED")
print(f"{'='*70}\n")
