"""
Saga Orchestrator – Order Creation
Steps:
  1. Create Order (PENDING)
  2. Reserve Payment
  3. Reserve Shipping
  4. Confirm Order (PAID)
  5. Compensate on any failure
"""
import logging
import requests

logger = logging.getLogger(__name__)

CART_SVC   = 'http://cart-service:8000'
PAY_SVC    = 'http://pay-service:8000'
SHIP_SVC   = 'http://ship-service:8000'
BOOK_SVC   = 'http://book-service:8000'

_TIMEOUT = 15


def _post(url, data):
    return requests.post(url, json=data, timeout=_TIMEOUT)

def _patch(url, data):
    return requests.patch(url, json=data, timeout=_TIMEOUT)


class OrderSaga:
    """
    Orchestrates the distributed order transaction.
    Returns a result dict with keys: success, order, error, steps.
    """

    def __init__(self, order, items, cart_id, payment_method, shipping_address):
        self.order = order
        self.items = items          # list of {book_id, quantity, price}
        self.cart_id = cart_id
        self.payment_method = payment_method
        self.shipping_address = shipping_address
        self.payment_id = None
        self.shipment_id = None
        self.steps = []

    # ── public entry point ────────────────────────────────────────────────────

    def execute(self):
        try:
            self._step_reserve_payment()
            self._step_reserve_shipping()
            self._step_confirm_order()
            self._step_clear_cart()
            self._step_update_stock()
            return {'success': True, 'order': self.order, 'steps': self.steps}
        except SagaException as exc:
            logger.error('Saga failed at step %s: %s', exc.step, exc.reason)
            self._compensate(exc.step)
            return {'success': False, 'error': exc.reason, 'steps': self.steps, 'order': self.order}

    # ── saga steps ────────────────────────────────────────────────────────────

    def _step_reserve_payment(self):
        resp = _post(f'{PAY_SVC}/api/payments/process/', {
            'order_id': self.order.id,
            'amount': float(self.order.total_amount),
            'payment_method': self.payment_method,
        })
        if resp.status_code not in (200, 201):
            raise SagaException('reserve_payment', f'Payment failed: {resp.text}')
        data = resp.json()
        if data.get('status') not in ('success', 'pending'):
            raise SagaException('reserve_payment', f'Payment declined: {data}')
        self.payment_id = data.get('payment', {}).get('id')
        self.steps.append({'step': 'reserve_payment', 'status': 'ok', 'payment_id': self.payment_id})

    def _step_reserve_shipping(self):
        resp = _post(f'{SHIP_SVC}/api/shipments/create_shipment/', {
            'order_id': self.order.id,
            'address': self.shipping_address,
            'customer_id': self.order.customer_id,
            'shipping_method': 'standard',
        })
        if resp.status_code not in (200, 201):
            raise SagaException('reserve_shipping', f'Shipping failed: {resp.text}')
        data = resp.json()
        self.shipment_id = data.get('shipment', {}).get('id')
        self.steps.append({'step': 'reserve_shipping', 'status': 'ok', 'shipment_id': self.shipment_id})

    def _step_confirm_order(self):
        from .models import OrderStatus
        self.order.status = OrderStatus.PAID
        self.order.save(update_fields=['status'])
        self.steps.append({'step': 'confirm_order', 'status': 'ok'})

    def _step_clear_cart(self):
        if not self.cart_id:
            return
        for item in self.items:
            try:
                _post(f'{CART_SVC}/api/carts/{self.cart_id}/update_item_quantity/', {
                    'book_id': item['book_id'], 'quantity': 0,
                })
            except Exception:
                pass
        self.steps.append({'step': 'clear_cart', 'status': 'ok'})

    def _step_update_stock(self):
        """Decrement stock for each book ordered."""
        for item in self.items:
            try:
                book_resp = requests.get(f'{BOOK_SVC}/api/books/{item["book_id"]}/', timeout=5)
                if book_resp.status_code == 200:
                    current_stock = book_resp.json().get('stock', 0)
                    new_stock = max(0, current_stock - item['quantity'])
                    requests.patch(
                        f'{BOOK_SVC}/api/books/{item["book_id"]}/update_stock/',
                        json={'stock': new_stock}, timeout=5,
                    )
            except Exception:
                pass
        self.steps.append({'step': 'update_stock', 'status': 'ok'})

    # ── compensation ──────────────────────────────────────────────────────────

    def _compensate(self, failed_step):
        logger.warning('Compensating saga from step: %s', failed_step)
        from .models import OrderStatus
        self.order.status = OrderStatus.CANCELED
        self.order.save(update_fields=['status'])
        self.steps.append({'step': 'compensate_order', 'status': 'ok'})

        if failed_step in ('reserve_shipping', 'confirm_order', 'clear_cart', 'update_stock'):
            if self.payment_id:
                try:
                    _post(f'{PAY_SVC}/api/payments/{self.payment_id}/refund/', {})
                    self.steps.append({'step': 'compensate_payment', 'status': 'ok'})
                except Exception as e:
                    self.steps.append({'step': 'compensate_payment', 'status': 'failed', 'error': str(e)})

        if failed_step in ('confirm_order', 'clear_cart', 'update_stock'):
            if self.shipment_id:
                try:
                    _patch(f'{SHIP_SVC}/api/shipments/{self.shipment_id}/', {'status': 'cancelled'})
                    self.steps.append({'step': 'compensate_shipping', 'status': 'ok'})
                except Exception as e:
                    self.steps.append({'step': 'compensate_shipping', 'status': 'failed', 'error': str(e)})


class SagaException(Exception):
    def __init__(self, step, reason):
        self.step = step
        self.reason = reason
        super().__init__(f'[{step}] {reason}')
