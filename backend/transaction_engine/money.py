from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def rupees_to_paise(value: Decimal | str | int) -> int:
    """Convert rupees to the canonical integer-paise representation."""
    try:
        amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("amount must be a valid decimal rupee value") from exc
    if not amount.is_finite():
        raise ValueError("amount must be finite")
    return int(amount * 100)


def paise_to_rupees(amount_paise: int) -> Decimal:
    return (Decimal(amount_paise) / Decimal(100)).quantize(Decimal("0.01"))
