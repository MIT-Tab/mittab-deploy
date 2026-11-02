"""Server-side, integer-cent quotes. Existing rows retain legacy pricing."""

from dataclasses import dataclass
from datetime import date, datetime

LEGACY = "legacy-v1"
SHARED = "shared-full-web-v2"
FIXED_CENTS = 1500
DAILY_CENTS = 100
REGISTRATION_DAILY_CENTS = 75
MAX_REGISTRATION_DAYS = 21


def today():
    # Preserve the existing production UTC calendar-day convention.
    return datetime.utcnow().date()


@dataclass(frozen=True)
class Quote:
    version: str
    fixed_cents: int
    registration_days: int
    normal_days: int
    test_days: int

    @property
    def total_cents(self):
        return (
            self.fixed_cents
            + self.registration_days * REGISTRATION_DAILY_CENTS
            + (self.normal_days + self.test_days) * DAILY_CENTS
        )

    def as_dict(self):
        return {
            "version": self.version,
            "fixed_cents": self.fixed_cents,
            "registration_days": self.registration_days,
            "registration_daily_cents": REGISTRATION_DAILY_CENTS,
            "normal_days": self.normal_days,
            "normal_daily_cents": DAILY_CENTS,
            "test_days": self.test_days,
            "total_cents": self.total_cents,
        }


def quote(
    deletion_date, start_date=None, add_test=False, *, shared=False, on_date=None
):
    on_date = on_date or today()
    if not isinstance(deletion_date, date) or deletion_date <= on_date:
        raise ValueError("Deletion date must be in the future")
    if start_date is not None and not shared:
        raise ValueError("Advance registration is not enabled")
    if start_date is not None and not on_date <= start_date <= deletion_date:
        raise ValueError("Tournament start date must be between today and deletion")
    registration_days = (start_date - on_date).days if start_date else 0
    if registration_days > MAX_REGISTRATION_DAYS:
        raise ValueError("Registration can start at most 21 days before the tournament")
    normal_days = (deletion_date - (start_date or on_date)).days + 1
    return Quote(
        SHARED if shared else LEGACY,
        FIXED_CENTS,
        registration_days,
        normal_days,
        normal_days if add_test else 0,
    )
