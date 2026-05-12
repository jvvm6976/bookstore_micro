#!/usr/bin/env python3
"""
Generate mock model artifacts for pipeline testing.
Creates dummy model files so pipeline can run end-to-end without PyTorch.
"""
import json
from pathlib import Path

def create_mock_artifacts():
    base_dir = Path(__file__).resolve().parents[1]
    artifacts_dir = base_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    
    # ============ Mock model metrics ============
    mock_results = [
        {
            "model_name": "rnn",
            "model_type": "RNN",
            "model_path": str(artifacts_dir / "rnn_model.pt"),
            "metrics": {
                "accuracy": 0.445,
                "precision": 0.382,
                "recall": 0.321,
                "f1_score": 0.077,
                "confusion_matrix": [[100, 50, 40, 30], [40, 85, 35, 40], [30, 35, 90, 45], [25, 40, 50, 85]]
            },
            "meta": {
                "epochs_trained": 15,
                "batch_size": 64,
                "learning_rate": 0.001,
                "device": "cpu"
            }
        },
        {
            "model_name": "lstm",
            "model_type": "LSTM",
            "model_path": str(artifacts_dir / "lstm_model.pt"),
            "metrics": {
                "accuracy": 0.438,
                "precision": 0.375,
                "recall": 0.310,
                "f1_score": 0.074,
                "confusion_matrix": [[98, 52, 42, 32], [42, 82, 38, 42], [32, 38, 88, 48], [28, 42, 52, 82]]
            },
            "meta": {
                "epochs_trained": 15,
                "batch_size": 64,
                "learning_rate": 0.001,
                "device": "cpu"
            }
        },
        {
            "model_name": "bilstm",
            "model_type": "biLSTM",
            "model_path": str(artifacts_dir / "bilstm_model.pt"),
            "metrics": {
                "accuracy": 0.428,
                "precision": 0.365,
                "recall": 0.300,
                "f1_score": 0.071,
                "confusion_matrix": [[95, 55, 45, 35], [45, 80, 40, 45], [35, 40, 85, 50], [30, 45, 55, 80]]
            },
            "meta": {
                "epochs_trained": 15,
                "batch_size": 64,
                "learning_rate": 0.001,
                "device": "cpu"
            }
        }
    ]
    
    # ============ Save model results ============
    (artifacts_dir / "all_model_results.json").write_text(
        json.dumps(mock_results, indent=2),
        encoding="utf-8"
    )
    print("✓ all_model_results.json created")
    
    # ============ Select best (highest F1) ============
    best = sorted(mock_results, key=lambda r: r["metrics"]["f1_score"], reverse=True)[0]
    
    best_summary = {
        "model_best": best["model_name"],
        "model_type": best["model_type"],
        "metrics": best["metrics"],
        "reason": "model_best is selected by highest F1-score on test set; if tied, higher accuracy wins."
    }
    
    (artifacts_dir / "model_best_summary.json").write_text(
        json.dumps(best_summary, indent=2),
        encoding="utf-8"
    )
    print(f"✓ model_best_summary.json created (selected: {best['model_name']})")
    
    # ============ Create dummy .pt files ============
    # PyTorch uses pickle format, but for testing we just create empty files
    for result in mock_results:
        model_path = Path(result["model_path"])
        model_path.write_text("MOCK_MODEL", encoding="utf-8")
        print(f"✓ {model_path.name} created")
    
    # Copy best to model_best.pt
    best_model_path = artifacts_dir / best["model_path"].split("/")[-1]
    (artifacts_dir / "model_best.pt").write_text("MOCK_MODEL", encoding="utf-8")
    print("✓ model_best.pt created (copy of best model)")
    
    # ============ Metrics files ============
    metrics_report = {
        "dataset": {
            "total_samples": 4891,
            "train_samples": 3424,
            "val_samples": 517,
            "test_samples": 950,
            "num_classes": 8
        },
        "models": [
            {
                "name": r["model_name"],
                "type": r["model_type"],
                "metrics": r["metrics"]
            }
            for r in mock_results
        ],
        "best_model": best["model_name"],
        "training_config": {
            "epochs": 15,
            "batch_size": 64,
            "learning_rate": 0.001,
            "optimizer": "Adam",
            "loss": "CrossEntropyLoss"
        }
    }
    
    (artifacts_dir / "metrics_report.json").write_text(
        json.dumps(metrics_report, indent=2),
        encoding="utf-8"
    )
    print("✓ metrics_report.json created")
    
    # ============ CSV export ============
    csv_content = "Model,Accuracy,Precision,Recall,F1-Score\n"
    for result in mock_results:
        m = result["metrics"]
        csv_content += f"{result['model_name']},{m['accuracy']},{m['precision']},{m['recall']},{m['f1_score']}\n"
    
    (artifacts_dir / "metrics_report.csv").write_text(csv_content, encoding="utf-8")
    print("✓ metrics_report.csv created")
    
    # ============ Meta files ============
    for result in mock_results:
        meta_path = artifacts_dir / f"{result['model_name']}_model_meta.json"
        meta = {
            "model_name": result["model_name"],
            "model_type": result["model_type"],
            "metrics": result["metrics"],
            "meta": result["meta"]
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"✓ {meta_path.name} created")
    
    model_best_meta = {
        "model_name": best["model_name"],
        "model_type": best["model_type"],
        "metrics": best["metrics"],
        "selection_reason": "Highest F1-score on test set",
        "selected_from": [r["model_name"] for r in mock_results]
    }
    (artifacts_dir / "model_best_meta.json").write_text(
        json.dumps(model_best_meta, indent=2),
        encoding="utf-8"
    )
    print("✓ model_best_meta.json created")
    
    # ============ Plot placeholder files ============
    plots_dir = artifacts_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    
    plot_files = [
        "training_loss.png",
        "validation_loss.png",
        "accuracy_comparison.png",
        "model_comparison_bar.png"
    ]
    
    for plot_file in plot_files:
        (plots_dir / plot_file).write_text("PNG_PLACEHOLDER", encoding="utf-8")
        print(f"✓ plots/{plot_file} created")
    
    # ============ Final summary ============
    print("\n" + "="*60)
    print("✅ MOCK ARTIFACTS GENERATED SUCCESSFULLY")
    print("="*60)
    print(f"\nLocation: {artifacts_dir}")
    print(f"\nGenerated files:")
    print(f"  • 3 model checkpoints (.pt files)")
    print(f"  • all_model_results.json")
    print(f"  • model_best.pt (copy of {best['model_name']})")
    print(f"  • model_best_summary.json")
    print(f"  • metrics_report.json & .csv")
    print(f"  • 3 meta files for each model")
    print(f"  • 4 plot placeholders")
    print(f"\n✓ Pipeline can now run without PyTorch!")
    print(f"✓ Ready to test recommendation flow")
    print(f"✓ Ready to test Neo4j integration")

if __name__ == "__main__":
    create_mock_artifacts()
