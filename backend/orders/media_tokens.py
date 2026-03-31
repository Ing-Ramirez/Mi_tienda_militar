"""Token firmado temporal para comprobante de pago (dueño del pedido)."""
from urllib.parse import urlencode

from django.core import signing
from django.urls import reverse

_PAYMENT_PROOF_SALT = 'franja-pixelada.order-payment-proof.v1'
_MAX_AGE_SECONDS = 3600


def build_payment_proof_token(order_id, user_id, relative_name: str) -> str:
    if not relative_name:
        raise ValueError('relative_name required')
    return signing.dumps(
        {'o': str(order_id), 'u': str(user_id), 'f': relative_name},
        salt=_PAYMENT_PROOF_SALT,
    )


def parse_payment_proof_token(token: str) -> dict:
    return signing.loads(token, max_age=_MAX_AGE_SECONDS, salt=_PAYMENT_PROOF_SALT)


def signed_payment_proof_absolute_url(request, order):
    if (
        not request
        or not order.payment_proof
        or not order.payment_proof.name
        or not order.user_id
    ):
        return None
    token = build_payment_proof_token(order.pk, order.user_id, order.payment_proof.name)
    path = reverse('order_payment_proof_media', kwargs={'pk': order.pk})
    return request.build_absolute_uri(f'{path}?{urlencode({"t": token})}')
