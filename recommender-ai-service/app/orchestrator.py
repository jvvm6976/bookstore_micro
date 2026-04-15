"""
ChatOrchestrator
─────────────────
Central coordinator for the chatbot pipeline:

  message → IntentDetector → EntityExtractor
         → [module dispatch] → ResponseComposer → ChatResponse

Each intent routes to the appropriate service(s).
"""
from __future__ import annotations
import logging
import re
import uuid
from typing import Any

from .services.intent_detector  import detect as detect_intent
from .services.entity_extractor import extract as extract_entities
from .services.rag_retrieval    import retrieve as rag_retrieve, build_context_string
from .services.recommendation   import recommendation_service as rec_svc
from .services.behavior_analysis import behavior_service
from .services.order_support    import order_support_service
from .services.response_composer import compose

logger = logging.getLogger(__name__)

# In-memory session store (replace with Redis for production)
_sessions: dict[str, list[dict]] = {}
_session_recommendations: dict[str, list[dict]] = {}
MAX_HISTORY = 6


def _get_history(session_id: str) -> list[dict]:
    return _sessions.get(session_id, [])[-MAX_HISTORY:]


def _save_message(session_id: str, role: str, content: str) -> None:
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": role, "content": content})
    # Trim
    if len(_sessions[session_id]) > MAX_HISTORY * 2:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY * 2:]


def _save_recommendations(session_id: str, recommendations: list[dict]) -> None:
    if not recommendations:
        return
    normalized: list[dict] = []
    for r in recommendations[:8]:
        normalized.append({
            "product_id": r.get("product_id") or r.get("id"),
            "title": r.get("title", ""),
            "author": r.get("author", ""),
            "category": r.get("category", ""),
            "price": float(r.get("price", 0) or 0),
            "stock": r.get("stock"),
            "score": float(r.get("score", 0) or 0),
            "reason": r.get("reason", "kết quả gợi ý gần nhất"),
            "avg_rating": float(r.get("avg_rating", 0) or 0),
        })
    _session_recommendations[session_id] = normalized


def _get_recent_recommendations(session_id: str) -> list[dict]:
    return _session_recommendations.get(session_id, [])


def _infer_book_title_from_history(session_id: str, current_message: str) -> str | None:
    """Infer likely title from recent messages for follow-up questions like "bao nhieu tien?"."""
    history = _get_history(session_id)
    for item in reversed(history):
        text = (item.get("content") or "").strip()
        if not text or text == current_message:
            continue

        # Prefer markdown/bold title from assistant messages.
        m = re.search(r"\*\*([^*]{2,80})\*\*", text)
        if m:
            cand = m.group(1).strip()
            if cand and not re.search(r"(gợi ý|goi y|kết quả|ket qua|thông tin|thong tin)", cand, re.I):
                return cand

    return None


def _infer_book_titles_from_history(session_id: str, current_message: str, max_items: int = 5) -> list[str]:
    """Infer a list of recent candidate titles from assistant messages."""
    history = _get_history(session_id)
    titles: list[str] = []
    seen: set[str] = set()
    for item in reversed(history):
        text = (item.get("content") or "").strip()
        if not text or text == current_message:
            continue
        for m in re.finditer(r"\*\*([^*]{2,80})\*\*", text):
            cand = m.group(1).strip()
            if not cand:
                continue
            if re.search(r"(gợi ý|goi y|kết quả|ket qua|thông tin|thong tin)", cand, re.I):
                continue
            key = cand.lower()
            if key in seen:
                continue
            seen.add(key)
            titles.append(cand)
            if len(titles) >= max_items:
                return titles
    return titles


def _get_interactions(customer_id: int) -> dict[str, dict[int, int]]:
    """Load interaction counts from DB via Django ORM."""
    try:
        from django.apps import apps
        CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")
        qs = CustomerBookInteraction.objects.filter(customer_id=customer_id)
        result: dict[str, dict[int, int]] = {}
        for ix in qs:
            result.setdefault(ix.interaction_type, {})[ix.book_id] = ix.count
        return result
    except Exception as exc:
        logger.debug("Could not load interactions: %s", exc)
        return {}


def _get_customer_ratings(customer_id: int) -> dict[int, int]:
    """Extract customer's own rating history: {book_id: rating_value}."""
    try:
        from django.apps import apps
        CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")
        qs = CustomerBookInteraction.objects.filter(
            customer_id=customer_id,
            interaction_type="rate",
            rating__isnull=False
        )
        result: dict[int, int] = {}
        for ix in qs:
            if ix.rating is not None:
                result[ix.book_id] = ix.rating
        logger.debug("Loaded %d ratings for C%s", len(result), customer_id)
        return result
    except Exception as exc:
        logger.debug("Could not load customer ratings: %s", exc)
        return {}


def _get_bestseller_from_interactions(limit: int = 8) -> list[dict]:
    """Build bestseller list from tracked purchase/cart/view interactions."""
    try:
        from django.apps import apps
        from django.db.models import Sum
        from .clients.catalog_client import catalog_client

        CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")
        # Prefer purchase signal, then cart/view as weaker fallback signals.
        rows = (
            CustomerBookInteraction.objects
            .filter(interaction_type__in=["purchase", "cart", "view"])
            .values("book_id", "interaction_type")
            .annotate(total=Sum("count"))
        )

        # Aggregate weighted engagement per book.
        weighted: dict[int, float] = {}
        for r in rows:
            bid = int(r.get("book_id") or 0)
            if not bid:
                continue
            itype = str(r.get("interaction_type") or "")
            total = float(r.get("total") or 0)
            w = 6.0 if itype == "purchase" else (2.0 if itype == "cart" else 1.0)
            weighted[bid] = weighted.get(bid, 0.0) + (total * w)

        if not weighted:
            return []

        all_books = catalog_client.get_all_products(limit=500)
        book_map = {
            int(b.get("id")): b for b in all_books
            if b.get("id") and int(b.get("stock", 0) or 0) > 0
        }

        ranked_ids = sorted(weighted.keys(), key=lambda bid: weighted.get(bid, 0), reverse=True)
        out: list[dict] = []
        for bid in ranked_ids:
            b = book_map.get(bid)
            if not b:
                continue
            out.append({
                "product_id": b.get("id"),
                "title": b.get("title", ""),
                "author": b.get("author", ""),
                "category": b.get("category", ""),
                "price": float(b.get("price", 0) or 0),
                "stock": int(b.get("stock", 0) or 0),
                "score": round(float(weighted.get(bid, 0)), 3),
                "reason": "bán chạy theo lịch sử mua gần đây",
                "avg_rating": 0,
            })
            if len(out) >= limit:
                break
        return out
    except Exception as exc:
        logger.debug("Could not build bestseller from interactions: %s", exc)
        return []


class ChatOrchestrator:
    def process(
        self,
        message:      str,
        customer_id:  int | None = None,
        session_id:   str | None = None,
        quick_action: str | None = None,
    ) -> dict[str, Any]:
        """
        Full pipeline: detect → extract → dispatch → compose.
        Returns ChatResponse-compatible dict.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        _save_message(session_id, "user", message)

        # 1. Intent detection
        intent, confidence = detect_intent(message, quick_action)
        logger.info("Intent=%s (%.2f) | C%s | msg=%s", intent, confidence, customer_id, message[:60])

        # 2. Entity extraction
        entities = extract_entities(message, intent)

        # Context-aware follow-up: if user asks price/stock without explicit filters/title,
        # reuse recent title from session. Do not infer when user provides budget filters.
        has_budget_filter = bool(
            entities.get("budget_min") is not None or entities.get("budget_max") is not None
        )
        if (
            (entities.get("ask_price") or entities.get("ask_stock"))
            and not entities.get("book_title")
            and not has_budget_filter
        ):
            inferred_title = _infer_book_title_from_history(session_id, message)
            if inferred_title:
                entities["book_title"] = inferred_title
                intent = "general_search"

        if entities.get("ask_best_price") and not entities.get("book_title") and not entities.get("book_titles"):
            inferred_titles = _infer_book_titles_from_history(session_id, message, max_items=6)
            if inferred_titles:
                entities["book_titles"] = inferred_titles
                intent = "general_search"

        # Force follow-up intent for contextual commerce Q&A.
        has_explicit_filter = bool(
            entities.get("budget_min") is not None
            or entities.get("budget_max") is not None
            or entities.get("book_titles")
            or entities.get("ask_compare_price")
            or entities.get("ask_next_book")
            or entities.get("ask_bestseller")
            or entities.get("ask_new_books")
            or entities.get("ask_same_author")
        )
        if (entities.get("ask_price") or entities.get("ask_stock") or entities.get("ask_best_price")) and not has_explicit_filter:
            intent = "general_search"

        if (
            entities.get("ask_compare_price")
            or entities.get("ask_next_book")
            or entities.get("ask_bestseller")
            or entities.get("ask_new_books")
            or entities.get("ask_same_author")
        ):
            intent = "general_search"

        # Any explicit budget filter should be treated as product search.
        if entities.get("budget_min") is not None or entities.get("budget_max") is not None:
            intent = "general_search"

        # 3. Dispatch to services
        data: dict[str, Any] = {}
        recommendations: list[dict] = []
        sources: list[dict] = []

        if intent in ("faq", "return_policy", "payment_support", "shipping_support"):
            # RAG retrieval from KB
            category_map = {
                "return_policy":    "policy",
                "payment_support":  "policy",
                "shipping_support": "policy",
                "faq":              None,
            }
            kb_cat = category_map.get(intent)
            entries = rag_retrieve(message, top_k=3, category=kb_cat)
            sources = entries
            data["sources"] = entries

        elif intent == "product_advice":
            # Behavior + Recommendation + RAG context
            interactions = _get_interactions(customer_id) if customer_id else {}
            customer_ratings = _get_customer_ratings(customer_id) if customer_id else {}
            flat_interactions = {
                itype: {bid: cnt for bid, cnt in book_counts.items()}
                for itype, book_counts in interactions.items()
            }

            direct_title = entities.get("book_title")
            if direct_title:
                from .clients.catalog_client import catalog_client
                from .clients.comment_client import comment_client as cc

                direct_books = catalog_client.search_products(
                    query=direct_title,
                    category=entities.get("category"),
                    min_price=entities.get("budget_min"),
                    max_price=entities.get("budget_max"),
                )
                if direct_books:
                    # Boost books whose titles contain the requested phrase.
                    ql = str(direct_title).lower()
                    direct_books.sort(
                        key=lambda b: (ql in str(b.get("title", "")).lower(), float(b.get("price", 0) or 0)),
                        reverse=True,
                    )
                    pids = [b.get("id") for b in direct_books if b.get("id")]
                    ratings = cc.get_reviews_for_products(pids) if pids else {}
                    matched_recs = []
                    for b in direct_books[:3]:
                        bid = b.get("id")
                        rm = ratings.get(bid, {})
                        matched_recs.append({
                            "product_id": bid,
                            "title": b.get("title", ""),
                            "author": b.get("author", ""),
                            "category": b.get("category", ""),
                            "price": float(b.get("price", 0) or 0),
                            "score": float(rm.get("avg", 0) or 0),
                            "reason": "khớp theo tên sách bạn đang tìm",
                            "avg_rating": round(float(rm.get("avg", 0) or 0), 2),
                        })

                    # Add similar books around the top match to keep recommendation behavior.
                    top_match_id = matched_recs[0].get("product_id") if matched_recs else None
                    if top_match_id:
                        similar = rec_svc.get_similar(int(top_match_id), limit=3, customer_ratings=customer_ratings)
                        recommendations = matched_recs + similar
                    else:
                        recommendations = matched_recs

                    data["recommendations"] = recommendations
                else:
                    data["not_found_title"] = direct_title

            recs = rec_svc.get_personalized(
                customer_id=customer_id or 0,
                interactions=flat_interactions,
                customer_ratings=customer_ratings,
                budget_min=entities.get("budget_min"),
                budget_max=entities.get("budget_max"),
                category=entities.get("category"),
            )

            # If category-constrained results are too generic, relax category to expose
            # stronger customer-specific ranking signals.
            if recs and all(float(r.get("score", 0) or 0) <= 0 for r in recs):
                relaxed = rec_svc.get_personalized(
                    customer_id=customer_id or 0,
                    interactions=flat_interactions,
                    customer_ratings=customer_ratings,
                    budget_min=entities.get("budget_min"),
                    budget_max=entities.get("budget_max"),
                    category=None,
                )
                if relaxed:
                    recs = relaxed

            # If no personalized recs, fall back to popular
            if not recs:
                recs = rec_svc.get_popular(limit=5)
            if not recommendations:
                recommendations = recs
                data["recommendations"] = recs

            # RAG context for additional context
            rag_entries = rag_retrieve(message, top_k=2, category="book")
            data["rag_context"] = build_context_string(rag_entries)
            sources = rag_entries

        elif intent == "order_support":
            if not customer_id:
                data["order_data"] = {
                    "found":   False,
                    "message": "Vui lòng đăng nhập để tra cứu đơn hàng của bạn. 🔒",
                }
            else:
                order_id = entities.get("order_id")
                data["order_data"] = order_support_service.get_order_info(customer_id, order_id)

        elif intent == "general_search":
            keywords = entities.get("product_keywords", [])
            query = " ".join(keywords) if keywords else message
            category = entities.get("category")
            from .clients.catalog_client import catalog_client

            customer_ratings = _get_customer_ratings(customer_id) if customer_id else {}
            recent_recs = _get_recent_recommendations(session_id)
            is_followup = bool(entities.get("ask_price") or entities.get("ask_stock") or entities.get("ask_best_price"))
            has_explicit_filter = bool(
                entities.get("budget_min") is not None
                or entities.get("budget_max") is not None
                or entities.get("book_titles")
                or entities.get("ask_compare_price")
                or entities.get("ask_next_book")
                or entities.get("ask_bestseller")
                or entities.get("ask_new_books")
                or entities.get("ask_same_author")
            )

            if entities.get("ask_bestseller"):
                recommendations = _get_bestseller_from_interactions(limit=8)
                if not recommendations:
                    recommendations = rec_svc.get_popular(limit=8)
                if not recommendations:
                    # Last-resort fallback if no rating + no interaction signal.
                    all_books = catalog_client.get_all_products(limit=300)
                    all_books = [b for b in all_books if (b.get("id") and int(b.get("stock", 0) or 0) > 0)]
                    all_books.sort(key=lambda b: int(b.get("stock", 0) or 0), reverse=True)
                    for b in all_books[:8]:
                        recommendations.append({
                            "product_id": b.get("id"),
                            "title": b.get("title", ""),
                            "author": b.get("author", ""),
                            "category": b.get("category", ""),
                            "price": float(b.get("price", 0) or 0),
                            "stock": int(b.get("stock", 0) or 0),
                            "score": 0.0,
                            "reason": "được quan tâm nhiều trong kho",
                            "avg_rating": 0,
                        })
                data["recommendations"] = recommendations
                data["sources"] = []

            elif entities.get("ask_new_books"):
                all_books = catalog_client.get_all_products(limit=300)
                all_books = [b for b in all_books if (b.get("id") and int(b.get("stock", 0) or 0) > 0)]
                all_books.sort(key=lambda b: int(b.get("id", 0) or 0), reverse=True)
                recommendations = []
                for b in all_books[:8]:
                    recommendations.append({
                        "product_id": b.get("id"),
                        "title": b.get("title", ""),
                        "author": b.get("author", ""),
                        "category": b.get("category", ""),
                        "price": float(b.get("price", 0) or 0),
                        "stock": int(b.get("stock", 0) or 0),
                        "score": 0.0,
                        "reason": "mới lên kệ",
                        "avg_rating": 0,
                    })
                data["recommendations"] = recommendations
                data["sources"] = []

            elif entities.get("ask_same_author"):
                author = entities.get("author")
                if not author and entities.get("book_title"):
                    found = catalog_client.search_products(query=str(entities.get("book_title")))
                    if found:
                        author = found[0].get("author")
                if author:
                    all_books = catalog_client.get_all_products(limit=400)
                    books = [
                        b for b in all_books
                        if author.lower() in str(b.get("author", "")).lower()
                    ]
                    books.sort(key=lambda b: float(b.get("price", 0) or 0))
                    recommendations = []
                    for b in books[:8]:
                        recommendations.append({
                            "product_id": b.get("id"),
                            "title": b.get("title", ""),
                            "author": b.get("author", ""),
                            "category": b.get("category", ""),
                            "price": float(b.get("price", 0) or 0),
                            "stock": int(b.get("stock", 0) or 0),
                            "score": 0.0,
                            "reason": f"cùng tác giả {author}",
                            "avg_rating": 0,
                        })
                    data["resolved_author"] = author
                data["recommendations"] = recommendations
                data["sources"] = []

            elif entities.get("ask_next_book"):
                base_id = None
                if recent_recs:
                    base_id = recent_recs[0].get("product_id")
                if not base_id and entities.get("book_title"):
                    found = catalog_client.search_products(query=str(entities.get("book_title")))
                    if found:
                        base_id = found[0].get("id")
                if base_id:
                    recommendations = rec_svc.get_similar(int(base_id), limit=8, customer_ratings=customer_ratings)
                data["recommendations"] = recommendations
                data["sources"] = []

            elif entities.get("ask_compare_price") and entities.get("book_titles"):
                books_map: dict[int, dict] = {}
                for t in entities.get("book_titles", [])[:3]:
                    matches = catalog_client.search_products(query=str(t))
                    if matches:
                        ql = str(t).lower()
                        matches.sort(key=lambda b: (ql in str(b.get("title", "")).lower(), int(b.get("id", 0) or 0)), reverse=True)
                        b = matches[0]
                        bid = b.get("id")
                        if bid and bid not in books_map:
                            books_map[bid] = b
                recommendations = []
                for b in books_map.values():
                    recommendations.append({
                        "product_id": b.get("id"),
                        "title": b.get("title", ""),
                        "author": b.get("author", ""),
                        "category": b.get("category", ""),
                        "price": float(b.get("price", 0) or 0),
                        "stock": int(b.get("stock", 0) or 0),
                        "score": 0.0,
                        "reason": "đối tượng so sánh giá",
                        "avg_rating": 0,
                    })
                data["recommendations"] = recommendations
                data["sources"] = []

            elif is_followup and recent_recs and not has_explicit_filter:
                recommendations = recent_recs[:8]
                data["recommendations"] = recommendations
                data["sources"] = []
            else:
                # Search products
                if entities.get("book_titles"):
                    books_map: dict[int, dict] = {}
                    for t in entities.get("book_titles", []):
                        for b in catalog_client.search_products(
                            query=str(t),
                            category=category,
                            min_price=entities.get("budget_min"),
                            max_price=entities.get("budget_max"),
                        ):
                            bid = b.get("id")
                            if bid and bid not in books_map:
                                books_map[bid] = b
                    books = list(books_map.values())
                elif entities.get("book_title"):
                    books = catalog_client.search_products(
                        query=str(entities.get("book_title")),
                        category=category,
                        min_price=entities.get("budget_min"),
                        max_price=entities.get("budget_max"),
                    )
                elif (
                    (entities.get("ask_price") or entities.get("ask_best_price"))
                    and (entities.get("budget_min") is not None or entities.get("budget_max") is not None)
                ):
                    # Price-only commerce query: avoid fulltext search term pollution like "gia tren 200000".
                    all_books = catalog_client.get_all_products(limit=500)
                    books = []
                    for b in all_books:
                        p = float(b.get("price", 0) or 0)
                        if entities.get("budget_min") is not None and p < float(entities.get("budget_min") or 0):
                            continue
                        if entities.get("budget_max") is not None and p > float(entities.get("budget_max") or 0):
                            continue
                        if category and b.get("category") != category:
                            continue
                        books.append(b)
                else:
                    books = catalog_client.search_products(
                        query=query,
                        category=category,
                        min_price=entities.get("budget_min"),
                        max_price=entities.get("budget_max"),
                    )
                # Format as recommendations
                from .clients.comment_client import comment_client as cc
                product_ids = [b["id"] for b in books if b.get("id")]
                ratings = cc.get_reviews_for_products(product_ids) if product_ids else {}
                recs = []
                for b in books[:8]:
                    bid = b.get("id")
                    rm  = ratings.get(bid, {})
                    recs.append({
                        "product_id": bid,
                        "title":      b.get("title", ""),
                        "author":     b.get("author", ""),
                        "category":   b.get("category", ""),
                        "price":      float(b.get("price", 0)),
                        "stock":      int(b.get("stock", 0) or 0),
                        "score":      rm.get("avg", 0),
                        "reason":     "kết quả tìm kiếm",
                        "avg_rating": round(rm.get("avg", 0), 2),
                    })
                recommendations = recs
                data["recommendations"] = recs

                # Only use RAG fallback for non-commerce queries.
                is_commerce_query = bool(
                    entities.get("ask_price")
                    or entities.get("ask_stock")
                    or entities.get("ask_best_price")
                    or entities.get("ask_compare_price")
                    or entities.get("ask_next_book")
                    or entities.get("ask_bestseller")
                    or entities.get("ask_new_books")
                    or entities.get("ask_same_author")
                    or entities.get("budget_min") is not None
                    or entities.get("budget_max") is not None
                )
                if not is_commerce_query:
                    rag_entries = rag_retrieve(message, top_k=2)
                    sources = rag_entries
                    data["sources"] = rag_entries

        else:  # fallback
            entries = rag_retrieve(message, top_k=2)
            sources = entries
            data["sources"] = entries

        # 4. Compose response
        answer = compose(intent, entities, data, customer_id)
        _save_message(session_id, "assistant", answer)
        _save_recommendations(session_id, recommendations)

        books_payload = []
        for r in recommendations:
            books_payload.append({
                "id":         r.get("id") or r.get("product_id"),
                "title":      r.get("title", ""),
                "author":     r.get("author", ""),
                "category":   r.get("category", ""),
                "price":      r.get("price", 0),
                "avg_rating": r.get("avg_rating", 0),
            })

        return {
            "session_id":      session_id,
            "intent":          intent,
            "confidence":      round(confidence, 3),
            "answer":          answer,
            "response":        answer,
            "recommendations": recommendations,
            "books":           books_payload,
            "sources":         [{"title": s["title"], "snippet": s["content"][:150]} for s in sources],
            "meta": {
                "entities":    entities,
                "customer_id": customer_id,
            },
        }


orchestrator = ChatOrchestrator()
