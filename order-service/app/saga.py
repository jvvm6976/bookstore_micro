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
import os
import requests

logger = logging.getLogger(__name__)

CART_SVC = os.environ.get('CART_SERVICE_URL', 'http://cart-service:8000')
PAY_SVC = os.environ.get('PAYMENT_SERVICE_URL', 'http://payment-service:8000')
SHIP_SVC = os.environ.get('SHIPPING_SERVICE_URL', 'http://shipping-service:8000')
PRODUCT_SVC = os.environ.get('PRODUCT_SERVICE_URL', 'http://product-service:8000')

_TIMEOUT = 15


def _post(url, data):
    return requests.post(url, json=data, timeout=_TIMEOUT)

def _patch(url, data):
    return requests.patch(url, json=data, timeout=_TIMEOUT)


def _delete(url):
    return requests.delete(url, timeout=_TIMEOUT)


def _item_product_id(item):
    return item.get('product_id') or item.get('book_id')


class OrderSaga:
    """
    Orchestrates the distributed order transaction.
    Returns a result dict with keys: success, order, error, steps.
    """

    def __init__(self, order, items, cart_id, payment_method, shipping_address):
        self.order = order
        self.items = items          # list of {product_id, quantity, price}
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
        resp = _post(f'{PAY_SVC}/internal/payments/', {
            'order_id': self.order.id,
            'amount': float(self.order.total_price),
            'payment_method': self.payment_method,
        })
        if resp.status_code not in (200, 201):
            raise SagaException('reserve_payment', f'Payment failed: {resp.text}')
        data = resp.json()
        if data.get('overall_status') not in ('success', 'pending'):
            raise SagaException('reserve_payment', f'Payment declined: {data}')
        self.payment_id = data.get('id')
        self.steps.append({'step': 'reserve_payment', 'status': 'ok', 'payment_id': self.payment_id})

    def _step_reserve_shipping(self):
        address = self.shipping_address or {}
        if isinstance(address, str):
            address = {'full_address': address}
        resp = _post(f'{SHIP_SVC}/internal/shipments/', {
            'order_id': self.order.id,
            'receiver_name': address.get('receiver_name', ''),
            'phone': address.get('phone', ''),
            'full_address': address.get('full_address') or address.get('address', ''),
        })
        if resp.status_code not in (200, 201):
            raise SagaException('reserve_shipping', f'Shipping failed: {resp.text}')
        data = resp.json()
        self.shipment_id = data.get('id')
        self.steps.append({'step': 'reserve_shipping', 'status': 'ok', 'shipment_id': self.shipment_id})

    def _step_confirm_order(self):
        self.order.current_status = 'paid'
        self.order.save(update_fields=['current_status'])
        self.steps.append({'step': 'confirm_order', 'status': 'ok'})

    def _step_clear_cart(self):
        try:
            _delete(f'{CART_SVC}/internal/carts/{self.order.user_id}/clear/')
        except Exception:
            pass
        self.steps.append({'step': 'clear_cart', 'status': 'ok'})

    def _step_update_stock(self):
        """Decrement stock for each product ordered."""
        for item in self.items:
            product_id = _item_product_id(item)
            if not product_id:
                continue
            try:
                resp = _post(
                    f'{PRODUCT_SVC}/internal/products/{product_id}/reduce-stock/',
                    {'quantity': item['quantity']},
                )
                if resp.status_code >= 400:
                    raise SagaException('update_stock', f'Stock update failed: {resp.text}')
            except SagaException:
                raise
            except Exception as exc:
                raise SagaException('update_stock', f'Stock update failed: {exc}')
        self.steps.append({'step': 'update_stock', 'status': 'ok'})

    # ── compensation ──────────────────────────────────────────────────────────

    def _compensate(self, failed_step):
        logger.warning('Compensating saga from step: %s', failed_step)
        self.order.current_status = 'cancelled'
        self.order.save(update_fields=['current_status'])
        self.steps.append({'step': 'compensate_order', 'status': 'ok'})

        if failed_step in ('reserve_shipping', 'confirm_order', 'clear_cart', 'update_stock'):
            if self.payment_id:
                try:
                    _post(f'{PAY_SVC}/internal/payments/{self.order.id}/refund/', {'reason': 'Saga compensation'})
                    self.steps.append({'step': 'compensate_payment', 'status': 'ok'})
                except Exception as e:
                    self.steps.append({'step': 'compensate_payment', 'status': 'failed', 'error': str(e)})

        if failed_step in ('confirm_order', 'clear_cart', 'update_stock'):
            if self.shipment_id:
                try:
                    _post(f'{SHIP_SVC}/internal/shipments/{self.order.id}/cancel/', {'location': 'Saga compensation'})
                    self.steps.append({'step': 'compensate_shipping', 'status': 'ok'})
                except Exception as e:
                    self.steps.append({'step': 'compensate_shipping', 'status': 'failed', 'error': str(e)})


class SagaException(Exception):
    def __init__(self, step, reason):
        self.step = step
        self.reason = reason
        super().__init__(f'[{step}] {reason}')
