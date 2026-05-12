# AI Assistant Service

Django-based AI service cho hệ thống e-commerce MoonBooks.

## Kiến trúc

```
recommender-ai-service/
├── main.py                          # Legacy compatibility stub (runtime uses Django)
├── app/
│   ├── views.py                     # Django REST endpoints
│   ├── urls.py                      # URL mapping for /health + /api/v1/*
│   ├── orchestrator.py              # ChatOrchestrator (pipeline điều phối)
│   ├── services/
│   │   ├── intent_detector.py       # Phát hiện intent (regex + scoring)
│   │   ├── entity_extractor.py      # Trích xuất entities (budget, category, order_id...)
│   │   ├── behavior_analysis.py     # PyTorch MLP + rule-based fallback
│   │   ├── recommendation.py        # Personalized + similar + popular
│   │   ├── kb_ingestion.py          # Knowledge Base builder (seed + books + reviews)
│   │   ├── rag_retrieval.py         # FAISS + TF-IDF + keyword fallback
│   │   ├── order_support.py         # Order + shipment + payment lookup
│   │   └── response_composer.py     # Per-intent response formatter
│   ├── clients/
│   │   ├── base.py                  # HTTP client với retry/timeout
│   │   ├── catalog_client.py        # → product-service (source of truth)
│   │   ├── order_client.py          # → order-service
│   │   ├── comment_client.py        # → comment-rate-service
│   │   ├── ship_client.py           # → ship-service
│   │   ├── pay_client.py            # → pay-service
│   │   └── customer_client.py       # → user-service (compat)
│   └── core/config.py               # Env config
├── recommender_ai_service/          # Django project settings/urls/wsgi/asgi
├── scripts/train_model.py           # Train BehaviorMLP với synthetic data
├── data/seed_kb.json                # FAQ + policy seed data
└── artifacts/                       # behavior_model.pt, kb_faiss.index
```

## API Endpoints

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/health` | Health check + KB stats |
| POST | `/api/v1/chat` | Chatbot (tất cả intents) |
| GET | `/api/v1/recommend/{customer_id}` | Gợi ý cá nhân hóa |
| GET | `/api/v1/recommend/similar/{product_id}` | Sản phẩm tương tự |
| GET | `/api/v1/analyze-customer/{customer_id}` | Phân tích hành vi |
| POST | `/api/v1/track` | Track interaction |
| POST | `/api/v1/kb/reindex` | Reindex KB từ tất cả sources |
| GET | `/api/v1/kb/status` | KB status |

Health check: `http://localhost:8011/health`

## Intents

| Intent | Trigger | Xử lý |
|--------|---------|-------|
| `product_advice` | "gợi ý sách", "recommend" | Behavior + Recommendation + RAG |
| `return_policy` | "đổi trả", "refund" | KB + RAG |
| `payment_support` | "thanh toán", "payment" | KB + RAG |
| `shipping_support` | "giao hàng", "ship" | KB + RAG |
| `order_support` | "đơn hàng", "order" | order-service + ship-service + pay-service |
| `general_search` | "tìm sách", "search" | product-service + RAG |
| `faq` | "faq", "hỏi đáp" | KB + RAG |
| `fallback` | không nhận ra | RAG fallback |

## Quick Actions

```json
{"message": "...", "quick_action": "recommend"}      // → product_advice
{"message": "...", "quick_action": "return_policy"}  // → return_policy
{"message": "...", "quick_action": "order_support"}  // → order_support
{"message": "...", "quick_action": "payment_support"}// → payment_support
```

## Deep Learning Model

Hybrid sequence modeling:
- LSTM (PyTorch/TensorFlow) cho chuỗi hành vi: view/click/add_to_cart/purchase/rate
- Output: purchase_propensity_score + customer_segment
- Fallback: BehaviorMLP/rule-based khi thiếu checkpoint

Train: `python scripts/train_model.py`

## RAG Pipeline

1. KB ingestion: seed FAQ + products từ product-service + reviews từ comment-service
2. TF-IDF vectorization → FAISS IndexFlatIP
3. Query → vector → FAISS search → keyword fallback
4. Top-k entries → ResponseComposer

## Chạy

```bash
# Build và start
docker compose up --build recommender-ai-service

# Reindex KB (sau khi books đã được seed)
curl -X POST http://localhost:8000/api/v1/kb/reindex

# Chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Gợi ý sách AI cho người mới dưới 300k", "customer_id": 1}'

# Stack status (Django + LSTM + RAG + Graph + Chatbot)
curl http://localhost:8011/health
```
