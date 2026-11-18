"""Uniform JSON error envelopes. Never leak stack traces or database details."""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.exceptions import IneligibleDonorError

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "details": None,
                }
            },
            status=500,
        )

    status = response.status_code
    if isinstance(exc, IneligibleDonorError):
        code = "ineligible_donor"
        message = "This donor is not eligible to donate yet."
        details = exc.detail
    elif isinstance(exc, (ValidationError,)):
        code = "validation_error"
        message = "The request contains invalid data."
        details = response.data
    elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        code = "authentication_failed"
        message = "Authentication is required or the supplied token is invalid."
        details = None
    elif isinstance(exc, (PermissionDenied, DjangoPermissionDenied)):
        code = "permission_denied"
        message = "You do not have permission to perform this action."
        details = None
    elif isinstance(exc, Http404):
        code = "not_found"
        message = "The requested resource does not exist."
        details = None
    elif status == 404:
        code = "not_found"
        message = "The requested resource does not exist."
        details = None
    elif status == 401:
        code = "authentication_failed"
        message = "Authentication is required or the supplied token is invalid."
        details = None
    elif status == 403:
        code = "permission_denied"
        message = "You do not have permission to perform this action."
        details = None
    elif status == 400:
        code = "bad_request"
        message = "The request could not be processed."
        details = response.data
    elif isinstance(exc, APIException):
        code = "api_error"
        message = str(exc.detail)
        details = None
    else:
        code = "error"
        message = "The request could not be processed."
        details = None

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
    return response
