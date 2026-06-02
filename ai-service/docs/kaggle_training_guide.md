# Kaggle Training Guide (5 Models, 5 Real Datasets)

Guide nay dung de train AI model tren Kaggle khi may local khong du tai nguyen.

## 1. Muc tieu

- Train 5 models: RNN, LSTM, BiLSTM, GRU, BiGRU
- Train tren 5 datasets thuc tu Kaggle
- Sinh nhieu bieu do so sanh trong `artifacts/plots`
- Xuat `model_best.pt` + `model_best_meta.json` de dung ngay cho runtime ecommerce
- Giu nguyen flow hien tai: Knowledge Graph + RAG + Chat + Recommend

## 2. File da san sang trong repo

- Script train tren Kaggle: `scripts/kaggle_train_notebook.py`
- Script copy artifact ve runtime: `scripts/apply_kaggle_artifacts.py`
- Runtime predictor da ho tro 5 model type (rnn/lstm/bilstm/gru/bigru): `app/ml/preprocess.py`

## 3. Tao notebook Kaggle

1. Tao notebook Python moi tren Kaggle.
2. Bat GPU (`Settings -> Accelerator -> GPU`).
3. Add dataset vao notebook:
   - RetailRocket eCommerce dataset
   - eCommerce behavior data from multi category store
  - Instacart Market Basket Analysis
  - H&M Personalized Fashion Recommendations
  - Olist Brazilian E-Commerce

Neu ban muon du 5 bo lon va de tim hon, uu tien bo sau:

- retailrocket/ecommerce-dataset
- mkechinov/ecommerce-behavior-data-from-multi-category-store
- olistbr/brazilian-ecommerce
- Instacart Market Basket Analysis (competition data)
- H&M Personalized Fashion Recommendations (competition data)

Tu khoa tim trong Add Data:

- "retailrocket ecommerce dataset"
- "multi category store behavior"
- "olist brazilian ecommerce"
- "instacart market basket analysis"
- "h and m personalized fashion recommendations"
4. Upload file `scripts/kaggle_train_notebook.py` vao `/kaggle/working/`.

## 4. Chay train tren Kaggle

Trong mot code cell:

```bash
!python /kaggle/working/kaggle_train_notebook.py
```

Lenh khuyen nghi de train nhanh nhung van dung quy trinh:

```bash
!python /kaggle/working/kaggle_train_notebook.py --mode balanced
```

Neu can nhanh hon nua (de test luong):

```bash
!python /kaggle/working/kaggle_train_notebook.py --mode quick
```

Neu muon day du, co the lau hon:

```bash
!python /kaggle/working/kaggle_train_notebook.py --mode full
```

Script se tu dong:

- Detect dataset path kha dung
- Chuan hoa schema ve format sequence chung
- Train 5 models tren tung dataset
- Tinh metrics: accuracy, precision, recall, macro-f1, roc-auc, pr-auc, train/val loss, generalization gap
- Chon best model theo:
  - avg_macro_f1 (primary)
  - avg_pr_auc, avg_roc_auc (tie-break)
  - lower generalization gap (tie-break)
- Retrain best model tren merged datasets
- Xuat artifact deploy

Quy tac split va train:

- Moi dataset duoc chia stratified: 70% train, 15% val, 15% test
- Test chi dung de danh gia sau khi model da train xong
- 5 model cung hoc tren cung mot bo train/val/test cua tung dataset
- Callback chong overfit: EarlyStopping (patience=5), ReduceLROnPlateau, dropout, weight_decay, gradient clipping

Hyperparameters mac dinh trong script:

- QUICK_EPOCHS = 10
- FULL_EPOCHS = 35
- BATCH_SIZE = 256
- LEARNING_RATE = 1e-3
- WEIGHT_DECAY = 1e-4
- DROPOUT = 0.3

Dieu kien so dataset:

- Script bat buoc toi thieu 5 dataset thuc de train chinh thuc
- Neu nap hon 5 dataset, script tu giu top 5 theo so dong

## 5. Dau ra sau khi train

Thu muc `/kaggle/working/artifacts/` co:

- `model_best.pt`
- `model_best_meta.json`
- `model_best_summary.json`
- `all_runs_metrics_raw.json`
- `all_model_results.json`
- `metrics_report.json`
- `dataset_report.json`
- `plots/*.png`

## 6. Danh sach bieu do duoc tao

Trong `artifacts/plots`:

- `avg_accuracy_models.png`
- `avg_macro_f1_models.png`
- `avg_roc_auc_models.png`
- `avg_pr_auc_models.png`
- `avg_generalization_gap_models.png`
- `heatmap_macro_f1.png`
- `heatmap_roc_auc.png`
- `heatmap_pr_auc.png`
- `model_top1_count.png`
- `train_vs_val_scatter_all_runs.png`
- `confusion_matrix_model_best.png`

## 7. Download artifact tu Kaggle

Sau khi run xong:

1. Download folder `/kaggle/working/artifacts` ve may.
2. Dat folder do trong may local (vi du `D:/downloads/kaggle-artifacts`).

## 8. Ap dung best_model vao he thong ecommerce

Chay trong `recommender-ai-service`:

```bash
python scripts/apply_kaggle_artifacts.py --source D:/downloads/kaggle-artifacts
```

Script se copy artifact vao ca:

- `artifacts/`
- `artifacts_final/`

Runtime hien tai cua orchestrator se tu load `artifacts/model_best.pt` va `artifacts/model_best_meta.json`.

## 9. Restart service va verify flow

Sau khi copy artifact:

```bash
docker compose up -d --build recommender-ai-service
```

Verify:

```bash
curl http://localhost:8011/health
curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"message\":\"goi y san pham cho toi\",\"customer_id\":1}"
curl http://localhost:8000/api/v1/recommend/1
```

Hoac verify tu dong:

```bash
python scripts/verify_after_kaggle.py
python scripts/verify_after_kaggle.py --check-api
```

## 10. Overfit control dang dung trong pipeline

- Early stopping (`patience=5`)
- Dropout (`0.3`)
- Weight decay (`1e-4`)
- Class-weighted cross entropy
- ReduceLROnPlateau scheduler
- Gradient clipping (`max_norm=1.0`)
- Stratified split theo label

## 11. Luu y

- Khong can Kubernetes cho buoc nay.
- Knowledge Graph va RAG khong bi anh huong boi viec thay model sequence.
- Neu dataset nao khong mount dung ten tren Kaggle, script se skip dataset do; can add lai dung dataset path de du 5/5.
