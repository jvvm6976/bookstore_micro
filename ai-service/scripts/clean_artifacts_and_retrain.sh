#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${SERVICE_ROOT}"

echo "[clean] Removing ML artifacts..."
rm -f artifacts/rnn_model.pt \
      artifacts/lstm_model.pt \
      artifacts/bilstm_model.pt \
      artifacts/model_best.pt \
      artifacts/rnn_model_meta.json \
      artifacts/lstm_model_meta.json \
      artifacts/bilstm_model_meta.json \
      artifacts/model_best_meta.json \
      artifacts/model_best_summary.json \
      artifacts/all_model_results.json \
      artifacts/metrics_report.json \
      artifacts/metrics_report.csv

rm -f artifacts/plots/training_loss.png \
      artifacts/plots/validation_loss.png \
      artifacts/plots/accuracy_comparison.png \
      artifacts/plots/model_comparison_bar.png

echo "[run] Regenerating dataset..."
python scripts/generate_data_user500.py

echo "[run] Training RNN/LSTM/biLSTM..."
python -m app.ml.evaluate_models

echo "[run] Selecting model_best..."
python -m app.ml.select_best_model

echo "[done] Clean retrain completed."
