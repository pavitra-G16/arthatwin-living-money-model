from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from transaction_engine.merchant import normalize_merchant
from models import LearnedCategoryRule

CATEGORIES = (
    "Food & Dining", "Groceries", "Transport", "Shopping", "Bills & Utilities",
    "Subscriptions", "Healthcare", "Education", "Rent", "Salary / Income",
    "Transfers", "Cash Withdrawal", "Other", "Review Required",
)

# Each entry is a conservative, explainable keyword rule. First match wins.
_RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
    ("Salary / Income", ("salary", "payroll", "wages", "salary credited"), 0.96),
    ("Rent", ("rent", "landlord", "house lease"), 0.94),
    ("Subscriptions", ("netflix", "spotify", "hotstar", "prime video", "subscription", "streamflix", "newsplus"), 0.94),
    ("Bills & Utilities", ("electricity", "bescom", "water bill", "gas bill", "utility", "broadband", "mobile bill", "recharge"), 0.91),
    ("Groceries", ("grocery", "groceries", "supermarket", "bigbasket", "blinkit", "zepto", "dmart", "freshmart", "reliance fresh"), 0.91),
    ("Food & Dining", ("restaurant", "cafe", "café", "food delivery", "swiggy", "zomato", "foodbox", "dining", "bakery"), 0.90),
    ("Transport", ("metro", "uber", "ola", "cabs", "cab", "fuel", "petrol", "rapido", "irctc"), 0.90),
    ("Healthcare", ("pharmacy", "hospital", "clinic", "medical", "healthcare", "diagnostic"), 0.91),
    ("Education", ("school", "college", "tuition", "course fee", "education", "udemy"), 0.90),
    ("Cash Withdrawal", ("atm withdrawal", "cash withdrawal", "withdrawal at atm"), 0.96),
    ("Transfers", ("neft", "imps", "rtgs", "bank transfer", "fund transfer", "upi transfer"), 0.82),
    ("Shopping", ("shopping", "amazon", "flipkart", "myntra", "retail", "marketplace"), 0.86),
)


@dataclass(frozen=True)
class CategoryPrediction:
    category: str
    confidence_score: float
    reason: str


def categorize(description: str, merchant: str | None, db: Session | None = None) -> CategoryPrediction:
    merchant_key = normalize_merchant(merchant)
    if db is not None and merchant_key:
        learned = db.scalar(select(LearnedCategoryRule).where(LearnedCategoryRule.merchant_key == merchant_key))
        if learned:
            return CategoryPrediction(learned.category, 1.0, f"Your saved merchant rule for '{merchant_key}'.")

    text = f"{description} {merchant or ''}".casefold()
    for category, keywords, confidence in _RULES:
        for keyword in keywords:
            if keyword in text:
                return CategoryPrediction(category, confidence, f"Matched keyword '{keyword}'.")

    return CategoryPrediction(
        "Review Required", 0.25,
        "No reliable categorization rule matched; review this transaction.",
    )
