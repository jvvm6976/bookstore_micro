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
from pathlib import Path
from typing import Any

from .services.intent_detector  import detect as detect_intent
from .services.entity_extractor import extract as extract_entities
from .services.rag_retrieval    import retrieve_with_graph_hints, build_context_string
from .services.recommendation   import recommendation_service as rec_svc
from .services.behavior_analysis import behavior_service
from .services.order_support    import order_support_service
from .services.response_composer import compose
from .graph.graph_queries import (
    get_user_interested_categories,
    get_user_interested_subcategories,
    get_customer_graph_hints,
    get_top_recommended_products,
)
from .ml.preprocess import BestModelPredictor
from .services.text_normalizer import strip_vietnamese_accents

logger = logging.getLogger(__name__)

# In-memory session store (replace with Redis for production)
_sessions: dict[str, list[dict]] = {}
_session_recommendations: dict[str, list[dict]] = {}
MAX_HISTORY = 6
_best_model_predictor = BestModelPredictor(Path(__file__).resolve().parents[1] / "artifacts")


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


def _enrich_recommendations_with_catalog(recommendations: list[dict]) -> list[dict]:
    if not recommendations:
        return recommendations
    try:
        from .clients.catalog_client import catalog_client
    except Exception:
        return recommendations

    cache: dict[int, dict] = {}
    for rec in recommendations:
        try:
            pid = int(rec.get("product_id") or rec.get("id") or 0)
        except (TypeError, ValueError):
            pid = 0
        if not pid:
            continue
        if pid not in cache:
            try:
                cache[pid] = catalog_client.get_product_by_id(pid) or {}
            except Exception:
                cache[pid] = {}
        product = cache.get(pid) or {}
        if not product:
            continue
        for key in (
            "id", "product_id", "name", "title", "description", "sku",
            "category", "category_name", "domain_id", "domain_name",
            "price", "stock", "image_url", "cover_image_url",
        ):
            if rec.get(key) in (None, "") and product.get(key) not in (None, ""):
                rec[key] = product.get(key)
    return recommendations


def _explicit_catalog_recommendations(
    message: str,
    entities: dict[str, Any],
    customer_ratings: dict[int, int],
    limit: int = 5,
) -> list[dict]:
    """Prioritize catalog items that directly match the current request."""
    from .clients.catalog_client import catalog_client
    from .clients.comment_client import comment_client

    category = entities.get("category")
    raw_keywords = [
        strip_vietnamese_accents(str(value)).lower()
        for value in entities.get("product_keywords", [])
        if len(str(value).strip()) >= 3
    ]
    keywords = [] if category else raw_keywords
    original_message = message.lower()
    folded_message = strip_vietnamese_accents(message).lower()
    synonym_terms = []
    synonym_map = {
        "tai nghe": ["headphone", "noise cancel"],
        "chong on": ["noise cancel", "headphone"],
        "lam sach da": ["cleanser", "skincare"],
        "sua rua mat": ["cleanser", "skincare"],
        "cham soc da": ["skincare", "cleanser"],
        "nuoc hoa": ["fragrance", "parfum"],
        "thoi trang": ["fashion", "womens", "mens", "shoes"],
        "phat trien ban than": ["habits", "startup", "non-fiction"],
        "so ghi chep": ["notebook", "stationery"],
        "ghi chep": ["notebook", "stationery"],
        "do dung gia dinh": ["home", "kitchen", "cookware", "appliance"],
    }
    for phrase, terms in synonym_map.items():
        if phrase in folded_message:
            synonym_terms.extend(terms)
    if re.search(r"(?<!\w)(sách|sach)(?!\w)", original_message):
        synonym_terms.extend(["books", "non-fiction", "fiction", "science"])
    query_terms = list(dict.fromkeys(keywords + synonym_terms))

    scored = []
    for product in catalog_client.get_all_products(limit=500):
        if not product.get("id") or int(product.get("stock", 0) or 0) <= 0:
            continue
        text = strip_vietnamese_accents(" ".join([
            str(product.get("title") or product.get("name") or ""),
            str(product.get("description") or ""),
            str(product.get("category") or product.get("category_name") or ""),
            str(product.get("domain_name") or ""),
            str(product.get("brand") or ""),
        ])).lower()
        score = 0
        if category and product.get("category") == category:
            score += 20
        title_text = strip_vietnamese_accents(str(product.get("title") or "")).lower()
        for term in query_terms:
            pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
            if re.search(pattern, text):
                score += 8 if re.search(pattern, title_text) else 3
        if score > 0:
            scored.append((score, product))

    if not scored:
        return []

    scored.sort(key=lambda item: (item[0], float(item[1].get("price", 0) or 0)), reverse=True)
    product_ids = [product["id"] for _, product in scored[:limit]]
    rating_map = comment_client.get_reviews_for_products(product_ids)
    result = []
    for score, product in scored[:limit]:
        product_id = product["id"]
        if customer_ratings.get(product_id, 5) < 3:
            continue
        rating = rating_map.get(product_id, {})
        result.append({
            "product_id": product_id,
            "title": product.get("title") or product.get("name") or "",
            "author": product.get("author", ""),
            "category": product.get("category") or product.get("category_name") or "",
            "domain_name": product.get("domain_name") or "",
            "price": float(product.get("price", 0) or 0),
            "score": float(score),
            "reason": "khớp trực tiếp với nhu cầu bạn vừa mô tả",
            "avg_rating": round(float(rating.get("avg", 0) or 0), 2),
        })
    return result


def _merge_recommendations(*groups: list[dict], limit: int = 8) -> list[dict]:
    merged = []
    seen = set()
    for group in groups:
        for item in group:
            product_id = int(item.get("product_id") or item.get("id") or 0)
            if not product_id or product_id in seen:
                continue
            seen.add(product_id)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


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
    """Load product-level interaction counts from DB plus completed order history."""
    result: dict[str, dict[int, int]] = {}

    def add(itype: str, pid: int, count: int = 1) -> None:
        if not pid:
            return
        result.setdefault(itype, {})
        result[itype][pid] = result[itype].get(pid, 0) + max(int(count or 1), 1)

    try:
        from django.apps import apps
        # Support both old (CustomerBookInteraction) and new (CustomerProductInteraction) model names
        try:
            Interaction = apps.get_model("app", "CustomerProductInteraction")
            id_field = "product_id"
        except LookupError:
            Interaction = apps.get_model("app", "CustomerBookInteraction")
            id_field = "book_id"
        qs = Interaction.objects.filter(customer_id=customer_id)
        for ix in qs:
            pid = getattr(ix, id_field, None) or getattr(ix, "product_id", None) or getattr(ix, "book_id", 0)
            add(ix.interaction_type, int(pid or 0), int(ix.count or 1))
    except Exception as exc:
        logger.debug("Could not load interactions: %s", exc)

    try:
        from .clients.order_client import order_client

        for order in order_client.get_orders_by_customer(customer_id):
            for item in order.get("items", []):
                pid = item.get("product_id") or item.get("book_id")
                add("purchase", int(pid or 0), int(item.get("quantity") or 1))
    except Exception as exc:
        logger.debug("Could not load order interactions: %s", exc)

    return result


def _get_customer_ratings(customer_id: int) -> dict[int, int]:
    """Extract customer's own rating history: {product_id: rating_value}."""
    try:
        from django.apps import apps
        try:
            Interaction = apps.get_model("app", "CustomerProductInteraction")
            id_field = "product_id"
        except LookupError:
            Interaction = apps.get_model("app", "CustomerBookInteraction")
            id_field = "book_id"
        qs = Interaction.objects.filter(
            customer_id=customer_id,
            interaction_type__in=["rate", "rate_product"],
            rating__isnull=False,
        )
        result: dict[int, int] = {}
        for ix in qs:
            pid = getattr(ix, id_field, None) or getattr(ix, "product_id", None) or getattr(ix, "book_id", 0)
            if ix.rating is not None:
                result[pid] = ix.rating
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

        try:
            Interaction = apps.get_model("app", "CustomerProductInteraction")
            id_field = "product_id"
        except LookupError:
            Interaction = apps.get_model("app", "CustomerBookInteraction")
            id_field = "book_id"

        rows = (
            Interaction.objects
            .filter(interaction_type__in=["purchase", "cart", "add_to_cart", "view", "view_detail"])
            .values(id_field, "interaction_type")
            .annotate(total=Sum("count"))
        )

        weighted: dict[int, float] = {}
        for r in rows:
            pid = int(r.get(id_field) or 0)
            if not pid:
                continue
            itype = str(r.get("interaction_type") or "")
            total = float(r.get("total") or 0)
            w = 6.0 if itype == "purchase" else (2.0 if itype in {"cart", "add_to_cart"} else 1.0)
            weighted[pid] = weighted.get(pid, 0.0) + (total * w)

        if not weighted:
            return []

        all_books = catalog_client.get_all_products(limit=500)
        book_map = {
            int(b.get("id")): b for b in all_books
            if b.get("id") and int(b.get("stock", 0) or 0) > 0
        }

        ranked_ids = sorted(weighted.keys(), key=lambda pid: weighted.get(pid, 0), reverse=True)
        out: list[dict] = []
        for pid in ranked_ids:
            b = book_map.get(pid)
            if not b:
                continue
            out.append({
                "product_id": b.get("id"),
                "title":      b.get("title", ""),
                "author":     b.get("author", ""),
                "category":   b.get("category", ""),
                "price":      float(b.get("price", 0) or 0),
                "stock":      int(b.get("stock", 0) or 0),
                "score":      round(float(weighted.get(pid, 0)), 3),
                "reason":     "bán chạy theo lịch sử mua gần đây",
                "avg_rating": 0,
            })
            if len(out) >= limit:
                break
        return out
    except Exception as exc:
        logger.debug("Could not build bestseller from interactions: %s", exc)
        return []


def _build_model_sequence_from_interactions(interactions: dict[str, dict[int, int]]) -> list[dict]:
    sequence: list[dict] = []
    step = 0
    for interaction_type, items in interactions.items():
        for pid, count in items.items():
            for _ in range(min(int(count), 3)):
                step += 1
                sequence.append(
                    {
                        "step": step,
                        "user_id": 0,
                        "product_id": int(pid),
                        "category": "unknown",
                        "sub_category": "unknown",
                        "action": interaction_type,
                        "action_type": interaction_type,
                        "interaction_type": interaction_type,
                        "price": 0,
                        "rating": 0,
                        "cart_value": 0,
                        "timestamp": 0,
                        "device": "desktop",
                        "source": "organic",
                        "intent": "browse",
                        "segment": "casual",
                    }
                )
    return sequence[-12:]


def _graph_hints_for_customer(customer_id: int | None) -> list[str]:
    if not customer_id:
        return []
    hints: list[str] = []
    try:
        hints.extend(get_customer_graph_hints(customer_id, limit=6))
    except Exception as exc:
        logger.debug("Could not collect graph hints: %s", exc)
    return [hint for hint in hints if hint]


_TITLE_STOPWORDS = {
    "san", "pham", "sản", "phẩm", "product", "item", "mat", "hang", "mặt", "hàng",
    "cuon", "cuốn", "quyen", "quyển", "sach", "sách", "gia", "giá", "price",
    "bao", "nhieu", "nhiêu", "con", "còn", "hang", "hàng", "khong", "không",
}


def _title_tokens(value: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9À-ỹ]+", str(value or "").lower())
    return [t for t in tokens if len(t) >= 2 and t not in _TITLE_STOPWORDS]


def _catalog_title_matches(query: str, limit: int = 8, strict: bool = True) -> list[dict]:
    """Find catalog products by title without accepting unrelated keyword-search noise."""
    from .clients.catalog_client import catalog_client

    q = str(query or "").strip()
    q_lower = q.lower()
    q_tokens = _title_tokens(q)
    if not q_tokens:
        return []

    min_score = 0.72 if strict and len(q_tokens) >= 3 else (0.55 if strict else 0.35)
    scored: list[tuple[float, dict]] = []
    for product in catalog_client.get_all_products(limit=500):
        title = str(product.get("title") or product.get("name") or "")
        title_lower = title.lower()
        title_tokens = set(_title_tokens(title))
        if not title_tokens:
            continue

        overlap = len([t for t in q_tokens if t in title_tokens])
        score = overlap / max(len(q_tokens), 1)
        if q_lower and q_lower in title_lower:
            score = 1.0
        elif overlap == len(q_tokens):
            score = 0.96
        elif q_tokens and q_tokens[0] in title_tokens:
            score += 0.08

        if score >= min_score:
            scored.append((score, product))

    scored.sort(key=lambda item: (item[0], int(item[1].get("id", 0) or 0)), reverse=True)
    return [product for _, product in scored[:limit]]


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
            or entities.get("book_title")
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

        if (
            (entities.get("ask_price") or entities.get("ask_stock"))
            and (entities.get("book_title") or entities.get("book_titles"))
        ):
            intent = "general_search"

        # Any explicit budget filter should be treated as product search.
        if entities.get("budget_min") is not None or entities.get("budget_max") is not None:
            intent = "general_search"

        # 3. Dispatch to services
        data: dict[str, Any] = {}
        recommendations: list[dict] = []
        sources: list[dict] = []
        graph_sources: list[dict] = []
        model_best_prediction: dict[str, Any] | None = None

        if intent in ("faq", "return_policy", "payment_support", "shipping_support"):
            # RAG retrieval from KB
            category_map = {
                "return_policy":    "policy",
                "payment_support":  "policy",
                "shipping_support": "policy",
                "faq":              None,
            }
            kb_cat = category_map.get(intent)
            entries = retrieve_with_graph_hints(message, graph_hints=[], top_k=3, category=kb_cat)
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
            if customer_id and _best_model_predictor.available:
                try:
                    seq = _build_model_sequence_from_interactions(interactions)
                    if seq:
                        model_best_prediction = _best_model_predictor.predict_next_action(seq)
                except Exception as exc:
                    logger.debug("model_best inference unavailable in product_advice: %s", exc)

            direct_title = entities.get("book_title")
            if direct_title:
                from .clients.catalog_client import catalog_client
                from .clients.comment_client import comment_client as cc

                direct_books = _catalog_title_matches(str(direct_title), limit=6, strict=True)
                if entities.get("budget_min") is not None:
                    direct_books = [b for b in direct_books if float(b.get("price", 0) or 0) >= float(entities.get("budget_min") or 0)]
                if entities.get("budget_max") is not None:
                    direct_books = [b for b in direct_books if float(b.get("price", 0) or 0) <= float(entities.get("budget_max") or 0)]
                if entities.get("category"):
                    direct_books = [b for b in direct_books if b.get("category") == entities.get("category")]
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
                            "reason": "khớp theo tên sản phẩm bạn đang tìm",
                            "avg_rating": round(float(rm.get("avg", 0) or 0), 2),
                        })

                    # Add similar products around the top match to keep recommendation behavior.
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
                model_best_prediction=model_best_prediction,
            )
            explicit_recs = _explicit_catalog_recommendations(
                message,
                entities,
                customer_ratings,
            )
            if explicit_recs:
                explicit_domains = {
                    item.get("domain_name")
                    for item in explicit_recs
                    if item.get("domain_name")
                }
                related_personalized = [
                    item for item in recs
                    if not explicit_domains or item.get("domain_name") in explicit_domains
                ]
                recs = _merge_recommendations(explicit_recs, related_personalized)

            if customer_id:
                try:
                    from .clients.catalog_client import catalog_client

                    graph_cat = get_user_interested_categories(customer_id, limit=3)
                    graph_subcats = get_user_interested_subcategories(customer_id, limit=3)
                    graph_sources.extend(
                        [
                            {
                                "title": "graph_category_interest",
                                "content": f"{g.get('category')}:{g.get('score')}",
                                "source_type": "graph",
                            }
                            for g in graph_cat
                        ]
                    )
                    graph_sources.extend(
                        [
                            {
                                "title": "graph_subcategory_interest",
                                "content": f"{g.get('subcategory')}:{g.get('score')}",
                                "source_type": "graph",
                            }
                            for g in graph_subcats
                        ]
                    )

                    graph_top = get_top_recommended_products(customer_id, limit=4)
                    if graph_top:
                        all_books = {int(b.get("id")): b for b in catalog_client.get_all_products(limit=500) if b.get("id")}
                        graph_items = []
                        for g in graph_top:
                            pid = int(g.get("product_id") or 0)
                            b = all_books.get(pid)
                            if not b:
                                continue
                            graph_items.append(
                                {
                                    "product_id": pid,
                                    "title": b.get("title", ""),
                                    "author": b.get("author", ""),
                                    "category": b.get("category", ""),
                                    "price": float(b.get("price", 0) or 0),
                                    "score": float(g.get("score", 0) or 0),
                                    "reason": "phù hợp với nhóm sản phẩm bạn hay quan tâm",
                                    "avg_rating": 0,
                                }
                            )

                        existing = {int(r.get("product_id") or r.get("id") or 0) for r in recs}
                        for gi in graph_items:
                            if (
                                gi["product_id"] not in existing
                                and (
                                    not entities.get("category")
                                    or gi.get("category") == entities.get("category")
                                )
                            ):
                                recs.append(gi)
                except Exception as exc:
                    logger.debug("Graph enrichment failed in product_advice: %s", exc)

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
            rag_entries = retrieve_with_graph_hints(
                message,
                graph_hints=_graph_hints_for_customer(customer_id),
                top_k=2,
                category=None,
            )
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
                or entities.get("book_title")
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
                    found = _catalog_title_matches(str(entities.get("book_title")), limit=1, strict=True)
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
                    found = _catalog_title_matches(str(entities.get("book_title")), limit=1, strict=True)
                    if found:
                        base_id = found[0].get("id")
                if base_id:
                    recommendations = rec_svc.get_similar(int(base_id), limit=8, customer_ratings=customer_ratings)
                data["recommendations"] = recommendations
                data["sources"] = []

            elif entities.get("ask_compare_price") and entities.get("book_titles"):
                books_map: dict[int, dict] = {}
                for t in entities.get("book_titles", [])[:3]:
                    matches = _catalog_title_matches(str(t), limit=3, strict=True)
                    if matches:
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
                        found = _catalog_title_matches(str(t), limit=8, strict=True)
                        if category:
                            found = [b for b in found if b.get("category") == category]
                        if entities.get("budget_min") is not None:
                            found = [b for b in found if float(b.get("price", 0) or 0) >= float(entities.get("budget_min") or 0)]
                        if entities.get("budget_max") is not None:
                            found = [b for b in found if float(b.get("price", 0) or 0) <= float(entities.get("budget_max") or 0)]
                        for b in found:
                            bid = b.get("id")
                            if bid and bid not in books_map:
                                books_map[bid] = b
                    books = list(books_map.values())
                elif entities.get("book_title"):
                    books = _catalog_title_matches(str(entities.get("book_title")), limit=8, strict=True)
                    if category:
                        books = [b for b in books if b.get("category") == category]
                    if entities.get("budget_min") is not None:
                        books = [b for b in books if float(b.get("price", 0) or 0) >= float(entities.get("budget_min") or 0)]
                    if entities.get("budget_max") is not None:
                        books = [b for b in books if float(b.get("price", 0) or 0) <= float(entities.get("budget_max") or 0)]
                    if not books and category:
                        all_books = catalog_client.get_all_products(limit=500)
                        books = [
                            b for b in all_books
                            if b.get("category") == category and int(b.get("stock", 0) or 0) > 0
                        ]
                        if entities.get("budget_min") is not None:
                            books = [b for b in books if float(b.get("price", 0) or 0) >= float(entities.get("budget_min") or 0)]
                        if entities.get("budget_max") is not None:
                            books = [b for b in books if float(b.get("price", 0) or 0) <= float(entities.get("budget_max") or 0)]
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
                elif category:
                    all_books = catalog_client.get_all_products(limit=500)
                    books = [
                        b for b in all_books
                        if b.get("category") == category and int(b.get("stock", 0) or 0) > 0
                    ]
                    if entities.get("budget_min") is not None:
                        books = [b for b in books if float(b.get("price", 0) or 0) >= float(entities.get("budget_min") or 0)]
                    if entities.get("budget_max") is not None:
                        books = [b for b in books if float(b.get("price", 0) or 0) <= float(entities.get("budget_max") or 0)]
                else:
                    books = catalog_client.search_products(
                        query=query,
                        category_slug=category,
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
                    rag_entries = retrieve_with_graph_hints(
                        message,
                        graph_hints=_graph_hints_for_customer(customer_id),
                        top_k=2,
                    )
                    sources = rag_entries
                    data["sources"] = rag_entries

            if customer_id:
                try:
                    graph_cat = get_user_interested_categories(customer_id, limit=3)
                    graph_sources.extend(
                        [
                            {
                                "title": "graph_category_interest",
                                "content": f"{g.get('category')}:{g.get('score')}",
                                "source_type": "graph",
                            }
                            for g in graph_cat
                        ]
                    )
                except Exception as exc:
                    logger.debug("Graph enrichment failed in general_search: %s", exc)

        else:  # fallback
            try:
                entries = retrieve_with_graph_hints(
                    message,
                    graph_hints=_graph_hints_for_customer(customer_id),
                    top_k=2,
                )
                sources = entries
                data["sources"] = entries
            except Exception as exc:
                logger.warning("Fallback RAG retrieval failed: %s", exc)
                data["sources"] = []

        # 4. Compose response
        if customer_id and _best_model_predictor.available:
            try:
                if model_best_prediction is None:
                    interactions = _get_interactions(customer_id)
                    seq = _build_model_sequence_from_interactions(interactions)
                    if seq:
                        model_best_prediction = _best_model_predictor.predict_next_action(seq)
                if model_best_prediction:
                    data["model_best_prediction"] = model_best_prediction
            except Exception as exc:
                logger.debug("model_best inference unavailable: %s", exc)

        recommendations = _enrich_recommendations_with_catalog(recommendations)
        if data.get("recommendations"):
            data["recommendations"] = _enrich_recommendations_with_catalog(data["recommendations"])

        answer = compose(intent, entities, data, customer_id)
        _save_message(session_id, "assistant", answer)
        _save_recommendations(session_id, recommendations)

        products_payload = []
        for r in recommendations:
            products_payload.append({
                "id":         r.get("id") or r.get("product_id"),
                "product_id": r.get("id") or r.get("product_id"),
                "name":       r.get("name") or r.get("title", ""),
                "title":      r.get("title", ""),
                "author":     r.get("author", ""),
                "category":   r.get("category", ""),
                "category_name": r.get("category_name") or r.get("category", ""),
                "domain_name": r.get("domain_name", ""),
                "price":      r.get("price", 0),
                "stock":      r.get("stock"),
                "image_url":  r.get("image_url", ""),
                "avg_rating": r.get("avg_rating", 0),
            })

        return {
            "session_id":      session_id,
            "intent":          intent,
            "confidence":      round(confidence, 3),
            "answer":          answer,
            "response":        answer,
            "recommendations": recommendations,
            "products":        products_payload,
            "items":           products_payload,
            "sources":         [{"title": s["title"], "snippet": s["content"][:150]} for s in sources],
            "meta": {
                "entities":    entities,
                "customer_id": customer_id,
            },
        }


orchestrator = ChatOrchestrator()
