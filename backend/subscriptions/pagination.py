"""
Pagination for the list endpoints.

Bounds the row count any single request can pull. Note that the dashboard's
headline figures do NOT come from these list endpoints -- they are computed
server-side by ProjectionsView over the user's full active set -- so putting
a page boundary on /subscriptions/ cannot silently change a total.
"""

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 500
