"""Cost estimation from configurable per-million-token prices. Prices default to zero.

Nothing here knows any provider's real prices. The operator sets them from the
provider's official pricing page (see docs/operations/llm-provider-gemini.md).
"""

from decimal import ROUND_HALF_UP, Decimal

_MILLION = Decimal(1_000_000)
_PLACES = Decimal("0.000001")


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    input_price_per_million: float,
    output_price_per_million: float,
) -> Decimal:
    cost = (
        Decimal(input_tokens) * Decimal(str(input_price_per_million))
        + Decimal(output_tokens) * Decimal(str(output_price_per_million))
    ) / _MILLION
    return cost.quantize(_PLACES, rounding=ROUND_HALF_UP)
