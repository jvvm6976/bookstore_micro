import json
import logging
import time
from pathlib import Path

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .orchestrator import orchestrator
from .services.recommendation import recommendation_service as rec_svc
from .services.behavior_analysis import behavior_service
from .services.kb_ingestion import kb_service
from .services.rag_retrieval import rag_service
from .ml.preprocess import BestModelPredictor
from .clients.order_client import order_client
from .clients.comment_client import comment_client
from .clients.catalog_client import catalog_client
from .infrastructure.graph.neo4j_adapter import neo4j_adapter

logger = logging.getLogger(__name__)
_best_model_predictor = BestModelPredictor(Path(__file__).resolve().parents[1] / "artifacts")


def _to_int(value, default):
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


def _to_float(value, default=None):
	if value is None:
		return default
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _add_interaction(interactions: dict[str, dict[int, int]], interaction_type: str, product_id: int, count: int = 1) -> None:
	if not product_id:
		return
	interactions.setdefault(interaction_type, {})
	interactions[interaction_type][product_id] = interactions[interaction_type].get(product_id, 0) + max(int(count or 1), 1)


def _interaction_totals(interactions: dict[str, dict[int, int]]) -> dict[str, int]:
	return {
		itype: sum(int(count or 0) for count in product_counts.values())
		for itype, product_counts in interactions.items()
	}


def _load_customer_signals(customer_id: int):
	interactions: dict[str, dict[int, int]] = {}
	event_sequence = []

	try:
		from django.apps import apps
		Interaction = apps.get_model('app', 'CustomerProductInteraction')
		qs = Interaction.objects.filter(customer_id=customer_id)
		for row in qs:
			itype = row.interaction_type
			_add_interaction(interactions, itype, int(row.product_id or 0), int(row.count or 1))
			event_sequence.append({
				'product_id': row.product_id,
				'action': itype,
				'interaction_type': itype,
				'timestamp': int(row.timestamp.timestamp()),
				'price_range': row.price_range,
				'category_idx': 0,
			})
	except Exception as exc:
		logger.debug('Could not load DB interactions: %s', exc)

	try:
		now_ts = int(time.time())
		orders = order_client.get_orders_by_customer(customer_id)
		for order in orders:
			for item in order.get('items', []):
				pid = item.get('product_id') or item.get('book_id')
				if not pid:
					continue
				_add_interaction(interactions, 'purchase', int(pid), int(item.get('quantity') or 1))
				event_sequence.append({
					'product_id': int(pid),
					'action': 'purchase',
					'interaction_type': 'purchase',
					'timestamp': now_ts,
					'price_range': 2,
					'category_idx': 0,
				})
	except Exception as exc:
		logger.debug('Could not load order signals: %s', exc)

	try:
		now_ts = int(time.time())
		comments = comment_client.get_all_comments()
		for c in comments:
			comment_owner = c.get('customer_id')
			if comment_owner is None:
				comment_owner = c.get('user_id')
			if comment_owner != customer_id:
				continue
			pid = c.get('product_id') or c.get('book_id')
			if not pid:
				continue
			_add_interaction(interactions, 'rate_product', int(pid), 1)
			event_sequence.append({
					'product_id': int(pid),
					'action': 'rate_product',
					'interaction_type': 'rate',
					'timestamp': now_ts,
					'price_range': 2,
					'category_idx': 0,
				})
	except Exception as exc:
		logger.debug('Could not load comment signals: %s', exc)

	return interactions, event_sequence


@api_view(['GET'])
def health(request):
	stats = kb_service.get_stats()
	from .infrastructure.ml.lstm_model import LSTM_MODEL_PATH
	best_model_path = Path("artifacts") / "model_best.pt"
	best_summary_path = Path("artifacts") / "model_best_summary.json"
	best_model_type = None
	if best_summary_path.exists():
		try:
			best_summary = json.loads(best_summary_path.read_text(encoding="utf-8"))
			best_model_type = best_summary.get("model_best")
		except Exception:
			best_model_type = None
	return Response({
		'service': 'recommender-ai-service',
		'status': 'healthy',
		'kb_stats': stats,
		'lstm_loaded': LSTM_MODEL_PATH.exists() or best_model_path.exists(),
		'model_best_loaded': best_model_path.exists(),
		'model_best_type': best_model_type,
		'graph_enabled': neo4j_adapter.is_available(),
		'hybrid_weights': {'lstm': 0.40, 'graph': 0.25, 'content': 0.25, 'rating': 0.10},
	})


@api_view(['POST'])
def chat(request):
	try:
		result = orchestrator.process(
			message=request.data.get('message', ''),
			customer_id=request.data.get('customer_id'),
			session_id=request.data.get('session_id'),
			quick_action=request.data.get('quick_action'),
		)
		return Response(result)
	except Exception as exc:
		logger.exception('Chat error: %s', exc)
		return Response({
			'answer': 'Xin lỗi, tôi gặp sự cố kỹ thuật. Bạn thử lại sau nhé! 🙏',
			'intent': 'fallback',
			'session_id': request.data.get('session_id', ''),
			'recommendations': [],
		})


@api_view(['GET'])
def recommend(request, customer_id):
	try:
		limit = _to_int(request.GET.get('limit'), 8)
		category = request.GET.get('category')
		budget_max = _to_float(request.GET.get('budget_max'))
		interactions, event_sequence = _load_customer_signals(customer_id)
		model_best_prediction = None
		if event_sequence:
			try:
				model_best_prediction = _best_model_predictor.predict_next_action(event_sequence)
			except Exception as exc:
				logger.debug('Could not infer model_best for recommend: %s', exc)
		recs = rec_svc.get_personalized(
			customer_id=customer_id,
			interactions=interactions,
			limit=max(1, min(limit, 20)),
			budget_max=budget_max,
			category=category,
			event_sequence=event_sequence,
			model_best_prediction=model_best_prediction,
		)
		return Response({'customer_id': customer_id, 'recommendations': recs, 'source': 'lstm_hybrid'})
	except Exception as exc:
		logger.exception('Recommend error: %s', exc)
		return Response({'error': str(exc)}, status=500)


@api_view(['GET'])
def similar(request, product_id):
	try:
		limit = _to_int(request.GET.get('limit'), 6)
		items = rec_svc.get_similar(product_id=product_id, limit=max(1, min(limit, 12)))
		return Response({'product_id': product_id, 'similar': items})
	except Exception as exc:
		logger.exception('Similar error: %s', exc)
		return Response({'error': str(exc)}, status=500)


@api_view(['GET'])
def popular(request):
	try:
		limit = _to_int(request.GET.get('limit'), 8)
		items = rec_svc.get_popular(limit=max(1, min(limit, 20)))
		return Response({'items': items, 'source': 'popular'})
	except Exception as exc:
		logger.exception('Popular error: %s', exc)
		return Response({'error': str(exc)}, status=500)


@api_view(['GET'])
def collaborative(request, customer_id):
	try:
		limit = _to_int(request.GET.get('limit'), 6)
		raw = neo4j_adapter.get_collaborative_recs(customer_id=customer_id, limit=max(1, min(limit, 20)))
		books = {int(b['id']): b for b in catalog_client.get_all_products(limit=500) if b.get('id')}
		items = []
		for r in raw:
			pid = int(r.get('product_id') or 0)
			b = books.get(pid)
			if not b:
				continue
			items.append({
				'product_id': pid,
				'title': b.get('title', ''),
				'author': b.get('author', ''),
				'category': b.get('category', ''),
				'price': float(b.get('price', 0) or 0),
				'score': float(r.get('support', 0) or 0),
				'reason': 'nguoi dung tuong tu cung mua',
				'avg_rating': 0.0,
			})
		return Response({'customer_id': customer_id, 'items': items[:limit], 'source': 'graph_collaborative'})
	except Exception as exc:
		logger.exception('Collaborative error: %s', exc)
		return Response({'error': str(exc)}, status=500)


@api_view(['GET'])
def analyze_customer(request, customer_id):
	try:
		interactions, event_sequence = _load_customer_signals(customer_id)
		profile = behavior_service.analyze(
			customer_id=customer_id,
			interactions=_interaction_totals(interactions),
			event_sequence=event_sequence if event_sequence else None,
		)
		profile['customer_id'] = customer_id
		return Response(profile)
	except Exception as exc:
		logger.exception('Analyze error: %s', exc)
		return Response({'error': str(exc)}, status=500)


@api_view(['POST'])
def track(request):
	try:
		customer_id = _to_int(request.data.get('customer_id'), 0)
		product_id = _to_int(request.data.get('product_id'), 0)
		interaction_type = request.data.get('interaction_type', '')
		rating = request.data.get('rating')
		if not customer_id or not interaction_type:
			return Response({'error': 'customer_id and interaction_type are required'}, status=400)

		from django.apps import apps
		Interaction = apps.get_model('app', 'CustomerProductInteraction')

		type_alias = {
			'click': 'view_detail',
			'view': 'view_detail',
			'cart': 'add_to_cart',
			'rate': 'rate_product',
		}
		normalized_type = type_alias.get(interaction_type, interaction_type)

		obj, created = Interaction.objects.get_or_create(
			customer_id=customer_id,
			product_id=product_id,
			interaction_type=normalized_type,
			defaults={'count': 1, 'rating': rating},
		)
		if not created:
			obj.count += 1
			if rating is not None:
				obj.rating = rating
			obj.save(update_fields=['count', 'rating', 'timestamp'])

		if product_id:
			rel_map = {
				'search': 'SEARCHED',
				'view_detail': 'VIEWED',
				'add_to_cart': 'ADDED_TO_CART',
				'purchase': 'PURCHASED',
				'rate_product': 'RATED',
				'wishlist': 'WISHLISTED',
				'remove_from_cart': 'REMOVED_FROM_CART',
				'click_recommendation': 'CLICKED_RECOMMENDATION',
			}
			rel_type = rel_map.get(normalized_type, 'VIEWED')
			product_meta = {}
			try:
				p = catalog_client.get_product_by_id(product_id)
				if p:
					product_meta = {
						'name': p.get('title', ''),
						'category': p.get('category', ''),
						'brand': p.get('brand', ''),
						'price': p.get('price', 0),
					}
			except Exception:
				pass
			neo4j_adapter.write_interaction(
				customer_id=customer_id,
				product_id=product_id,
				rel_type=rel_type,
				props={'rating': rating or 0},
				product_meta=product_meta,
			)

		return Response({'tracked': True, 'customer_id': customer_id, 'product_id': product_id, 'type': normalized_type})
	except Exception as exc:
		logger.warning('Track failed: %s', exc)
		return Response({'tracked': False, 'error': str(exc)}, status=500)


@api_view(['POST'])
def kb_reindex(request):
	try:
		count = kb_service.reindex()
		rag_service.build_index()
		return Response({'indexed': count, 'message': f'KB reindexed: {count} entries'})
	except Exception as exc:
		logger.exception('KB reindex error: %s', exc)
		return Response({'error': str(exc)}, status=500)


@api_view(['GET'])
def kb_status(request):
	stats = kb_service.get_stats()
	from .core.config import FAISS_INDEX_PATH
	return Response({
		'total_entries': stats.get('total_entries', 0),
		'by_category': stats.get('by_category', {}),
		'faiss_indexed': FAISS_INDEX_PATH.exists(),
		'index_size': stats.get('total_entries', 0),
	})
