from __future__ import annotations

import re
import unicodedata

_CHANNEL_TOKENS = {
    "upi", "paytmqr", "paytm", "phonepe", "gpay", "googlepay", "imps", "neft",
    "rtgs", "pos", "ref", "txn", "transaction", "payment", "paid", "debited",
    "credited", "purchase", "transfer", "to", "for", "via", "on", "at",
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def normalize_merchant(value: str | None) -> str | None:
    if not value:
        return None
    text = unicodedata.normalize("NFKC", value).casefold()
    text = text.replace("/", " ").replace("*", " ")
    text = re.sub(r"\b(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d{1,2})?\b", " ", text)
    text = re.sub(r"\b\d{5,}\b", " ", text)
    tokens = re.findall(r"[\w]+", text, flags=re.UNICODE)
    kept = [token for token in tokens if token not in _CHANNEL_TOKENS and not token.isdigit()]
    result = " ".join(kept).strip()
    return result[:180] or None
