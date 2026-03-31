"""Descarga de archivos sensibles del pedido (solo staff, sesión Django admin)."""
import mimetypes

from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import Order


@staff_member_required
def staff_order_payment_proof(request, order_id):
    """
    Sirve el comprobante Neki para previsualizar en Django Admin.
    Requiere cookie de sesión de staff (no JWT).
    """
    order = get_object_or_404(Order, pk=order_id)
    if not order.payment_proof or not order.payment_proof.name:
        raise Http404('Sin comprobante')
    try:
        fp = order.payment_proof.open('rb')
    except FileNotFoundError as e:
        raise Http404('Archivo no encontrado') from e
    mime, _ = mimetypes.guess_type(order.payment_proof.name)
    resp = FileResponse(fp, content_type=mime or 'application/octet-stream')
    resp['Cache-Control'] = 'private, no-store'
    return resp
