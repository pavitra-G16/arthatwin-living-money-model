from __future__ import annotations

import re


def clean_description(raw_narration: str) -> str:
    value = " ".join(raw_narration.strip().split())
    value = re.sub(r"^(?:UPI|IMPS|NEFT|RTGS)[/:\s-]+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:RRN|UTR|REF(?:ERENCE)?|TXN(?:\s*ID)?)\s*[:#-]?\s*[A-Z0-9-]{5,}\b", "", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip(" /|-") or raw_narration.strip()
