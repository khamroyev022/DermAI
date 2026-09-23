"""
Central DRF exception handling.

Unexpected errors are logged with their traceback server-side, but the API
response only ever contains a generic message — never a stack trace.
"""

import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "A required service is temporarily unavailable. Please try again."
    default_code = "service_unavailable"


class UpstreamLLMError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "The language model could not produce an answer. Please try again."
    default_code = "llm_error"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response

    view = context.get("view")
    logger.exception("Unhandled error in %s", view.__class__.__name__ if view else "unknown view")
    return Response(
        {"detail": "Internal server error."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
