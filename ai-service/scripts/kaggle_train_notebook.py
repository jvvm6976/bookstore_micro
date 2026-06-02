"""
Kaggle training pipeline for recommender-ai-service.

Goals:
- Train 5 sequence models: RNN, LSTM, BiLSTM, GRU, BiGRU
- Use 5 real Kaggle datasets: RetailRocket, Multi-Category Store, Instacart, H&M, Olist
- Produce many comparison plots in artifacts/plots
- Export deployable artifacts: model_best.pt, model_best_meta.json, model_best_summary.json

Run on Kaggle notebook:
  1) Add datasets listed in DATASET_CANDIDATE_PATHS.
  2) Open a code cell and run: !python /kaggle/working/kaggle_train_notebook.py
  3) Download /kaggle/working/artifacts and copy files back to repo artifacts/.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ----------------------------
# Configuration
# ----------------------------
SEED = 42
SEQ_LEN = 12
FEATURE_DIM = 13
NUM_CLASSES = 10
MAX_ROWS_PER_DATASET = 450_000
MIN_DATASETS_REQUIRED = 5
QUICK_EPOCHS = 10
FULL_EPOCHS = 35
BATCH_SIZE = 256
LR = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE = 5
DROPOUT = 0.3
HIDDEN_DIM = 128
NUM_LAYERS = 1
USE_AMP = False
NUM_WORKERS = 4
PIN_MEMORY = True

PRESETS = {
    "quick": {
        "max_rows": 200_000,
        "quick_epochs": 6,
        "full_epochs": 18,
        "batch_size": 128,
    },
    "balanced": {
        "max_rows": 350_000,
        "quick_epochs": 8,
        "full_epochs": 25,
        "batch_size": 128,
    },
    "full": {
        "max_rows": 500_000,
        "quick_epochs": 10,
        "full_epochs": 35,
        "batch_size": 256,
    },
}

ACTIONS = [
    "search", "view", "add_to_cart", "purchase", "rate_product",
    "wishlist", "remove_from_cart", "click", "compare", "share",
]
ACTION_TO_ID = {a: i for i, a in enumerate(ACTIONS)}

DATASET_CANDIDATE_PATHS = {
    "retailrocket": [
        "/kaggle/input/ecommerce-dataset/events.csv",
        "/kaggle/input/retailrocket/ecommerce-dataset/events.csv",
    ],
    "multi_category_store": [
        "/kaggle/input/ecommerce-behavior-data-from-multi-category-store/2019-Oct.csv",
        "/kaggle/input/ecommerce-behavior-data-from-multi-category-store/2019-Nov.csv",
        "/kaggle/input/ecommerce-behavior-data-from-multi-category-store/2019-Dec.csv",
    ],
    "instacart": [
        "/kaggle/input/instacart-market-basket-analysis/orders.csv",
    ],
    "hm_fashion": [
        "/kaggle/input/h-and-m-personalized-fashion-recommendations/transactions_train.csv",
        "/kaggle/input/h-and-m-personalized-fashion-recommendations/transactions_train.parquet",
        "/kaggle/input/h-and-m-product-dataset/handm.csv",
    ],
    "olist": [
        "/kaggle/input/brazilian-ecommerce/olist_orders_dataset.csv",
        "/kaggle/input/olistbr-brazilian-ecommerce/olist_orders_dataset.csv",
        "/kaggle/input/datasets/organizations/olistbr/brazilian-ecommerce/olist_orders_dataset.csv",
        "/kaggle/input/datasets/*/olistbr/brazilian-ecommerce/olist_orders_dataset.csv",
        "/kaggle/input/datasets/*/organizations/olistbr/brazilian-ecommerce/olist_orders_dataset.csv",
        "/kaggle/input/*/brazilian-ecommerce/olist_orders_dataset.csv",
    ],
}
DATASET_SEQ_LEN_OVERRIDES = {
    "hm_fashion": 6,
    "olist": 3,
}

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "/kaggle/working/artifacts"))
PLOTS_DIR = ARTIFACTS_DIR / "plots"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DEFAULT_KAGGLE_INPUT_DIR = Path("/kaggle/input")
LOCAL_KAGGLE_CACHE_DIR = Path.home() / ".cache" / "kagglehub" / "datasets"
LOCAL_KAGGLE_COMPETITIONS_DIR = Path.home() / ".cache" / "kagglehub" / "competitions"
KAGGLE_INPUT_DIR = Path(os.getenv("KAGGLE_INPUT_DIR", str(DEFAULT_KAGGLE_INPUT_DIR)))


# ----------------------------
# Utilities
# ----------------------------
def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


@lru_cache(maxsize=1)
def _all_kaggle_input_files() -> tuple[str, ...]:
    roots = [KAGGLE_INPUT_DIR, LOCAL_KAGGLE_CACHE_DIR, LOCAL_KAGGLE_COMPETITIONS_DIR]
    files: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(str(path).replace("\\", "/") for path in root.rglob("*") if path.is_file())
    return tuple(sorted(set(files)))


def resolve_runtime_config() -> dict[str, int | str]:
    parser = argparse.ArgumentParser(description="Kaggle training runner with speed presets")
    parser.add_argument("--mode", choices=["quick", "balanced", "full"], default="balanced")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--quick-epochs", type=int, default=None)
    parser.add_argument("--full-epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--min-datasets", type=int, default=MIN_DATASETS_REQUIRED)
    parser.add_argument("--amp", action="store_true", help="Enable mixed-precision training (torch.cuda.amp)")
    parser.add_argument("--num-workers", type=int, default=None, help="DataLoader num_workers override")
    parser.add_argument("--pin-memory", action="store_true", help="Set DataLoader.pin_memory=True")
    args = parser.parse_args()

    preset = PRESETS[args.mode]
    return {
        "mode": args.mode,
        "max_rows": int(args.max_rows or preset["max_rows"]),
        "quick_epochs": int(args.quick_epochs or preset["quick_epochs"]),
        "full_epochs": int(args.full_epochs or preset["full_epochs"]),
        "batch_size": int(args.batch_size or preset["batch_size"]),
        "min_datasets": int(args.min_datasets),
        "amp": bool(args.amp),
        "num_workers": args.num_workers,
        "pin_memory": bool(args.pin_memory),
    }


def find_existing_path(candidates: list[str]) -> str | None:
    all_input_files = _all_kaggle_input_files()
    for c in candidates:
        if "*" in c:
            import glob
            hits = glob.glob(c, recursive=True)
            if hits:
                return sorted(hits)[0]
        elif os.path.exists(c):
            return c

        normalized = str(Path(c)).replace("\\", "/")
        if "/kaggle/input/" in normalized:
            suffix = normalized.split("/kaggle/input/", 1)[1].lstrip("/")
            suffix_matches = [path for path in all_input_files if path.endswith(suffix)]
            if suffix_matches:
                return sorted(suffix_matches, key=len)[0]

        basename = Path(c).name
        basename_matches = [path for path in all_input_files if Path(path).name == basename]
        if basename_matches:
            return sorted(basename_matches, key=len)[0]
    return None


def default_schema(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    required_cols = [
        "user_id", "session_id", "step", "product_id", "category", "sub_category",
        "action", "timestamp", "price", "rating", "cart_value", "dwell_time",
        "device", "source", "intent", "segment",
    ]
    for c in required_cols:
        if c not in df.columns:
            df[c] = 0

    df["user_id"] = pd.to_numeric(df["user_id"], errors="coerce").fillna(0).astype(int)
    df["session_id"] = pd.to_numeric(df["session_id"], errors="coerce").fillna(0).astype(int)
    df["step"] = pd.to_numeric(df["step"], errors="coerce").fillna(0).astype(int)
    df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce").fillna(0).astype(int)

    for c in ["price", "rating", "cart_value", "dwell_time"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)

    for c in ["category", "sub_category", "action", "timestamp", "device", "source", "intent", "segment"]:
        df[c] = df[c].astype(str)

    df["source"] = source_name
    return df[required_cols]


def stable_hash_series(values: pd.Series, modulo: int) -> pd.Series:
    return (pd.util.hash_pandas_object(values.fillna("").astype(str), index=False).astype("uint64") % modulo).astype("int64")


# ----------------------------
# Dataset adapters
# ----------------------------
def load_retailrocket(max_rows: int) -> pd.DataFrame:
    path = find_existing_path(DATASET_CANDIDATE_PATHS["retailrocket"])
    if not path:
        return pd.DataFrame()
    df = pd.read_csv(path, nrows=max_rows)
    event_map = {"view": "view", "addtocart": "add_to_cart", "transaction": "purchase"}
    df = df[df["event"].isin(event_map)].copy()
    df["action"] = df["event"].map(event_map)
    df["user_id"] = df["visitorid"].astype(int)
    df["session_id"] = df["visitorid"].astype(int)
    df["product_id"] = df["itemid"].astype(int)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms").dt.strftime("%Y-%m-%dT%H:%M:%S")
    df["category"] = "general"
    df["sub_category"] = "general"
    df["price"] = 50.0
    df["rating"] = 0.0
    df["cart_value"] = 0.0
    df["dwell_time"] = 30.0
    df["device"] = "desktop"
    df["intent"] = "browse"
    df["segment"] = "casual"
    df["step"] = df.groupby("session_id").cumcount() + 1
    return default_schema(df, "retailrocket")


def load_multi_category(max_rows: int) -> pd.DataFrame:
    path = find_existing_path(DATASET_CANDIDATE_PATHS["multi_category_store"])
    if not path:
        return pd.DataFrame()
    df = pd.read_csv(path, nrows=max_rows)
    event_map = {
        "view": "view",
        "cart": "add_to_cart",
        "purchase": "purchase",
        "remove_from_cart": "remove_from_cart",
    }
    df = df[df["event_type"].isin(event_map)].copy()
    df["action"] = df["event_type"].map(event_map)
    df["user_id"] = pd.to_numeric(df["user_id"], errors="coerce").fillna(0).astype(int)
    df["session_id"] = stable_hash_series(df["user_session"].astype(str), 100_000_000)
    df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce").fillna(0).astype(int)
    df["timestamp"] = pd.to_datetime(df["event_time"], errors="coerce").fillna(pd.Timestamp("1970-01-01")).dt.strftime("%Y-%m-%dT%H:%M:%S")

    def parse_cat(code: Any) -> str:
        if pd.isna(code):
            return "general"
        return str(code).split(".")[0].replace("_", " ").lower()

    def parse_sub(code: Any) -> str:
        if pd.isna(code):
            return "general"
        parts = str(code).split(".")
        return (parts[1] if len(parts) > 1 else "general").replace("_", " ").lower()

    df["category"] = df["category_code"].apply(parse_cat)
    df["sub_category"] = df["category_code"].apply(parse_sub)
    df["price"] = pd.to_numeric(df.get("price", 0), errors="coerce").fillna(0.0)
    df["rating"] = 0.0
    df["cart_value"] = 0.0
    df["dwell_time"] = 25.0
    df["device"] = "desktop"
    df["intent"] = "browse"
    df["segment"] = "casual"
    df["step"] = df.groupby("session_id").cumcount() + 1
    return default_schema(df, "multi_category_store")


def load_instacart(max_rows: int) -> pd.DataFrame:
    orders_path = find_existing_path(DATASET_CANDIDATE_PATHS["instacart"])
    if not orders_path:
        return pd.DataFrame()

    base = Path(orders_path).parent
    prior_path = base / "order_products__prior.csv"
    products_path = base / "products.csv"

    if not prior_path.exists():
        return pd.DataFrame()

    orders = pd.read_csv(orders_path, usecols=["order_id", "user_id", "order_number", "order_dow", "order_hour_of_day"])
    prior = pd.read_csv(prior_path, nrows=max_rows)
    df = prior.merge(orders, on="order_id", how="left")

    if products_path.exists():
        products = pd.read_csv(products_path, usecols=["product_id", "aisle_id"])
        df = df.merge(products, on="product_id", how="left")
    else:
        df["aisle_id"] = 0

    df["user_id"] = pd.to_numeric(df["user_id"], errors="coerce").fillna(0).astype(int)
    df["order_number"] = pd.to_numeric(df["order_number"], errors="coerce").fillna(0).astype(int)
    df["session_id"] = (df["user_id"].astype(np.int64) * 10000 + df["order_number"].astype(np.int64)).astype(np.int64)
    df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce").fillna(0).astype(int)
    df["step"] = pd.to_numeric(df.get("add_to_cart_order", 1), errors="coerce").fillna(1).astype(int)
    # Build less-degenerate labels: early cart events, then split by reordered signal.
    reordered = pd.to_numeric(df.get("reordered", 0), errors="coerce").fillna(0).astype(int)
    df["action"] = np.where(
        df["step"] <= 2,
        "add_to_cart",
        np.where(reordered == 1, "purchase", "view"),
    )
    df["timestamp"] = (
        "2020-01-" + ((pd.to_numeric(df.get("order_dow", 0), errors="coerce").fillna(0).astype(int) % 28) + 1).astype(str).str.zfill(2)
        + "T" + pd.to_numeric(df.get("order_hour_of_day", 12), errors="coerce").fillna(12).astype(int).astype(str).str.zfill(2)
        + ":00:00"
    )
    df["category"] = "instacart_aisle_" + pd.to_numeric(df.get("aisle_id", 0), errors="coerce").fillna(0).astype(int).astype(str)
    df["sub_category"] = "instacart"
    df["price"] = 0.0
    df["rating"] = 0.0
    df["cart_value"] = 0.0
    df["dwell_time"] = 20.0
    df["device"] = "desktop"
    df["intent"] = "buy"
    df["segment"] = "buyer"
    # Keep event order stable within each session for sequence building.
    df = df.sort_values(["session_id", "step", "product_id"]).reset_index(drop=True)
    return default_schema(df, "instacart")


def load_hm_fashion(max_rows: int) -> pd.DataFrame:
    path = find_existing_path(DATASET_CANDIDATE_PATHS["hm_fashion"])
    if not path:
        return pd.DataFrame()
    print(f"[INFO] hm_fashion resolved path -> {path}")

    p = Path(path)
    df = pd.DataFrame()

    try:
        # If path is a directory, prefer parquet files then CSVs inside it
        if p.is_dir():
            candidates = list(p.rglob("*.parquet")) + list(p.rglob("*.csv"))
            if candidates:
                p = candidates[0]

        lower = str(p).lower()
        if lower.endswith(".parquet"):
            try:
                df = pd.read_parquet(str(p))
                df = df.head(max_rows)
            except Exception as exc:
                print(f"[WARN] hm_fashion parquet read failed -> {exc}")
                df = pd.DataFrame()

        if df.empty:
            # Try CSV with a few common encodings
            encodings = ["utf-8", "latin1", "iso-8859-1"]
            for enc in encodings:
                try:
                    df = pd.read_csv(str(p), nrows=max_rows, encoding=enc)
                    break
                except Exception as exc:
                    print(f"[WARN] hm_fashion csv read encoding={enc} failed -> {exc}")
                    df = pd.DataFrame()
    except Exception as exc:
        print(f"[ERR] hm_fashion read -> {exc}")
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    if {"customer_id", "article_id", "t_dat"}.issubset(set(df.columns)):
        df["user_id"] = stable_hash_series(df["customer_id"].astype(str), 100_000_000)
        ts = pd.to_datetime(df["t_dat"], errors="coerce").fillna(pd.Timestamp("1970-01-01"))
        df["timestamp"] = ts.dt.strftime("%Y-%m-%dT%H:%M:%S")
        day_key = ts.dt.strftime("%Y%m%d").astype(int)
        df["session_id"] = (df["user_id"].astype(np.int64) * 100000 + day_key.astype(np.int64) % 100000).astype(np.int64)
        df["product_id"] = pd.to_numeric(df["article_id"], errors="coerce").fillna(0).astype(int)
        df["step"] = df.groupby("session_id").cumcount() + 1
        price = pd.to_numeric(df.get("price", np.nan), errors="coerce")
        if price.notna().sum() > 0 and price.nunique(dropna=True) > 1:
            q1 = float(price.quantile(0.33))
            q2 = float(price.quantile(0.66))
            df["action"] = np.select(
                [price <= q1, price <= q2],
                ["view", "add_to_cart"],
                default="purchase",
            )
        else:
            # H&M transaction rows do not contain explicit click/cart events.
            proxy = stable_hash_series(df["customer_id"].astype(str) + "|" + df["article_id"].astype(str), 3)
            df["action"] = np.select([proxy == 0, proxy == 1], ["view", "add_to_cart"], default="purchase")
        df["category"] = "fashion"
        df["sub_category"] = "article"
        df["price"] = pd.to_numeric(df.get("price", 0.0), errors="coerce").fillna(0.0)
        df["rating"] = 0.0
        df["cart_value"] = 0.0
        df["dwell_time"] = 18.0
        df["device"] = "desktop"
        df["intent"] = "buy"
        df["segment"] = "buyer"
        return default_schema(df, "hm_fashion")

    if {"productId", "productName", "mainCatCode"}.issubset(set(df.columns)):
        # Public Kaggle H&M product catalog fallback. It is real product data, but
        # lacks user events, so labels are deterministic catalog-behavior proxies.
        def text_col(name: str, default: str = "unknown") -> pd.Series:
            if name in df.columns:
                return df[name].fillna(default).astype(str)
            return pd.Series(default, index=df.index, dtype="object")

        price = pd.to_numeric(df.get("price", 0.0), errors="coerce").fillna(0.0)
        main_cat = text_col("mainCatCode", "fashion").replace("nan", "fashion")
        product_name = text_col("productName", "product")
        color_name = text_col("colorName", "unknown")
        brand_name = text_col("brandName", "H&M")
        is_online = text_col("isOnline", "true").str.lower().isin(["true", "1", "yes"])
        new_arrival = text_col("newArrival", "false").str.lower().isin(["true", "1", "yes"])
        coming_soon = text_col("comingSoon", "false").str.lower().isin(["true", "1", "yes"])

        df = df.copy()
        df["_main_cat"] = main_cat
        df["_sort_price"] = price
        df["_product_name"] = product_name
        df = df.sort_values(["_main_cat", "_sort_price", "_product_name"], kind="mergesort").reset_index(drop=True)

        price = pd.to_numeric(df.get("price", 0.0), errors="coerce").fillna(0.0)
        main_cat = df["_main_cat"].astype(str)
        product_name = df["_product_name"].astype(str)
        color_name = text_col("colorName", "unknown").reset_index(drop=True)
        brand_name = text_col("brandName", "H&M").reset_index(drop=True)
        is_online = text_col("isOnline", "true").reset_index(drop=True).str.lower().isin(["true", "1", "yes"])
        new_arrival = text_col("newArrival", "false").reset_index(drop=True).str.lower().isin(["true", "1", "yes"])
        coming_soon = text_col("comingSoon", "false").reset_index(drop=True).str.lower().isin(["true", "1", "yes"])

        group_step = df.groupby(main_cat, sort=False).cumcount()
        session_bucket = (group_step // 40).astype(str)
        session_key = main_cat + "|" + session_bucket
        df["user_id"] = stable_hash_series(main_cat + "|" + brand_name + "|" + color_name, 100_000_000)
        df["session_id"] = stable_hash_series(session_key, 2_000_000_000)
        product_id = pd.to_numeric(df["productId"], errors="coerce")
        if product_id.notna().sum() == 0:
            product_id = stable_hash_series(product_name, 2_000_000_000)
        df["product_id"] = product_id.fillna(0).astype("int64")
        df["step"] = (group_step % 40) + 1
        ts = pd.Timestamp("2024-01-01") + pd.to_timedelta(np.arange(len(df)) % 365, unit="D")
        df["timestamp"] = pd.Series(ts).dt.strftime("%Y-%m-%dT%H:%M:%S")

        price_rank = price.rank(method="average", pct=True).fillna(0.5).astype(np.float32)
        text_score = stable_hash_series(product_name + "|" + color_name, 1000).astype(np.float32) / 999.0
        score = (
            0.52 * price_rank
            + 0.23 * text_score
            + 0.10 * new_arrival.astype(np.float32)
            + 0.08 * is_online.astype(np.float32)
            + 0.07 * coming_soon.astype(np.float32)
        )
        action_bins = np.linspace(0.0, 1.0, num=len(ACTIONS) + 1)
        action_idx = np.clip(np.digitize(np.clip(score, 0.0, 1.0), action_bins[1:-1], right=False), 0, len(ACTIONS) - 1)
        df["action"] = pd.Index(ACTIONS).take(action_idx)
        df["category"] = main_cat.str.split("_").str[0].replace("", "fashion")
        df["sub_category"] = main_cat
        df["price"] = price
        df["rating"] = 0.0
        df["cart_value"] = np.where(df["action"].isin(["add_to_cart", "purchase"]), price, 0.0)
        df["dwell_time"] = np.where(new_arrival, 35.0, 18.0)
        df["device"] = "desktop"
        df["intent"] = np.where(df["action"].isin(["add_to_cart", "purchase", "wishlist"]), "buy", "browse")
        median_price = float(price.median()) if len(price) else 0.0
        df["segment"] = np.where(price >= median_price, "premium", "casual")
        return default_schema(df, "hm_fashion_catalog")

    return pd.DataFrame()


def load_olist(max_rows: int) -> pd.DataFrame:
    orders_path = find_existing_path(DATASET_CANDIDATE_PATHS["olist"])
    if not orders_path:
        return pd.DataFrame()
    print(f"[INFO] olist resolved orders path -> {orders_path}", flush=True)

    base = Path(orders_path).parent

    def _resolve_related_path(anchor_dir: Path, exact_name: str, name_tokens: list[str]) -> Path | None:
        # 1) Try same folder first (fast path).
        direct = anchor_dir / exact_name
        if direct.exists():
            return direct

        # 2) Search recursively near orders file.
        near_hits = list(anchor_dir.rglob(exact_name))
        if near_hits:
            return sorted(near_hits, key=lambda p: len(str(p)))[0]

        # 3) Fallback to global Kaggle input file index.
        all_files = _all_kaggle_input_files()
        basename_hits = [Path(p) for p in all_files if Path(p).name == exact_name]
        if basename_hits:
            return sorted(basename_hits, key=lambda p: len(str(p)))[0]

        token_hits = [
            Path(p)
            for p in all_files
            if p.endswith(".csv") and all(token in Path(p).name.lower() for token in name_tokens)
        ]
        if token_hits:
            return sorted(token_hits, key=lambda p: len(str(p)))[0]

        return None

    items_path = _resolve_related_path(base, "olist_order_items_dataset.csv", ["order", "items"])
    products_path = _resolve_related_path(base, "olist_products_dataset.csv", ["product"])
    customers_path = _resolve_related_path(base, "olist_customers_dataset.csv", ["customer"])
    print(f"[INFO] olist items path -> {items_path}", flush=True)
    print(f"[INFO] olist products path -> {products_path}", flush=True)
    print(f"[INFO] olist customers path -> {customers_path}", flush=True)

    def _safe_read_csv(path: str | Path, nrows: int | None = None, usecols: list[str] | None = None) -> pd.DataFrame:
        p = str(path)
        encodings = ["utf-8", "latin1", "iso-8859-1"]
        last_exc: Exception | None = None
        for enc in encodings:
            try:
                return pd.read_csv(p, nrows=nrows, usecols=usecols, encoding=enc, low_memory=False)
            except Exception as exc:
                last_exc = exc

        # Last-chance read that skips malformed lines.
        try:
            return pd.read_csv(p, nrows=nrows, usecols=usecols, encoding="latin1", on_bad_lines="skip", low_memory=False)
        except Exception as exc:
            raise RuntimeError(f"Failed reading CSV: {p} | last_error={exc} | first_error={last_exc}")

    if not items_path:
        print("[WARN] olist missing order items CSV (expected olist_order_items_dataset.csv)", flush=True)
        return pd.DataFrame()

    print("[INFO] olist reading orders...", flush=True)
    try:
        orders = _safe_read_csv(orders_path, usecols=["order_id", "customer_id", "order_purchase_timestamp"])
    except Exception:
        orders = _safe_read_csv(orders_path)
    print(f"[INFO] olist orders loaded -> {len(orders):,} rows", flush=True)

    required_orders = {"order_id", "customer_id", "order_purchase_timestamp"}
    if not required_orders.issubset(set(orders.columns)):
        print(f"[WARN] olist orders columns mismatch -> {sorted(list(orders.columns))[:20]}", flush=True)
        return pd.DataFrame()

    print(f"[INFO] olist reading items (nrows={max_rows:,})...", flush=True)
    items = _safe_read_csv(items_path, nrows=max_rows)
    print(f"[INFO] olist items loaded -> {len(items):,} rows", flush=True)
    print("[INFO] olist merging items + orders...", flush=True)
    df = items.merge(orders, on="order_id", how="left")
    print(f"[INFO] olist merged items+orders -> {len(df):,} rows", flush=True)

    if customers_path and customers_path.exists():
        print("[INFO] olist reading customers...", flush=True)
        try:
            customers = _safe_read_csv(customers_path, usecols=["customer_id", "customer_unique_id"])
        except Exception:
            customers = _safe_read_csv(customers_path)
        print(f"[INFO] olist customers loaded -> {len(customers):,} rows", flush=True)
        print("[INFO] olist merging customers...", flush=True)
        df = df.merge(customers, on="customer_id", how="left")
        if "customer_unique_id" in df.columns:
            user_src = df["customer_unique_id"].fillna(df["customer_id"]).astype(str)
        else:
            user_src = df["customer_id"].astype(str)
        # Stable and vectorized hashing is much faster than Python's row-wise hash().
        df["user_id"] = (pd.util.hash_pandas_object(user_src, index=False).astype("uint64") % 100_000_000).astype("int64")
    else:
        user_src = df["customer_id"].astype(str)
        df["user_id"] = (pd.util.hash_pandas_object(user_src, index=False).astype("uint64") % 100_000_000).astype("int64")

    if products_path and products_path.exists():
        print("[INFO] olist reading products...", flush=True)
        try:
            products = _safe_read_csv(products_path, usecols=["product_id", "product_category_name"])
        except Exception:
            products = _safe_read_csv(products_path)
            if "product_category_name" not in products.columns:
                products["product_category_name"] = "general"
        print(f"[INFO] olist products loaded -> {len(products):,} rows", flush=True)
        print("[INFO] olist merging products...", flush=True)
        df = df.merge(products, on="product_id", how="left")
    else:
        df["product_category_name"] = "general"

    print("[INFO] olist feature engineering: timestamps...", flush=True)
    ts = pd.to_datetime(df["order_purchase_timestamp"], errors="coerce").fillna(pd.Timestamp("1970-01-01"))
    day_key = (ts.dt.year * 10000 + ts.dt.month * 100 + ts.dt.day).astype("int64")
    df["timestamp"] = ts.dt.strftime("%Y-%m-%dT%H:%M:%S")
    print("[INFO] olist feature engineering: session_id...", flush=True)
    # Use customer-level sessions to create longer, more informative behavior chains.
    df["session_id"] = df["user_id"].astype(np.int64)
    print("[INFO] olist feature engineering: product_id encode...", flush=True)
    # Olist product_id is typically an alphanumeric key, so encode deterministically instead of numeric coercion to 0.
    prod_src = df["product_id"].astype(str)
    df["product_id"] = (pd.util.hash_pandas_object(prod_src, index=False).astype("uint64") % 2_000_000_000).astype("int64")
    df["step"] = pd.to_numeric(df.get("order_item_id", 1), errors="coerce").fillna(1).astype(int)
    # Turn Olist into a 10-class proxy task so the benchmark can separate models better.
    # The original dataset is too sparse if we only map it to 1-2 actions.
    price = pd.to_numeric(df.get("price", np.nan), errors="coerce")
    customer_step = df.groupby("customer_id").cumcount().astype(np.float32)
    category_hash = (pd.util.hash_pandas_object(df["product_category_name"].astype(str), index=False).astype("uint64") % 1000).astype(np.float32)
    product_hash = (pd.util.hash_pandas_object(prod_src, index=False).astype("uint64") % 1000).astype(np.float32)
    order_step = pd.to_numeric(df.get("order_item_id", 1), errors="coerce").fillna(1).astype(np.float32)
    if price.notna().sum() > 0 and price.nunique(dropna=True) > 9:
        scaled = price.rank(method="average", pct=True).fillna(0.5).astype(np.float32)
    else:
        max_order_step = max(float(order_step.max()), 1.0)
        scaled = (
            0.34 * (category_hash / 999.0)
            + 0.24 * (product_hash / 999.0)
            + 0.16 * (order_step / max_order_step)
            + 0.12 * ((day_key % 31) / 30.0)
            + 0.14 * np.tanh(customer_step / 10.0)
        ).astype(np.float32)
    scaled = np.clip(scaled, 0.0, 1.0)
    action_bins = np.linspace(0.0, 1.0, num=len(ACTIONS) + 1)
    action_idx = np.clip(np.digitize(scaled, action_bins[1:-1], right=False), 0, len(ACTIONS) - 1)
    df["action"] = pd.Index(ACTIONS).take(action_idx)
    df["category"] = df["product_category_name"].astype(str).replace("nan", "general")
    df["sub_category"] = "olist"
    df["price"] = pd.to_numeric(df.get("price", 0.0), errors="coerce").fillna(0.0)
    df["rating"] = 0.0
    df["cart_value"] = 0.0
    df["dwell_time"] = 15.0
    df["device"] = "desktop"
    df["intent"] = "buy"
    df["segment"] = "buyer"
    df = df.sort_values(["session_id", "timestamp", "step", "product_id"], kind="mergesort").reset_index(drop=True)
    df["step"] = df.groupby("session_id").cumcount() + 1
    print(f"[INFO] olist final rows before schema -> {len(df):,}", flush=True)
    return default_schema(df, "olist")


# ----------------------------
# Feature building
# ----------------------------
def build_vocab(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    values = sorted({str(r.get(key) or "unknown") for r in rows})
    return {v: i + 1 for i, v in enumerate(values)}


def encode_event(
    row: dict[str, Any],
    category_to_id: dict[str, int],
    sub_category_to_id: dict[str, int],
    max_product_id: int,
    max_price: float,
    max_cart_value: float,
    max_dwell_time: float,
) -> np.ndarray:
    action_norm = ACTION_TO_ID.get(str(row.get("action")), 0) / max(NUM_CLASSES - 1, 1)
    product_norm = min(float(row.get("product_id", 0)) / max(max_product_id, 1), 1.0)
    cat_norm = float(category_to_id.get(str(row.get("category", "unknown")), 0)) / max(len(category_to_id), 1)
    sub_norm = float(sub_category_to_id.get(str(row.get("sub_category", "unknown")), 0)) / max(len(sub_category_to_id), 1)
    price_norm = min(float(row.get("price", 0.0)) / max(max_price, 1.0), 1.0)
    rating_norm = min(float(row.get("rating", 0.0)) / 5.0, 1.0)
    cart_norm = min(float(row.get("cart_value", 0.0)) / max(max_cart_value, 1.0), 1.0)
    dwell_norm = min(float(row.get("dwell_time", 0.0)) / max(max_dwell_time, 1.0), 1.0)

    # Default placeholders for sparse public datasets.
    device_id = 1.0
    source_id = 1.0 / 5.0
    hour = 0.5
    intent_id = 1.0 / 5.0
    segment_id = 1.0 / 5.0

    return np.array([
        action_norm, product_norm, cat_norm, sub_norm,
        price_norm, rating_norm, cart_norm, dwell_norm,
        device_id, source_id, hour, intent_id, segment_id,
    ], dtype=np.float32)


def build_sequences(df: pd.DataFrame, seq_len: int = 12) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    working = df.copy()
    sort_cols: list[str] = []
    if "session_id" in working.columns:
        sort_cols.append("session_id")
    if "timestamp" in working.columns:
        working["_sort_timestamp"] = pd.to_datetime(working["timestamp"], errors="coerce")
        sort_cols.append("_sort_timestamp")
    if "step" in working.columns:
        sort_cols.append("step")
    if "product_id" in working.columns:
        sort_cols.append("product_id")
    if sort_cols:
        working = working.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    if "_sort_timestamp" in working.columns:
        working = working.drop(columns=["_sort_timestamp"])

    rows = working.to_dict("records")
    if not rows:
        return np.array([]), np.array([]), np.array([]), {}

    category_to_id = build_vocab(rows, "category")
    sub_category_to_id = build_vocab(rows, "sub_category")

    max_product_id = max(int(r.get("product_id", 0)) for r in rows) or 1
    max_price = max(float(r.get("price", 0.0)) for r in rows) or 1.0
    max_cart_value = max(float(r.get("cart_value", 0.0)) for r in rows) or 1.0
    max_dwell_time = max(float(r.get("dwell_time", 0.0)) for r in rows) or 1.0

    by_session: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_session[int(r.get("session_id", 0))].append(r)

    X_list: list[np.ndarray] = []
    y_list: list[int] = []
    group_list: list[int] = []

    for session_id, srows in by_session.items():
        if len(srows) <= seq_len:
            continue
        encoded = [
            encode_event(
                row=r,
                category_to_id=category_to_id,
                sub_category_to_id=sub_category_to_id,
                max_product_id=max_product_id,
                max_price=max_price,
                max_cart_value=max_cart_value,
                max_dwell_time=max_dwell_time,
            )
            for r in srows
        ]
        actions = [ACTION_TO_ID.get(str(r.get("action", "view")), 0) for r in srows]
        for i in range(seq_len, len(encoded)):
            X_list.append(np.array(encoded[i - seq_len:i], dtype=np.float32))
            y_list.append(int(actions[i]))
            group_list.append(int(session_id))

    if not X_list:
        return np.array([]), np.array([]), np.array([]), {}

    meta = {
        "category_to_id": category_to_id,
        "sub_category_to_id": sub_category_to_id,
        "max_product_id": max_product_id,
        "max_price": max_price,
        "max_cart_value": max_cart_value,
        "max_dwell_time": max_dwell_time,
        "seq_len": seq_len,
        "feature_dim": FEATURE_DIM,
        "num_classes": NUM_CLASSES,
        "actions": ACTIONS,
    }
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int64), np.array(group_list, dtype=np.int64), meta


def grouped_stratified_split(y: np.ndarray, groups: np.ndarray, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    groups = np.asarray(groups)
    if len(y) != len(groups):
        raise ValueError(f"y/groups length mismatch: y={len(y)} groups={len(groups)}")

    if len(y) == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64), np.array([], dtype=np.int64)

    group_labels: dict[int, list[int]] = defaultdict(list)
    for label, group in zip(y, groups):
        group_labels[int(group)].append(int(label))

    grouped_rows: list[tuple[int, int]] = []
    for group_id, labels in group_labels.items():
        counts = np.bincount(np.array(labels, dtype=np.int64), minlength=NUM_CLASSES)
        major_label = int(np.argmax(counts))
        grouped_rows.append((group_id, major_label))

    def _allocate_counts(n_groups: int) -> list[int]:
        if n_groups <= 0:
            return [0, 0, 0]
        if n_groups == 1:
            return [1, 0, 0]
        if n_groups == 2:
            return [1, 0, 1]

        desired = np.array([0.70, 0.15, 0.15], dtype=np.float64)
        raw = desired * n_groups
        counts = np.floor(raw).astype(int)
        for i in range(3):
            if counts[i] == 0:
                counts[i] = 1

        while counts.sum() > n_groups:
            candidates = np.where(counts > 1)[0]
            if len(candidates) == 0:
                break
            i = int(candidates[np.argmax(counts[candidates])])
            counts[i] -= 1

        while counts.sum() < n_groups:
            i = int(np.argmax(raw - counts))
            counts[i] += 1

        return counts.astype(int).tolist()

    train_groups: list[int] = []
    val_groups: list[int] = []
    test_groups: list[int] = []

    for label in sorted({major for _, major in grouped_rows}):
        label_group_ids = [group_id for group_id, major in grouped_rows if major == label]
        rng.shuffle(label_group_ids)
        n_train, n_val, n_test = _allocate_counts(len(label_group_ids))
        train_groups.extend(label_group_ids[:n_train])
        val_groups.extend(label_group_ids[n_train:n_train + n_val])
        test_groups.extend(label_group_ids[n_train + n_val:n_train + n_val + n_test])

    all_groups = np.array([group_id for group_id, _ in grouped_rows], dtype=np.int64)
    assigned = set(train_groups) | set(val_groups) | set(test_groups)
    missing_groups = [group_id for group_id in all_groups.tolist() if group_id not in assigned]
    if missing_groups:
        rng.shuffle(missing_groups)
        for i, group_id in enumerate(missing_groups):
            if i % 10 == 0:
                train_groups.append(group_id)
            elif i % 10 == 1:
                val_groups.append(group_id)
            else:
                test_groups.append(group_id)

    group_to_split: dict[int, int] = {}
    for group_id in train_groups:
        group_to_split[int(group_id)] = 0
    for group_id in val_groups:
        group_to_split[int(group_id)] = 1
    for group_id in test_groups:
        group_to_split[int(group_id)] = 2

    train_idx = [i for i, group_id in enumerate(groups.tolist()) if group_to_split.get(int(group_id), 0) == 0]
    val_idx = [i for i, group_id in enumerate(groups.tolist()) if group_to_split.get(int(group_id), 0) == 1]
    test_idx = [i for i, group_id in enumerate(groups.tolist()) if group_to_split.get(int(group_id), 0) == 2]

    if not val_idx or not test_idx:
        unique_groups = np.array(sorted(group_to_split.keys()), dtype=np.int64)
        rng.shuffle(unique_groups)
        n_groups = len(unique_groups)
        n_train = max(1, int(round(n_groups * 0.70)))
        n_val = max(1, int(round(n_groups * 0.15))) if n_groups >= 3 else 0
        if n_train + n_val >= n_groups and n_groups >= 3:
            n_train = max(1, n_train - 1)
        train_set = set(unique_groups[:n_train].tolist())
        val_set = set(unique_groups[n_train:n_train + n_val].tolist())
        test_set = set(unique_groups[n_train + n_val:].tolist())
        train_idx = [i for i, group_id in enumerate(groups.tolist()) if int(group_id) in train_set]
        val_idx = [i for i, group_id in enumerate(groups.tolist()) if int(group_id) in val_set]
        test_idx = [i for i, group_id in enumerate(groups.tolist()) if int(group_id) in test_set]

    rng.shuffle(train_idx)
    rng.shuffle(val_idx)
    rng.shuffle(test_idx)
    return np.array(train_idx), np.array(val_idx), np.array(test_idx)


# ----------------------------
# Models
# ----------------------------
class RNNClassifier(nn.Module):
    def __init__(self, input_dim=FEATURE_DIM, hidden_dim=128, num_layers=1, num_classes=NUM_CLASSES):
        super().__init__()
        self.rnn = nn.RNN(input_dim, hidden_dim, num_layers, batch_first=True, dropout=DROPOUT if num_layers > 1 else 0.0)
        self.dropout = nn.Dropout(DROPOUT)
        self.fc = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        out, _ = self.rnn(x)
        return self.fc(self.dropout(out[:, -1, :]))


class LSTMClassifier(nn.Module):
    def __init__(self, input_dim=FEATURE_DIM, hidden_dim=128, num_layers=1, num_classes=NUM_CLASSES):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=DROPOUT if num_layers > 1 else 0.0)
        self.dropout = nn.Dropout(DROPOUT)
        self.fc = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(self.dropout(out[:, -1, :]))


class BiLSTMClassifier(nn.Module):
    def __init__(self, input_dim=FEATURE_DIM, hidden_dim=128, num_layers=1, num_classes=NUM_CLASSES):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=DROPOUT if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(DROPOUT)
        self.fc = nn.Linear(hidden_dim * 2, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(self.dropout(out[:, -1, :]))


class GRUClassifier(nn.Module):
    def __init__(self, input_dim=FEATURE_DIM, hidden_dim=128, num_layers=1, num_classes=NUM_CLASSES):
        super().__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, num_layers, batch_first=True, dropout=DROPOUT if num_layers > 1 else 0.0)
        self.dropout = nn.Dropout(DROPOUT)
        self.fc = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(self.dropout(out[:, -1, :]))


class BiGRUClassifier(nn.Module):
    def __init__(self, input_dim=FEATURE_DIM, hidden_dim=128, num_layers=1, num_classes=NUM_CLASSES):
        super().__init__()
        self.gru = nn.GRU(
            input_dim,
            hidden_dim,
            num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=DROPOUT if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(DROPOUT)
        self.fc = nn.Linear(hidden_dim * 2, num_classes)

    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(self.dropout(out[:, -1, :]))


MODEL_FACTORIES = {
    "rnn": RNNClassifier,
    "lstm": LSTMClassifier,
    "bilstm": BiLSTMClassifier,
    "gru": GRUClassifier,
    "bigru": BiGRUClassifier,
}


# ----------------------------
# Training helpers
# ----------------------------
class SequenceDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


def compute_class_weights(y_train: np.ndarray, n_classes: int = NUM_CLASSES) -> torch.Tensor:
    counts = np.bincount(y_train.astype(np.int64), minlength=n_classes).astype(np.float64)
    safe = np.where(counts > 0, counts, 1.0)
    raw = 1.0 / np.sqrt(safe)
    normalized = np.clip(raw / np.mean(raw), 0.5, 2.0)
    return torch.tensor(normalized, dtype=torch.float32)


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> np.ndarray:
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        cm[int(t), int(p)] += 1
    return cm


def balanced_accuracy_from_cm(cm: np.ndarray, active_labels: list[int]) -> float:
    recalls: list[float] = []
    for i in active_labels:
        tp = float(cm[i, i])
        fn = float(cm[i, :].sum() - tp)
        recalls.append(tp / (tp + fn) if (tp + fn) > 0 else 0.0)
    return float(np.mean(recalls)) if recalls else 0.0


def roc_auc_macro(y_true: np.ndarray, y_prob: np.ndarray, n_classes: int) -> float:
    aucs: list[float] = []
    for c in range(n_classes):
        binary = (y_true == c).astype(int)
        if binary.sum() == 0 or binary.sum() == len(binary):
            continue
        scores = y_prob[:, c]
        order = np.argsort(-scores)
        bs = binary[order]
        tp = np.cumsum(bs)
        fp = np.cumsum(1 - bs)
        tpr = np.concatenate([[0.0], tp / max(binary.sum(), 1)])
        fpr = np.concatenate([[0.0], fp / max((1 - binary).sum(), 1)])
        # NumPy 2.x removed np.trapz in some builds; use trapezoid with fallback.
        area = np.trapezoid(tpr, fpr) if hasattr(np, "trapezoid") else np.trapz(tpr, fpr)
        aucs.append(abs(float(area)))
    return float(np.mean(aucs)) if aucs else 0.0


def pr_auc_macro(y_true: np.ndarray, y_prob: np.ndarray, n_classes: int) -> float:
    aucs: list[float] = []
    for c in range(n_classes):
        binary = (y_true == c).astype(int)
        # Skip undefined one-vs-rest cases with all positives or all negatives.
        if binary.sum() == 0 or binary.sum() == len(binary):
            continue
        scores = y_prob[:, c]
        order = np.argsort(-scores)
        bs = binary[order]
        tp = np.cumsum(bs)
        fp = np.cumsum(1 - bs)
        precision = np.concatenate([[1.0], tp / np.maximum(tp + fp, 1)])
        recall = np.concatenate([[0.0], tp / max(binary.sum(), 1)])
        area = np.trapezoid(precision, recall) if hasattr(np, "trapezoid") else np.trapz(precision, recall)
        aucs.append(abs(float(area)))
    return float(np.mean(aucs)) if aucs else 0.0


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict[str, Any]:
    cm = confusion_matrix(y_true, y_pred, NUM_CLASSES)
    accuracy = float((y_true == y_pred).mean()) if len(y_true) else 0.0
    active_labels = sorted(set(np.unique(y_true).tolist()) | set(np.unique(y_pred).tolist()))
    if not active_labels:
        active_labels = list(range(NUM_CLASSES))
    degenerate_target_space = len(np.unique(y_true)) < 2

    if degenerate_target_space:
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "num_active_classes": int(len(active_labels)),
            "roc_auc": 0.0,
            "pr_auc": 0.0,
            "confusion_matrix": cm.tolist(),
            "degenerate_target_space": True,
        }

    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    for i in active_labels:
        tp = float(cm[i, i])
        fp = float(cm[:, i].sum() - tp)
        fn = float(cm[i, :].sum() - tp)
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        precisions.append(p)
        recalls.append(r)
        f1s.append(f)

    return {
        "accuracy": round(accuracy, 6),
        "balanced_accuracy": round(balanced_accuracy_from_cm(cm, active_labels), 6),
        "precision": round(float(np.mean(precisions)), 6),
        "recall": round(float(np.mean(recalls)), 6),
        "f1_score": round(float(np.mean(f1s)), 6),
        "num_active_classes": int(len(active_labels)),
        "roc_auc": round(roc_auc_macro(y_true, y_prob, NUM_CLASSES), 6),
        "pr_auc": round(pr_auc_macro(y_true, y_prob, NUM_CLASSES), 6),
        "confusion_matrix": cm.tolist(),
        "degenerate_target_space": False,
    }


def train_model(
    model: nn.Module,
    dataset_name: str,
    model_name: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    epochs: int,
) -> dict[str, Any]:
    model = model.to(DEVICE)
    # DataLoader performance options
    _num_workers = NUM_WORKERS
    _pin_memory = PIN_MEMORY
    train_dataset = SequenceDataset(X_train, y_train)
    y_counts = np.bincount(y_train.astype(np.int64), minlength=NUM_CLASSES)
    nonzero_counts = y_counts[y_counts > 0]
    imbalance_ratio = float(nonzero_counts.max() / max(nonzero_counts.min(), 1)) if len(nonzero_counts) else 1.0
    if imbalance_ratio >= 4.0 and len(y_train) >= BATCH_SIZE:
        sample_weights = np.array([1.0 / max(y_counts[int(label)], 1.0) for label in y_train], dtype=np.float64)
        sample_weights = sample_weights / max(sample_weights.mean(), 1e-12)
        sampler = WeightedRandomSampler(weights=torch.as_tensor(sample_weights, dtype=torch.double), num_samples=len(sample_weights), replacement=True)
        train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, sampler=sampler, num_workers=_num_workers, pin_memory=_pin_memory)
    else:
        train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=_num_workers, pin_memory=_pin_memory)
    val_loader = DataLoader(SequenceDataset(X_val, y_val), batch_size=BATCH_SIZE, shuffle=False, num_workers=_num_workers, pin_memory=_pin_memory)
    test_loader = DataLoader(SequenceDataset(X_test, y_test), batch_size=BATCH_SIZE, shuffle=False, num_workers=_num_workers, pin_memory=_pin_memory)

    class_weights = compute_class_weights(y_train).to(DEVICE)
    criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.05)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=2)

    best_val = float("inf")
    best_train = float("inf")
    best_val_bacc = float("-inf")
    patience_counter = 0

    history = {"train_loss": [], "val_loss": [], "val_accuracy": []}
    tmp_ckpt = ARTIFACTS_DIR / f"_tmp_{dataset_name}_{model_name}.pt"

    if len(np.unique(y_val)) < 2 or len(np.unique(y_test)) < 2:
        print(
            f"[WARN] {dataset_name}/{model_name}: validation or test split has <2 active classes; metrics may be unstable.",
            flush=True,
        )
    print(
        f"[INFO] {dataset_name}/{model_name}: train_class_imbalance_ratio={imbalance_ratio:.2f} "
        f"sampler={'on' if imbalance_ratio >= 4.0 and len(y_train) >= BATCH_SIZE else 'off'}",
        flush=True,
    )

    scaler = None
    if USE_AMP and DEVICE.type == "cuda":
        scaler = torch.amp.GradScaler("cuda")

    for epoch in range(epochs):
        model.train()
        train_loss_total = 0.0
        n_train_batches = 0
        for xb, yb in train_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            if scaler is not None:
                with torch.amp.autocast("cuda"):
                    logits = model(xb)
                    loss = criterion(logits, yb)
                scaler.scale(loss).backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                logits = model(xb)
                loss = criterion(logits, yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
            train_loss_total += float(loss.item())
            n_train_batches += 1

        avg_train = train_loss_total / max(n_train_batches, 1)

        model.eval()
        val_loss_total = 0.0
        n_val_batches = 0
        y_val_true: list[int] = []
        y_val_pred: list[int] = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                if scaler is not None:
                    with torch.amp.autocast("cuda"):
                        logits = model(xb)
                        val_loss_total += float(criterion(logits, yb).item())
                else:
                    logits = model(xb)
                    val_loss_total += float(criterion(logits, yb).item())
                n_val_batches += 1
                y_val_pred.extend(torch.argmax(logits, dim=-1).cpu().numpy().tolist())
                y_val_true.extend(yb.cpu().numpy().tolist())

        avg_val = val_loss_total / max(n_val_batches, 1)
        scheduler.step(avg_val)
        val_true_arr = np.array(y_val_true, dtype=np.int64)
        val_pred_arr = np.array(y_val_pred, dtype=np.int64)
        val_acc = float((val_true_arr == val_pred_arr).mean()) if len(val_true_arr) else 0.0
        val_active = sorted(set(val_true_arr.tolist()) | set(val_pred_arr.tolist())) if len(val_true_arr) else []
        if val_active:
            val_cm = confusion_matrix(val_true_arr, val_pred_arr, NUM_CLASSES)
            val_bacc = balanced_accuracy_from_cm(val_cm, val_active)
        else:
            val_bacc = 0.0

        history["train_loss"].append(avg_train)
        history["val_loss"].append(avg_val)
        history["val_accuracy"].append(val_acc)

        if (val_bacc > best_val_bacc) or (val_bacc == best_val_bacc and avg_val < best_val):
            best_val_bacc = val_bacc
            best_val = avg_val
            best_train = avg_train
            patience_counter = 0
            torch.save(model.state_dict(), str(tmp_ckpt))
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                break

    if tmp_ckpt.exists():
        model.load_state_dict(torch.load(str(tmp_ckpt), map_location=DEVICE))
        tmp_ckpt.unlink()

    model.eval()
    y_true: list[int] = []
    y_pred: list[int] = []
    probs: list[np.ndarray] = []
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(DEVICE)
            if scaler is not None:
                with torch.amp.autocast("cuda"):
                    logits = model(xb)
            else:
                logits = model(xb)
            y_pred.extend(torch.argmax(logits, dim=-1).cpu().numpy().tolist())
            y_true.extend(yb.numpy().tolist())
            probs.append(torch.softmax(logits, dim=-1).cpu().numpy())

    y_true_arr = np.array(y_true, dtype=np.int64)
    y_pred_arr = np.array(y_pred, dtype=np.int64)
    y_prob = np.vstack(probs) if probs else np.zeros((0, NUM_CLASSES), dtype=np.float32)

    metrics = classification_metrics(y_true_arr, y_pred_arr, y_prob)
    metrics["train_loss"] = round(best_train, 6)
    metrics["val_loss"] = round(best_val, 6)
    metrics["best_val_balanced_accuracy"] = round(best_val_bacc, 6)
    metrics["generalization_gap"] = round(best_val - best_train, 6)
    if len(y_pred_arr):
        pred_counts = np.bincount(y_pred_arr, minlength=NUM_CLASSES)
        metrics["pred_majority_share"] = round(float(pred_counts.max() / max(pred_counts.sum(), 1)), 6)
        metrics["predicted_classes"] = int((pred_counts > 0).sum())
    else:
        metrics["pred_majority_share"] = 0.0
        metrics["predicted_classes"] = 0

    return {
        "dataset_name": dataset_name,
        "model_name": model_name,
        "history": history,
        "metrics": metrics,
        "state_dict": model.state_dict(),
    }


# ----------------------------
# Plotting
# ----------------------------
def _ensure_plot_dir() -> None:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def _plot_bar(labels: list[str], values: list[float], title: str, ylabel: str, filename: str, ylim_0_1: bool = True) -> None:
    _ensure_plot_dir()
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.get_cmap("tab10")(np.linspace(0, 1, len(labels)))
    ax.bar(labels, values, color=colors)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    if ylim_0_1:
        ax.set_ylim(0, 1)
    plt.xticks(rotation=15)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / filename, dpi=140)
    plt.close(fig)


def _plot_heatmap(matrix: np.ndarray, row_labels: list[str], col_labels: list[str], title: str, filename: str, vmin: float = 0.0, vmax: float = 1.0) -> None:
    _ensure_plot_dir()
    fig, ax = plt.subplots(figsize=(11, 6))
    im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=vmin, vmax=vmax)
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels)
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=20)
    ax.set_title(title)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.3f}", ha="center", va="center", fontsize=8)
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / filename, dpi=140)
    plt.close(fig)


def _plot_loss_scatter(results: list[dict[str, Any]]) -> None:
    _ensure_plot_dir()
    fig, ax = plt.subplots(figsize=(10, 6))
    model_names = sorted({r["model_name"] for r in results})
    colors = {m: plt.get_cmap("tab10")(i / max(len(model_names), 1)) for i, m in enumerate(model_names)}
    for r in results:
        m = r["model_name"]
        metrics = r["metrics"]
        ax.scatter(metrics["train_loss"], metrics["val_loss"], color=colors[m], label=m, alpha=0.8)
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys())
    ax.set_title("Train vs Validation Loss (All dataset-model runs)")
    ax.set_xlabel("Train Loss")
    ax.set_ylabel("Validation Loss")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "train_vs_val_scatter_all_runs.png", dpi=140)
    plt.close(fig)


def _plot_model_radar(results: list[dict[str, Any]]) -> None:
    _ensure_plot_dir()
    models = sorted({r["model_name"] for r in results})
    metrics = ["balanced_accuracy", "f1_score", "roc_auc", "pr_auc"]
    labels = ["BACC", "F1", "ROC", "PR"]

    def _avg(model_name: str, metric_name: str) -> float:
        vals = [r["metrics"].get(metric_name, 0.0) for r in results if r["model_name"] == model_name]
        return float(np.mean(vals)) if vals else 0.0

    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw={"polar": True})
    cmap = plt.get_cmap("tab10")
    for i, model in enumerate(models):
        values = [_avg(model, metric) for metric in metrics]
        values += values[:1]
        ax.plot(angles, values, color=cmap(i / max(len(models) - 1, 1)), linewidth=2.2, label=model.upper())
        ax.fill(angles, values, color=cmap(i / max(len(models) - 1, 1)), alpha=0.10)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_yticklabels([])
    ax.set_title("Model Radar: Mean Balanced Metrics", pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.10))
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "model_radar_metrics.png", dpi=140)
    plt.close(fig)


def _plot_model_metric_heatmap(results: list[dict[str, Any]]) -> None:
    _ensure_plot_dir()
    models = sorted({r["model_name"] for r in results})
    metric_names = ["accuracy", "balanced_accuracy", "f1_score", "roc_auc", "pr_auc", "pred_majority_share"]
    matrix = np.zeros((len(models), len(metric_names)), dtype=np.float32)
    for i, model in enumerate(models):
        subset = [r["metrics"] for r in results if r["model_name"] == model]
        for j, metric_name in enumerate(metric_names):
            matrix[i, j] = float(np.mean([m.get(metric_name, 0.0) for m in subset])) if subset else 0.0

    fig, ax = plt.subplots(figsize=(12, 5))
    im = ax.imshow(matrix, cmap="magma", aspect="auto", vmin=0.0, vmax=1.0)
    ax.set_xticks(np.arange(len(metric_names)))
    ax.set_xticklabels(["ACC", "BACC", "F1", "ROC", "PR", "P@1"], rotation=15)
    ax.set_yticks(np.arange(len(models)))
    ax.set_yticklabels([m.upper() for m in models])
    ax.set_title("Model Metric Heatmap")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.3f}", ha="center", va="center", color="white", fontsize=8)
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "model_metric_heatmap.png", dpi=140)
    plt.close(fig)


def _plot_average_confusion_matrices(results: list[dict[str, Any]]) -> None:
    _ensure_plot_dir()
    models = sorted({r["model_name"] for r in results})
    if not models:
        return

    fig, axes = plt.subplots(1, len(models), figsize=(4.5 * len(models), 4.5), squeeze=False)
    cmap = plt.get_cmap("Blues")
    for col, model in enumerate(models):
        cms = [np.array(r["metrics"].get("confusion_matrix", []), dtype=np.float32) for r in results if r["model_name"] == model]
        if not cms:
            continue
        cm = np.mean(cms, axis=0)
        row_sums = cm.sum(axis=1, keepdims=True)
        cm = cm / np.maximum(row_sums, 1.0)
        ax = axes[0, col]
        im = ax.imshow(cm, interpolation="nearest", cmap=cmap, vmin=0.0, vmax=1.0)
        ax.set_title(model.upper())
        ax.set_xticks(np.arange(len(ACTIONS)))
        ax.set_xticklabels(ACTIONS, rotation=45, ha="right")
        ax.set_yticks(np.arange(len(ACTIONS)))
        ax.set_yticklabels(ACTIONS)
        ax.set_xlabel("Predicted")
        if col == 0:
            ax.set_ylabel("True")
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center", fontsize=7, color="black")
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.75)
    fig.suptitle("Average Normalized Confusion Matrices by Model", y=1.02)
    fig.subplots_adjust(top=0.88)
    fig.savefig(PLOTS_DIR / "average_confusion_matrices_by_model.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def _plot_dataset_model_rank_matrix(results: list[dict[str, Any]]) -> None:
    _ensure_plot_dir()
    models = sorted({r["model_name"] for r in results})
    datasets = sorted({r["dataset_name"] for r in results})
    if not models or not datasets:
        return

    rank_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    score_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    for i, d in enumerate(datasets):
        subset = [r for r in results if r["dataset_name"] == d]
        ranked = sorted(subset, key=lambda r: r["metrics"].get("balanced_accuracy", 0.0), reverse=True)
        for rank, run in enumerate(ranked, start=1):
            j = models.index(run["model_name"])
            rank_matrix[i, j] = rank
        for j, m in enumerate(models):
            run = next((r for r in subset if r["model_name"] == m), None)
            if run:
                score_matrix[i, j] = run["metrics"].get("balanced_accuracy", 0.0)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    im0 = axes[0].imshow(score_matrix, cmap="YlGnBu", aspect="auto", vmin=0.0, vmax=1.0)
    axes[0].set_title("Balanced Accuracy by Dataset x Model")
    axes[0].set_xticks(np.arange(len(models)))
    axes[0].set_xticklabels([m.upper() for m in models], rotation=20)
    axes[0].set_yticks(np.arange(len(datasets)))
    axes[0].set_yticklabels(datasets)
    for i in range(score_matrix.shape[0]):
        for j in range(score_matrix.shape[1]):
            axes[0].text(j, i, f"{score_matrix[i, j]:.3f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im0, ax=axes[0])

    im1 = axes[1].imshow(rank_matrix, cmap="OrRd", aspect="auto", vmin=1, vmax=max(len(models), 1))
    axes[1].set_title("Rank by Dataset (1 = best)")
    axes[1].set_xticks(np.arange(len(models)))
    axes[1].set_xticklabels([m.upper() for m in models], rotation=20)
    axes[1].set_yticks(np.arange(len(datasets)))
    axes[1].set_yticklabels(datasets)
    for i in range(rank_matrix.shape[0]):
        for j in range(rank_matrix.shape[1]):
            if rank_matrix[i, j] > 0:
                axes[1].text(j, i, f"{int(rank_matrix[i, j])}", ha="center", va="center", fontsize=8)
    fig.colorbar(im1, ax=axes[1])

    fig.suptitle("Dataset-Model Comparison Matrix", y=1.02)
    fig.subplots_adjust(top=0.88)
    fig.savefig(PLOTS_DIR / "dataset_model_comparison_matrix.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def generate_plots(results: list[dict[str, Any]]) -> None:
    if not results:
        return

    models = sorted({r["model_name"] for r in results})
    datasets = sorted({r["dataset_name"] for r in results})

    def model_avg(metric_name: str) -> dict[str, float]:
        out: dict[str, float] = {}
        for m in models:
            vals = [r["metrics"].get(metric_name, 0.0) for r in results if r["model_name"] == m]
            out[m] = float(np.mean(vals)) if vals else 0.0
        return out

    avg_f1 = model_avg("f1_score")
    avg_roc = model_avg("roc_auc")
    avg_pr = model_avg("pr_auc")
    avg_gap = model_avg("generalization_gap")
    avg_acc = model_avg("accuracy")

    _plot_bar(models, [avg_acc[m] for m in models], "Average Accuracy by Model", "Accuracy", "avg_accuracy_models.png", ylim_0_1=True)
    _plot_bar(models, [avg_f1[m] for m in models], "Average Macro-F1 by Model", "Macro-F1", "avg_macro_f1_models.png", ylim_0_1=True)
    _plot_bar(models, [avg_roc[m] for m in models], "Average ROC-AUC by Model", "ROC-AUC", "avg_roc_auc_models.png", ylim_0_1=True)
    _plot_bar(models, [avg_pr[m] for m in models], "Average PR-AUC by Model", "PR-AUC", "avg_pr_auc_models.png", ylim_0_1=True)
    _plot_bar(models, [avg_gap[m] for m in models], "Average Generalization Gap by Model", "Val Loss - Train Loss", "avg_generalization_gap_models.png", ylim_0_1=False)
    _plot_model_radar(results)
    _plot_model_metric_heatmap(results)

    f1_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    roc_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    pr_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    acc_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    bacc_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    p1_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    gap_matrix = np.zeros((len(datasets), len(models)), dtype=np.float32)
    rank_count = {m: 0 for m in models}

    for i, d in enumerate(datasets):
        subset = [r for r in results if r["dataset_name"] == d]
        ranked = sorted(subset, key=lambda r: r["metrics"].get("balanced_accuracy", 0.0), reverse=True)
        if ranked:
            rank_count[ranked[0]["model_name"]] += 1
        for j, m in enumerate(models):
            run = next((r for r in subset if r["model_name"] == m), None)
            if run:
                acc_matrix[i, j] = run["metrics"].get("accuracy", 0.0)
                bacc_matrix[i, j] = run["metrics"].get("balanced_accuracy", 0.0)
                f1_matrix[i, j] = run["metrics"].get("f1_score", 0.0)
                roc_matrix[i, j] = run["metrics"].get("roc_auc", 0.0)
                pr_matrix[i, j] = run["metrics"].get("pr_auc", 0.0)
                p1_matrix[i, j] = run["metrics"].get("pred_majority_share", 0.0)
                gap_matrix[i, j] = run["metrics"].get("generalization_gap", 0.0)

    _plot_heatmap(acc_matrix, datasets, models, "Accuracy Heatmap (Dataset x Model)", "heatmap_accuracy.png")
    _plot_heatmap(bacc_matrix, datasets, models, "Balanced Accuracy Heatmap (Dataset x Model)", "heatmap_balanced_accuracy.png")
    _plot_heatmap(f1_matrix, datasets, models, "Macro-F1 Heatmap (Dataset x Model)", "heatmap_macro_f1.png")
    _plot_heatmap(roc_matrix, datasets, models, "ROC-AUC Heatmap (Dataset x Model)", "heatmap_roc_auc.png")
    _plot_heatmap(pr_matrix, datasets, models, "PR-AUC Heatmap (Dataset x Model)", "heatmap_pr_auc.png")
    _plot_heatmap(p1_matrix, datasets, models, "Prediction Top-1 Share Heatmap (Dataset x Model)", "heatmap_pred_top1_share.png")
    _plot_heatmap(gap_matrix, datasets, models, "Generalization Gap Heatmap (Dataset x Model)", "heatmap_generalization_gap.png", vmin=min(-1.0, float(np.min(gap_matrix)) if gap_matrix.size else -1.0), vmax=max(1.0, float(np.max(gap_matrix)) if gap_matrix.size else 1.0))

    _plot_bar(models, [rank_count[m] for m in models], "Top-1 Count Across Datasets", "Count", "model_top1_count.png", ylim_0_1=False)

    _plot_dataset_model_rank_matrix(results)
    _plot_average_confusion_matrices(results)
    _plot_loss_scatter(results)


# ----------------------------
# Selection and export
# ----------------------------
def aggregate_model_scores(results: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        grouped[r["model_name"]].append(r["metrics"])

    summary: dict[str, dict[str, float]] = {}
    for model_name, metrics_list in grouped.items():
        summary[model_name] = {
            "avg_accuracy": round(float(np.mean([m.get("accuracy", 0.0) for m in metrics_list])), 6),
            "avg_balanced_accuracy": round(float(np.mean([m.get("balanced_accuracy", 0.0) for m in metrics_list])), 6),
            "avg_precision": round(float(np.mean([m.get("precision", 0.0) for m in metrics_list])), 6),
            "avg_recall": round(float(np.mean([m.get("recall", 0.0) for m in metrics_list])), 6),
            "avg_macro_f1": round(float(np.mean([m.get("f1_score", 0.0) for m in metrics_list])), 6),
            "avg_roc_auc": round(float(np.mean([m.get("roc_auc", 0.0) for m in metrics_list])), 6),
            "avg_pr_auc": round(float(np.mean([m.get("pr_auc", 0.0) for m in metrics_list])), 6),
            "avg_train_loss": round(float(np.mean([m.get("train_loss", 0.0) for m in metrics_list])), 6),
            "avg_val_loss": round(float(np.mean([m.get("val_loss", 0.0) for m in metrics_list])), 6),
            "avg_generalization_gap": round(float(np.mean([m.get("generalization_gap", 0.0) for m in metrics_list])), 6),
            "num_runs": len(metrics_list),
        }
    return summary


def choose_best_model(summary: dict[str, dict[str, float]]) -> tuple[str, str]:
    ranked = sorted(
        summary.items(),
        key=lambda kv: (
            kv[1]["avg_macro_f1"],
            kv[1]["avg_roc_auc"],
            kv[1]["avg_pr_auc"],
            kv[1]["avg_balanced_accuracy"],
            -kv[1]["avg_generalization_gap"],
        ),
        reverse=True,
    )
    best_name, best_stats = ranked[0]
    reason = (
        f"avg_macro_f1={best_stats['avg_macro_f1']:.4f}; "
        f"avg_roc_auc={best_stats['avg_roc_auc']:.4f}; "
        f"avg_pr_auc={best_stats['avg_pr_auc']:.4f}; "
        f"avg_balanced_accuracy={best_stats['avg_balanced_accuracy']:.4f}; "
        f"generalization_gap={best_stats['avg_generalization_gap']:.4f}."
    )
    return best_name, reason


def train_best_on_merged_data(best_model_name: str, merged_df: pd.DataFrame, quick_results: list[dict[str, Any]]) -> None:
    X, y, groups, meta = build_sequences(merged_df, seq_len=SEQ_LEN)
    if len(X) < 50:
        raise ValueError("Merged dataset too small to train best model.")

    tr_idx, va_idx, te_idx = grouped_stratified_split(y, groups, seed=SEED)
    model_cls = MODEL_FACTORIES[best_model_name]
    model = model_cls(
        input_dim=X.shape[2],
        hidden_dim=HIDDEN_DIM,
        num_layers=NUM_LAYERS,
        num_classes=NUM_CLASSES,
    )

    best_run = train_model(
        model=model,
        dataset_name="merged_all_datasets",
        model_name=best_model_name,
        X_train=X[tr_idx],
        y_train=y[tr_idx],
        X_val=X[va_idx],
        y_val=y[va_idx],
        X_test=X[te_idx],
        y_test=y[te_idx],
        epochs=FULL_EPOCHS,
    )

    torch.save(best_run["state_dict"], ARTIFACTS_DIR / "model_best.pt")

    best_meta = {
        **meta,
        "model_name": best_model_name,
        "model_type": best_model_name,
        "hidden_dim": HIDDEN_DIM,
        "num_layers": NUM_LAYERS,
        "num_classes": NUM_CLASSES,
        "metrics": best_run["metrics"],
        "train_source": "kaggle_merged_real_datasets",
    }
    (ARTIFACTS_DIR / "model_best_meta.json").write_text(json.dumps(best_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save a dedicated confusion matrix for final deployed model
    cm = np.array(best_run["metrics"].get("confusion_matrix", np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.int64)))
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(len(ACTIONS)),
        yticks=np.arange(len(ACTIONS)),
        xticklabels=ACTIONS,
        yticklabels=ACTIONS,
        ylabel="True",
        xlabel="Predicted",
        title=f"Confusion Matrix - model_best ({best_model_name.upper()})",
    )
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "confusion_matrix_model_best.png", dpi=140)
    plt.close(fig)


# ----------------------------
# Main pipeline
# ----------------------------
def main() -> None:
    global MAX_ROWS_PER_DATASET, QUICK_EPOCHS, FULL_EPOCHS, BATCH_SIZE, MIN_DATASETS_REQUIRED
    runtime_cfg = resolve_runtime_config()
    # Apply runtime config to globals
    global USE_AMP, NUM_WORKERS, PIN_MEMORY
    USE_AMP = bool(runtime_cfg.get("amp", False))
    if runtime_cfg.get("num_workers") is not None:
        NUM_WORKERS = int(runtime_cfg.get("num_workers"))
    PIN_MEMORY = bool(runtime_cfg.get("pin_memory", PIN_MEMORY))

    # Enable cudnn benchmark for fixed-size inputs to improve performance on GPU
    try:
        if DEVICE.type == "cuda":
            torch.backends.cudnn.benchmark = True
    except Exception:
        pass
    MAX_ROWS_PER_DATASET = int(runtime_cfg["max_rows"])
    QUICK_EPOCHS = int(runtime_cfg["quick_epochs"])
    FULL_EPOCHS = int(runtime_cfg["full_epochs"])
    BATCH_SIZE = int(runtime_cfg["batch_size"])
    MIN_DATASETS_REQUIRED = int(runtime_cfg["min_datasets"])

    set_seed(SEED)
    print("=" * 80)
    print("KAGGLE PIPELINE: 5 DATASETS x 5 MODELS")
    print(f"Device: {DEVICE}")
    print(
        "Config: "
        f"mode={runtime_cfg['mode']} | max_rows={MAX_ROWS_PER_DATASET:,} | "
        f"quick_epochs={QUICK_EPOCHS} | full_epochs={FULL_EPOCHS} | "
        f"batch_size={BATCH_SIZE} | min_datasets={MIN_DATASETS_REQUIRED}"
    )
    print("=" * 80)

    loaders = {
        "retailrocket": load_retailrocket,
        "multi_category_store": load_multi_category,
        "instacart": load_instacart,
        "hm_fashion": load_hm_fashion,
        "olist": load_olist,
    }

    datasets: dict[str, pd.DataFrame] = {}
    for name, fn in loaders.items():
        try:
            cand = None
            if name in DATASET_CANDIDATE_PATHS:
                cand = find_existing_path(DATASET_CANDIDATE_PATHS[name])
            print(f"[RESOLVE] {name:<22} -> {cand}")
            df = fn(MAX_ROWS_PER_DATASET)
            if not df.empty:
                datasets[name] = df
                print(f"[OK] {name:<22} -> {len(df):,} rows")
            else:
                print(f"[SKIP] {name:<22} -> not found or empty")
        except Exception as exc:
            print(f"[ERR] {name:<22} -> {exc}")

    if len(datasets) > MIN_DATASETS_REQUIRED:
        datasets = dict(sorted(datasets.items(), key=lambda kv: len(kv[1]), reverse=True)[:MIN_DATASETS_REQUIRED])
        print(
            f"[INFO] Loaded more than {MIN_DATASETS_REQUIRED} datasets. "
            f"Keeping top {MIN_DATASETS_REQUIRED} by row count: {list(datasets.keys())}"
        )

    if len(datasets) < MIN_DATASETS_REQUIRED:
        raise RuntimeError(
            f"Need at least {MIN_DATASETS_REQUIRED} real datasets. "
            f"Loaded={len(datasets)} -> {list(datasets.keys())}. "
            "Please add more datasets in Kaggle Add Data."
        )

    dataset_report = {
        name: {
            "rows": int(len(df)),
            "unique_sessions": int(df["session_id"].nunique()),
            "unique_products": int(df["product_id"].nunique()),
            "actions": {k: int(v) for k, v in df["action"].value_counts().to_dict().items()},
        }
        for name, df in datasets.items()
    }
    (ARTIFACTS_DIR / "dataset_report.json").write_text(json.dumps(dataset_report, ensure_ascii=False, indent=2), encoding="utf-8")

    all_results: list[dict[str, Any]] = []

    for dataset_name, df in datasets.items():
        print(f"[INFO] {dataset_name}: building sequences...", flush=True)
        effective_seq_len = int(DATASET_SEQ_LEN_OVERRIDES.get(dataset_name, SEQ_LEN))
        X, y, groups, meta = build_sequences(df, seq_len=effective_seq_len)
        if len(X) < 50 and effective_seq_len != SEQ_LEN:
            print(
                f"[INFO] {dataset_name}: retrying with global seq_len={SEQ_LEN} because seq_len={effective_seq_len} produced too few samples",
                flush=True,
            )
            X, y, groups, meta = build_sequences(df, seq_len=SEQ_LEN)
        print(f"[INFO] {dataset_name}: sequences built -> {len(X):,}", flush=True)
        if len(X) < 50:
            print(f"[WARN] {dataset_name}: too few sequence samples ({len(X)}), skipping")
            continue

        label_counts = np.bincount(y.astype(np.int64), minlength=NUM_CLASSES)
        active_classes = [int(i) for i, c in enumerate(label_counts.tolist()) if c > 0]
        compact_counts = {ACTIONS[i]: int(label_counts[i]) for i in active_classes}
        print(
            f"[INFO] {dataset_name}: active target classes={active_classes} -> {compact_counts}",
            flush=True,
        )

        group_count = int(len(np.unique(groups))) if len(groups) else 0
        print(f"[INFO] {dataset_name}: unique sessions for splitting -> {group_count}", flush=True)

        print(f"[INFO] {dataset_name}: stratified split...", flush=True)
        tr_idx, va_idx, te_idx = grouped_stratified_split(y, groups, seed=SEED)
        X_train, y_train = X[tr_idx], y[tr_idx]
        X_val, y_val = X[va_idx], y[va_idx]
        X_test, y_test = X[te_idx], y[te_idx]

        print("-" * 80)
        print(f"Dataset: {dataset_name} | samples={len(X):,} | train={len(tr_idx):,} val={len(va_idx):,} test={len(te_idx):,}")

        for model_name, model_cls in MODEL_FACTORIES.items():
            print(f"  Training {model_name.upper()} on {dataset_name}...")
            model = model_cls(
                input_dim=X_train.shape[2],
                hidden_dim=HIDDEN_DIM,
                num_layers=NUM_LAYERS,
                num_classes=NUM_CLASSES,
            )
            result = train_model(
                model=model,
                dataset_name=dataset_name,
                model_name=model_name,
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                X_test=X_test,
                y_test=y_test,
                epochs=QUICK_EPOCHS,
            )

            # Save per-dataset checkpoint + meta for audit
            run_ckpt_name = f"{dataset_name}__{model_name}.pt"
            torch.save(result["state_dict"], ARTIFACTS_DIR / run_ckpt_name)
            run_meta = {
                **meta,
                "dataset_name": dataset_name,
                "model_name": model_name,
                "model_type": model_name,
                "hidden_dim": HIDDEN_DIM,
                "num_layers": NUM_LAYERS,
                "num_classes": NUM_CLASSES,
                "metrics": result["metrics"],
            }
            (ARTIFACTS_DIR / f"{dataset_name}__{model_name}_meta.json").write_text(
                json.dumps(run_meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            all_results.append(
                {
                    "dataset_name": dataset_name,
                    "model_name": model_name,
                    "model_type": model_name,
                    "metrics": result["metrics"],
                    "model_path": str(ARTIFACTS_DIR / run_ckpt_name),
                }
            )
            m = result["metrics"]
            print(
                f"    -> ACC={m['accuracy']:.4f} BACC={m['balanced_accuracy']:.4f} F1={m['f1_score']:.4f} "
                f"ROC={m['roc_auc']:.4f} PR={m['pr_auc']:.4f} GAP={m['generalization_gap']:.4f} "
                f"PRED_TOP1={m['pred_majority_share']:.4f}"
            )

    if not all_results:
        raise RuntimeError("No training results generated.")

    (ARTIFACTS_DIR / "all_runs_metrics_raw.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = aggregate_model_scores(all_results)
    best_model_name, reason = choose_best_model(summary)

    best_summary = {
        "model_best": best_model_name,
        "model_type": best_model_name,
        "all_models_summary": summary,
        "reason": reason,
        "datasets_used": sorted(datasets.keys()),
    }
    (ARTIFACTS_DIR / "model_best_summary.json").write_text(
        json.dumps(best_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Retrain best model on merged real datasets for deployment.
    merged_df = pd.concat(list(datasets.values()), ignore_index=True)
    train_best_on_merged_data(best_model_name, merged_df, all_results)

    # Compatibility files expected by current repo scripts.
    (ARTIFACTS_DIR / "all_model_results.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ARTIFACTS_DIR / "metrics_report.json").write_text(
        json.dumps([{"dataset": r["dataset_name"], "model": r["model_name"], **r["metrics"]} for r in all_results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    generate_plots(all_results)

    print("=" * 80)
    print(f"Best model: {best_model_name}")
    print(f"Reason    : {reason}")
    print(f"Artifacts : {ARTIFACTS_DIR}")
    print(f"Plots     : {PLOTS_DIR}")
    print("Done.")


if __name__ == "__main__":
    main()
