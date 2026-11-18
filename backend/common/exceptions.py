from rest_framework.exceptions import APIException


class IneligibleDonorError(APIException):
    """Raised when a donor fails the server-side 90-day screening rule."""

    status_code = 400
    default_detail = "This donor is not eligible to donate yet."
    default_code = "ineligible_donor"
