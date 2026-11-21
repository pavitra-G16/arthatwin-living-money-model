from __future__ import annotations

import hashlib
import json

from transaction_engine.merchant import normalize_text


def duplicate_fingerprint(transaction_date, transaction_type: str, amount, description: str) -> str:
    """Fingerprint an import row without collapsing transactions that only share an amount."""
    canonical = {
        "date": transaction_date.isoformat(),
        "type": transaction_type,
        "amount": format(amount, ".2f"),
        "narration": normalize_text(description),
    }
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
