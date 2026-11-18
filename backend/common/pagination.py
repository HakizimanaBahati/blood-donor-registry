from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Consistent count/next/previous/results envelope for every list endpoint."""

    page_query_param = "page"
    page_size_query_param = "page_size"
    page_size = 10
    max_page_size = 100
