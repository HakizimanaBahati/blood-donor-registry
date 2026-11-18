"""Reusable 90-day donor eligibility service.

This is the single source of truth for registry eligibility. The API, the request
validation and the serializers all call these functions; no other layer recalculates it.
The rule is a project screening requirement, not a clinical eligibility assessment.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional

from django.utils import timezone

from common.exceptions import IneligibleDonorError

MIN_DAYS_BETWEEN_DONATIONS = 90


@dataclass(frozen=True)
class EligibilityInfo:
    eligible: bool
    has_donation_history: bool
    days_since_last_donation: Optional[int]
    days_until_eligible: int
    eligibility_message: str
    eligibility_badge: str


def _plural(count: int) -> str:
    return "day" if count == 1 else "days"


def calculate_eligibility(
    last_donation: Optional[date], today: Optional[date] = None
) -> EligibilityInfo:
    """Calculate registry eligibility using the server's current date."""
    today = today or timezone.localdate()

    if last_donation is None:
        return EligibilityInfo(
            eligible=True,
            has_donation_history=False,
            days_since_last_donation=None,
            days_until_eligible=0,
            eligibility_message=(
                "No donation history recorded. Eligible for preliminary registry "
                "screening; clinical screening still required."
            ),
            eligibility_badge="no_history",
        )

    days_since = (today - last_donation).days
    if days_since >= MIN_DAYS_BETWEEN_DONATIONS:
        return EligibilityInfo(
            eligible=True,
            has_donation_history=True,
            days_since_last_donation=days_since,
            days_until_eligible=0,
            eligibility_message=(
                "Eligible under the 90-day registry rule. Clinical screening still required."
            ),
            eligibility_badge="eligible",
        )

    remaining = max(0, MIN_DAYS_BETWEEN_DONATIONS - days_since)
    return EligibilityInfo(
        eligible=False,
        has_donation_history=True,
        days_since_last_donation=days_since,
        days_until_eligible=remaining,
        eligibility_message=(
            f"This donor is not eligible yet. Please wait {remaining} "
            f"more {_plural(remaining)}."
        ),
        eligibility_badge="ineligible",
    )


def ensure_donor_selectable(donor, today: Optional[date] = None) -> EligibilityInfo:
    """Raise a 400 IneligibleDonorError when an ineligible donor is selected."""
    info = calculate_eligibility(donor.last_donation, today=today)
    if not info.eligible:
        raise IneligibleDonorError(
            {
                "message": (
                    "This donor is not eligible to donate yet. Please wait "
                    f"{info.days_until_eligible} more "
                    f"{_plural(info.days_until_eligible)}."
                ),
                "days_until_eligible": info.days_until_eligible,
                "eligibility_badge": info.eligibility_badge,
                "donor_id": str(donor.pk),
            }
        )
    return info
