from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Paginación estándar. Permite que el cliente controle el tamaño
    via ?page_size=N hasta un máximo de 500.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 500
