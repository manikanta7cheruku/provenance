"""The payment provider interface. It exists so billing can be added without touching a feature, and it
stays switched off.

No provider has been chosen and no provider's terms have been read, so nothing here can collect money
or a card number. `DisabledPayments` is the only implementation. When a provider is chosen (carryover
C-132), its terms are read and recorded in docs/providers, an implementation of `PaymentProvider` is
written beside this one, and the plan service is given it. The features never see any of that: they
only ask whether a person may do something (pv_domain.entitlements).
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CheckoutResult:
    """Where to send the person to pay, or why they cannot."""

    available: bool
    url: str | None
    message: str


class PaymentProvider(Protocol):
    name: str
    enabled: bool

    def start_checkout(self, *, user_id: str, plan_id: str) -> CheckoutResult: ...

    def cancel(self, *, user_id: str) -> CheckoutResult: ...


class DisabledPayments:
    """Payments are off. Every call says so and does nothing."""

    name = "none"
    enabled = False
    _MESSAGE = "Paid plans are not available yet. Nothing is charged."

    def start_checkout(self, *, user_id: str, plan_id: str) -> CheckoutResult:
        return CheckoutResult(False, None, self._MESSAGE)

    def cancel(self, *, user_id: str) -> CheckoutResult:
        return CheckoutResult(False, None, self._MESSAGE)
