import logging
import time

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .orchestrator import orchestrator
from .services.recommendation import recommendation_service as rec_svc
from .services.behavior_analysis import behavior_service
from .services.kb_ingestion import kb_service
from .services.rag_retrieval import rag_service
from .clients.order_client import order_client
from .clients.comment_client import comment_client
from .clients.catalog_client import catalog_client
from .infrastructure.graph.neo4j_adapter import neo4j_adapter

logger = logging.getLogger(__name__)
_kb_bootstrapped = False


def _ensure_kb_loaded():
	global _kb_bootstrapped
	if _kb_bootstrapped and kb_service.get_stats().get('total_entries', 0) > 0:
		return
	count = kb_service.load_from_disk()
	ok = rag_service.load_index()
	if not ok and count > 0:
		rag_service.build_index()
	_kb_bootstrapped = True


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


def _load_customer_signals(customer_id: int):
	interactions = {}
	event_sequence = []

	def add_interaction(itype, product_id, count=1):
		if not product_id:
			return
		pid = int(product_id)
		interactions.setdefault(itype, {})
		interactions[itype][pid] = interactions[itype].get(pid, 0) + int(count or 1)

	try:
		from django.apps import apps
		Interaction = apps.get_model('app', 'CustomerProductInteraction')
		qs = Interaction.objects.filter(customer_id=customer_id)
		for row in qs:
			itype = row.interaction_type
			add_interaction(itype, row.product_id, row.count)
			event_sequence.append({
				'product_id': row.product_id,
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
				# order-service OrderItem uses product_id
				pid = item.get('product_id')
				if not pid:
					continue
				add_interaction('purchase', pid)
				event_sequence.append({
					'product_id': int(pid),
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
			# comment-service Review uses user_id and product_id
			if c.get('user_id') != customer_id:
				continue
				pid = c.get('product_id')
				if not pid:
					continue
				add_interaction('rate', pid)
				event_sequence.append({
					'product_id': int(pid),
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
	_ensure_kb_loaded()
	stats = kb_service.get_stats()
	from .infrastructure.ml.lstm_model import LSTM_MODEL_PATH
	return Response({
		'service': 'recommender-ai-service',
		'status': 'healthy',
		'kb_stats': stats,
		'lstm_loaded': LSTM_MODEL_PATH.exists(),
		'graph_enabled': neo4j_adapter.is_available(),
		'hybrid_weights': {'lstm': 0.40, 'graph': 0.25, 'content': 0.25, 'rating': 0.10},
	})


@api_view(['POST'])
def chat(request):
	try:
		_ensure_kb_loaded()
		result = orchestrator.process(
			message=request.data.get('message', ''),
			customer_id=request.data.get('customer_id'),
			session_id=request.data.get('session_id'),
			quick_action=request.data.get('quick_action'),
		)
		return Response(result)
	except Exception as exc:
		logger.exception('Chat error: %s', exc)
		return Response({'error': str(exc)}, status=500)


@api_view(['GET'])
def recommend(request, customer_id):
	try:
		limit = _to_int(request.GET.get('limit'), 8)
		category = request.GET.get('category')
		budget_max = _to_float(request.GET.get('budget_max'))
		interactions, event_sequence = _load_customer_signals(customer_id)
		recs = rec_svc.get_personalized(
			customer_id=customer_id,
			interactions=interactions,
			limit=max(1, min(limit, 20)),
			budget_max=budget_max,
			category=category,
			event_sequence=event_sequence,
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
def recommend_by_query(request):
	"""
	Alias endpoint for frontend/gateway compatibility.
	Called as: GET /recommend/recommendations/?user_id=<id>&limit=<n>
	Returns: { recommended_product_ids: [...], recommendations: [...] }
	"""
	try:
		customer_id = _to_int(request.GET.get('user_id'), 0)
		limit = _to_int(request.GET.get('limit'), 8)
		if not customer_id:
			# Return popular items when no user_id provided
			items = rec_svc.get_popular(limit=max(1, min(limit, 20)))
			product_ids = [item.get('product_id') or item.get('id') for item in items if item.get('product_id') or item.get('id')]
			return Response({
				'recommended_product_ids': product_ids,
				'recommendations': items,
				'source': 'popular',
			})
		interactions, event_sequence = _load_customer_signals(customer_id)
		recs = rec_svc.get_personalized(
			customer_id=customer_id,
			interactions=interactions,
			limit=max(1, min(limit, 20)),
			event_sequence=event_sequence,
		)
		product_ids = [r.get('product_id') or r.get('id') for r in recs if r.get('product_id') or r.get('id')]
		return Response({
			'recommended_product_ids': product_ids,
			'recommendations': recs,
			'source': 'lstm_hybrid',
		})
	except Exception as exc:
		logger.exception('recommend_by_query error: %s', exc)
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
			interactions=interactions,
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
		global _kb_bootstrapped
		count = kb_service.reindex()
		rag_service.build_index()
		_kb_bootstrapped = True
		return Response({'indexed': count, 'message': f'KB reindexed: {count} entries'})
	except Exception as exc:
		logger.exception('KB reindex error: %s', exc)
		return Response({'error': str(exc)}, status=500)


@api_view(['GET'])
def kb_status(request):
	_ensure_kb_loaded()
	stats = kb_service.get_stats()
	from .core.config import FAISS_INDEX_PATH
	return Response({
		'total_entries': stats.get('total_entries', 0),
		'by_category': stats.get('by_category', {}),
		'faiss_indexed': FAISS_INDEX_PATH.exists(),
		'index_size': stats.get('total_entries', 0),
	})
