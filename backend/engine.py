from __future__ import annotations

import re
import os
from collections import defaultdict
from decimal import Decimal
from datetime import date

from sqlalchemy.orm import Session

from database import FinancialGoal, FinancialProfile, LearnedRule, MonthCoverage, SubscriptionFeedback, Transaction
from finance import (
    FIXED_CATEGORIES,
    TRANSFER_CATEGORIES,
    amount_sum,
    category_totals,
    compare_category_spending,
    decimal_money,
    filter_month,
    month_for_transactions,
    monthly_summary,
    prior_month,
    project_goals,
    refund_total,
    ZERO,
)
from importers import clean_untrusted, parse_csv_bytes, parse_pdf_bytes, parse_sms_dump, quarantined

DEFAULT_MERCHANT_MAP = {
    # Specific merchant phrases must win over broad brand and UPI transfer
    # heuristics (many Indian UPI narrations have a DR/CR path segment).
    "SWIGGY INSTAMART": ("Groceries", 0.99), "INSTAMART": ("Groceries", 0.98),
    "STARBUCKS COFFEE": ("Dining Out", 0.98), "ZOMATO ORDER": ("Dining Out", 0.98),
    "NOBROKER RENT": ("Housing", 0.99), "AIRTEL FIBER": ("Utilities", 0.99),
    "RAHUL SHARMA": ("Transfers / People", 0.99),
    "ZOMATO": ("Dining Out", 0.98), "SWIGGY": ("Dining Out", 0.98), "STARBUCKS": ("Dining Out", 0.96),
    "CHAI POINT": ("Dining Out", 0.94), "CAFE": ("Dining Out", 0.78), "FOOD": ("Dining Out", 0.74),
    "BLINKIT": ("Groceries", 0.98), "ZEPTO": ("Groceries", 0.96), "BIGBASKET": ("Groceries", 0.98), "DMART": ("Groceries", 0.95),
    "UBER": ("Transport", 0.97), "OLA": ("Transport", 0.97), "IRCTC": ("Travel", 0.97), "INDIGO": ("Travel", 0.97),
    "NETFLIX": ("Subscriptions", 0.99), "SPOTIFY": ("Subscriptions", 0.98), "PRIME VIDEO": ("Subscriptions", 0.98),
    "AMAZON PRIME": ("Subscriptions", 0.98), "CULTFIT": ("Subscriptions", 0.97), "YOUTUBE PREMIUM": ("Subscriptions", 0.98),
    "AIRTEL": ("Utilities", 0.98), "JIO": ("Utilities", 0.97), "BESCOM": ("Utilities", 0.98),
    "RENT": ("Housing", 0.97), "NOBROKER": ("Housing", 0.97), "APOLLO": ("Health", 0.94), "PHARMEASY": ("Health", 0.97),
    "AMAZON": ("Shopping", 0.88), "FLIPKART": ("Shopping", 0.97), "MYNTRA": ("Shopping", 0.97),
    "SALARY": ("Income", 0.98), "PAYROLL": ("Income", 0.95),
}
CATEGORIES = {
    "Dining Out", "Groceries", "Transport", "Travel", "Subscriptions", "Utilities", "Housing", "Health",
    "Shopping", "Education", "Cash Withdrawal", "Transfers", "Transfers / People", "Income", "Refund",
    "Uncategorised", "Review Required",
}
INJECTION_PATTERNS = ("ignore all rules", "ignore previous", "system prompt", "mark this as", "you are now", "override instructions")
BLOCKED_INVESTMENT_PATTERNS = (
    r"\b(?:stock|stocks|share|shares|equity)\b", r"\bmutual\s+fund\b", r"\bcrypto(?:currency)?\b",
    r"\bbitcoin\b", r"\bethereum\b", r"\b(?:nifty|sensex|etf|ipo)\b", r"\bguaranteed\s+returns?\b",
    r"\bwhich\s+(?:fund|security|coin)\b", r"\bwhere\s+to\s+invest\b",
)


def detect_prompt_injection(raw_text: str) -> str | None:
    return quarantined(raw_text)


def quarantine_untrusted_text(raw_text: str) -> str:
    return clean_untrusted(raw_text)


def extract_merchant_token(raw_text: str) -> str:
    from importers import merchant_from_text
    return merchant_from_text(clean_untrusted(raw_text))


def _transfer_or_refund(raw: str) -> str | None:
    upper = raw.upper()
    if re.search(r"\b(ATM|CASH WITHDRAWAL|CASH WDL)\b", upper):
        return "Cash Withdrawal"
    if re.search(r"\b(REFUND|REVERSAL|CHARGEBACK)\b", upper):
        return "Refund"
    if re.search(r"\b(TRANSFER|IMPS|NEFT|RTGS|SELF\s+TRANSFER)\b", upper) or "P2P" in upper:
        return "Transfers / People" if re.search(r"\b(TO|FROM)\s+[A-Z]+\s+[A-Z]+\b", upper) or "P2P" in upper else "Transfers"
    if re.search(r"UPI/\d+/(?:DR|CR)/[A-Z]+\s+[A-Z]+/", upper):
        return "Transfers / People"
    return None


def categorize_with_evidence(db: Session, merchant: str, raw_narration: str, amount: Decimal | float, txn_type: str = "DEBIT") -> tuple[str, str, float]:
    safe_raw = quarantine_untrusted_text(raw_narration)
    searchable = f"{merchant} {safe_raw}".upper()
    if txn_type == "CREDIT":
        if re.search(r"\b(REFUND|REVERSAL|CHARGEBACK)\b", searchable):
            return "Refund", "REFUND_RULE", 0.98
        if re.search(r"\b(SALARY|PAYROLL|WAGES)\b", searchable):
            return "Income", "INCOME_RULE", 0.98
        transfer = _transfer_or_refund(searchable)
        return (transfer, "TRANSFER_RULE", 0.95) if transfer else ("Income", "CREDIT_DIRECTION", 0.72)
    learned_query = db.query(LearnedRule).filter(LearnedRule.is_enabled.is_(True))
    if os.getenv("ARTHATWIN_PUBLIC_DEMO", "0") == "1":
        learned_query = learned_query.filter(LearnedRule.is_demo.is_(True))
    learned = learned_query.order_by(LearnedRule.id.desc()).all()
    exact_merchant = " ".join(merchant.upper().split())
    for rule in learned:
        if exact_merchant == " ".join(rule.pattern.upper().split()):
            return rule.category, "LEARNED_RULE", 1.0
    merchant_key = " ".join(merchant.upper().split())
    # Match merchant-specific defaults before interpreting the surrounding UPI
    # narration. For example, UPI/.../DR/SWIGGY INSTAMART/... is a purchase,
    # while UPI/.../DR/RAHUL SHARMA/... is a person-to-person transfer.
    for token in sorted(DEFAULT_MERCHANT_MAP, key=len, reverse=True):
        if token in merchant_key:
            category, confidence = DEFAULT_MERCHANT_MAP[token]
            return category, "MERCHANT_RULE", confidence
    special = _transfer_or_refund(searchable)
    if special:
        return special, "TRANSFER_RULE", 0.96
    for token in sorted(DEFAULT_MERCHANT_MAP, key=len, reverse=True):
        if token in searchable:
            category, confidence = DEFAULT_MERCHANT_MAP[token]
            return category, "MERCHANT_RULE", confidence
    if re.search(r"\b(SALARY|PAYROLL|WAGES)\b", searchable):
        return "Income", "INCOME_RULE", 0.95
    return "Review Required", "NEEDS_REVIEW", 0.0


def categorize_with_memory(db: Session, merchant: str, raw_narration: str, amount: float) -> tuple[str, str]:
    category, source, _ = categorize_with_evidence(db, merchant, raw_narration, amount)
    return category, source


def _cadence(days: int) -> str | None:
    for name, low, high in (("weekly", 5, 10), ("monthly", 25, 35), ("quarterly", 80, 100), ("annual", 350, 380)):
        if low <= days <= high:
            return name
    return None


def _monthly_equivalent(amount: Decimal, cadence: str) -> Decimal:
    if cadence == "weekly":
        return decimal_money(amount * Decimal(52) / Decimal(12))
    if cadence == "quarterly":
        return decimal_money(amount / Decimal(3))
    if cadence == "annual":
        return decimal_money(amount / Decimal(12))
    return amount


def detect_recurring_and_creep(db: Session):
    txn_query = db.query(Transaction).filter(Transaction.txn_type == "DEBIT", Transaction.category.notin_(TRANSFER_CATEGORIES))
    feedback_query = db.query(SubscriptionFeedback)
    if os.getenv("ARTHATWIN_PUBLIC_DEMO", "0") == "1":
        txn_query = txn_query.filter(Transaction.is_demo.is_(True))
        feedback_query = feedback_query.filter(SubscriptionFeedback.is_demo.is_(True))
    txns = txn_query.all()
    feedback = {row.merchant.upper(): row.still_uses for row in feedback_query.all()}
    grouped: dict[str, list[tuple[date, Transaction]]] = defaultdict(list)
    for txn in txns:
        try:
            day = date.fromisoformat(txn.date)
        except (TypeError, ValueError):
            continue
        grouped[txn.merchant.upper()].append((day, txn))
    alerts = []
    for merchant, items in grouped.items():
        items.sort(key=lambda pair: pair[0])
        if len(items) < 2:
            continue
        intervals = [(items[index][0] - items[index - 1][0]).days for index in range(1, len(items))]
        cadence = _cadence(sorted(intervals)[len(intervals) // 2])
        if not cadence or sum(1 for interval in intervals if _cadence(interval) == cadence) < 1:
            continue
        latest_day, latest = items[-1]
        prev_day, previous = items[-2]
        if _cadence((latest_day - prev_day).days) != cadence:
            continue
        cadence_matches = sum(1 for interval in intervals if _cadence(interval) == cadence)
        consistency = cadence_matches / len(intervals)
        confidence = "low" if len(items) < 3 else "medium" if len(items) < 5 or consistency < 0.8 else "high"
        latest_amount = decimal_money(latest.amount)
        previous_amount = decimal_money(previous.amount)
        pct = ((latest_amount - previous_amount) / previous_amount * Decimal(100)) if previous_amount else ZERO
        usage = feedback.get(merchant, "unsure")
        if pct >= Decimal("5"):
            alert_type = "PRICE_HIKE"
            reason = f"Observed amount increased +{pct.quantize(Decimal('1'))}% between {prev_day.isoformat()} and {latest_day.isoformat()}. Confirm whether this is a recurring price change."
        elif abs(pct) >= Decimal("25"):
            alert_type = "AMOUNT_VARIATION"
            reason = f"Observed recurring amount changed {pct.quantize(Decimal('1'))}% between {prev_day.isoformat()} and {latest_day.isoformat()}; check whether this is a one-off variation."
        elif usage == "no":
            alert_type = "USER_MARKED_NOT_USING"
            reason = "You marked this payment as not currently used. The app cannot observe service usage."
        else:
            alert_type = "RECURRING_CANDIDATE"
            reason = f"Two or more payments have a {cadence} cadence in the imported ledger; confirm whether this payment is recurring."
        monthly_amount = _monthly_equivalent(latest_amount, cadence)
        alerts.append({
            "merchant": merchant,
            "type": alert_type,
            "cadence": cadence,
            "confidence": confidence,
            "observation_count": len(items),
            "cadence_consistency": round(consistency, 2),
            "reason": reason,
            "last_amount": latest_amount,
            "monthly_amount": monthly_amount,
            "annual_cost": (monthly_amount * Decimal(12)).quantize(Decimal("0.01")),
            "last_payment_date": latest_day.isoformat(),
            "observation_count": len(items),
            "still_uses": usage,
        })
    return sorted(alerts, key=lambda row: (row["type"] not in {"PRICE_HIKE", "AMOUNT_VARIATION"}, row["merchant"]))


def run_what_if_simulation(
    db: Session,
    dining_cut_pct: float = 0.0,
    rent_change: float = 0.0,
    cancel_unused_subs: bool = False,
    extra_income: float = 0.0,
    month: str | None = None,
    as_of: date | None = None,
) -> dict:
    public_demo = os.getenv("ARTHATWIN_PUBLIC_DEMO", "0") == "1"
    profile_query = db.query(FinancialProfile)
    goal_query = db.query(FinancialGoal)
    transaction_query = db.query(Transaction)
    if public_demo:
        profile_query = profile_query.filter(FinancialProfile.is_demo.is_(True))
        goal_query = goal_query.filter(FinancialGoal.is_demo.is_(True))
        transaction_query = transaction_query.filter(Transaction.is_demo.is_(True))
    profile = profile_query.first() or FinancialProfile()
    goals = goal_query.all()
    all_txns = transaction_query.all()
    period = month_for_transactions(all_txns, month, as_of)
    rows = filter_month(all_txns, period)
    expense_rows = [row for row in rows if row.txn_type == "DEBIT" and row.category not in TRANSFER_CATEGORIES]
    variable = [row for row in expense_rows if row.category not in FIXED_CATEGORIES]
    dining = amount_sum(row for row in variable if row.category == "Dining Out")
    other_variable = amount_sum(row for row in variable if row.category != "Dining Out")
    fixed_observed = amount_sum(row for row in expense_rows if row.category in FIXED_CATEGORIES)
    fixed_base = max(decimal_money(profile.fixed_costs), fixed_observed)
    income = decimal_money(profile.monthly_income)
    period_refunds = refund_total(rows)
    base_surplus = income - fixed_base - dining - other_variable + period_refunds
    cut = max(Decimal(0), min(Decimal(100), decimal_money(dining_cut_pct)))
    rent_delta = max(Decimal(0), decimal_money(rent_change))
    added_income = decimal_money(extra_income)
    subscription_savings = ZERO
    if cancel_unused_subs:
        for alert in detect_recurring_and_creep(db):
            if alert["still_uses"] == "no":
                subscription_savings += alert["monthly_amount"]
    dining_savings = decimal_money(dining * cut / Decimal(100))
    scenario_surplus = base_surplus + dining_savings - rent_delta + subscription_savings + added_income
    goals_result = project_goals(goals, base_surplus, scenario_surplus, as_of)
    return {
        "month": period,
        "base_monthly_surplus": base_surplus,
        "simulated_monthly_surplus": scenario_surplus,
        "monthly_delta": scenario_surplus - base_surplus,
        "dining_savings": dining_savings,
        "rent_change": rent_delta,
        "subscription_savings": subscription_savings,
        "income_change": added_income,
        "assumptions": "Scenario estimate uses selected-month imported variable debits, identified refunds, profile monthly income/fixed costs, confirmed 'no' subscription feedback converted to monthly equivalent, and constant surplus. Statement completeness is unknown; transfers and cash withdrawals are excluded.",
        "goal_impacts": goals_result,
    }


def _report(profile: FinancialProfile, transactions: list[Transaction], month: str, goals: list[FinancialGoal], alerts: list[dict], nudges: list[dict]) -> dict:
    summary = monthly_summary(profile, transactions, month)
    return {
        "month": month,
        "income": summary["observed_income"],
        "profile_income_assumption": summary["profile_monthly_income"],
        "expenses": summary["observed_expenses"],
        "refunds": summary["observed_refunds"],
        "modeled_surplus": summary["modeled_surplus"],
        "category_breakdown": summary["category_breakdown"],
        "recurring_payments": alerts,
        "spending_changes": nudges,
        "goals": [{"name": goal.name, "target_amount": goal.target_amount, "saved_amount": goal.saved_amount, "target_date": goal.target_date} for goal in goals],
        "data_quality": summary["data_quality"],
        "disclaimer": "Educational cashflow summary from the selected period and stated assumptions. It is not financial advice.",
    }


def _external_coach_tool_result(db: Session, name: str, month: str, user_message: str, as_of: date | None = None) -> dict:
    """Execute one allowlisted, read-only local tool; never include raw narration."""
    public_demo = os.getenv("ARTHATWIN_PUBLIC_DEMO", "0") == "1"
    tx_query, profile_query, goal_query = db.query(Transaction), db.query(FinancialProfile), db.query(FinancialGoal)
    if public_demo:
        tx_query = tx_query.filter(Transaction.is_demo.is_(True))
        profile_query = profile_query.filter(FinancialProfile.is_demo.is_(True))
        goal_query = goal_query.filter(FinancialGoal.is_demo.is_(True))
    transactions = tx_query.all()
    profile = profile_query.first() or FinancialProfile()
    goals = goal_query.all()
    period_rows = filter_month(transactions, month)
    previous_rows = filter_month(transactions, prior_month(month))
    coverage_query = db.query(MonthCoverage)
    if public_demo:
        coverage_query = coverage_query.filter(MonthCoverage.is_demo.is_(True))
    complete = {row.month for row in coverage_query.filter(MonthCoverage.confirmed_complete.is_(True)).all()}

    def spending_nudges() -> dict:
        prior = prior_month(month)
        missing = [period for period in (month, prior) if period not in complete]
        if missing:
            return {"month": month, "nudges": [], "warnings": [f"No spending comparison shown; {', '.join(missing)} is not user-confirmed complete."]}
        return {"month": month, "nudges": compare_category_spending(period_rows, previous_rows, month), "warnings": []}

    if name == "get_financial_profile":
        return {"monthly_income": decimal_money(profile.monthly_income), "fixed_costs": decimal_money(profile.fixed_costs), "emergency_fund_current": decimal_money(profile.emergency_fund_current), "emergency_fund_target": decimal_money(profile.emergency_fund_target), "goals": [{"name": g.name, "target": g.target_amount, "saved": g.saved_amount, "target_date": g.target_date} for g in goals]}
    if name == "get_monthly_summary":
        return monthly_summary(profile, transactions, month)
    if name == "analyze_category_spending":
        return spending_nudges()
    if name == "detect_recurring_payments":
        return detect_recurring_and_creep(db)
    if name == "simulate_goal_change":
        lowered = user_message.lower()
        percent = re.search(r"(\d{1,3})\s*%", lowered)
        rent = re.search(r"rent.{0,30}?(?:by|increase|up)\s*(?:₹|rs\.?\s*)?([\d,]+)", lowered)
        income = re.search(r"income.{0,30}?(?:by|increase|up|decrease|down|drop|fall)\s*(?:₹|rs\.?\s*)?([\d,]+)", lowered)
        income_delta = float(income.group(1).replace(",", "")) if income else 0
        if income and re.search(r"(?:decrease|down|drop|fall)", lowered[income.start():income.end()]):
            income_delta *= -1
        return run_what_if_simulation(db, float(percent.group(1)) if percent else (30 if "dining" in lowered else 0), float(rent.group(1).replace(",", "")) if rent else 0, "cancel" in lowered, income_delta, month, as_of)
    if name == "get_spending_nudges":
        return spending_nudges()
    if name == "generate_monthly_report":
        summary = monthly_summary(profile, transactions, month)
        alerts = detect_recurring_and_creep(db)
        return {"month": month, "observed_income": summary["observed_income"], "observed_expenses": summary["observed_expenses"], "observed_refunds": summary["observed_refunds"], "modeled_surplus": summary["modeled_surplus"], "category_breakdown": summary["category_breakdown"], "recurring_payments": alerts, "spending_changes": spending_nudges(), "goals": [{"name": g.name, "target": g.target_amount, "saved": g.saved_amount, "target_date": g.target_date} for g in goals], "data_quality": summary["data_quality"]}
    raise ValueError("Unknown read-only finance tool")


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items() if k not in {"transactions", "raw_expense_rows", "income_rows"}}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _optional_external_coach(db: Session, user_message: str, month: str, as_of: date | None = None) -> dict | None:
    """Model selects a bounded tool; local deterministic code executes and explains verified results."""
    if os.getenv("EXTERNAL_AI_ENABLED") != "1" or not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return None
    client = None
    try:
        from google import genai
        from google.genai import types

        declarations = [types.FunctionDeclaration(name=name, description=description, parameters_json_schema={"type": "object", "properties": {}, "additionalProperties": False}) for name, description in [
            ("get_financial_profile", "Read user-entered profile assumptions and goals."),
            ("get_monthly_summary", "Read verified aggregates for the selected month."),
            ("analyze_category_spending", "Compare category totals with the previous calendar month."),
            ("detect_recurring_payments", "Find dated repeat-payment candidates; usage must be user-confirmed."),
            ("simulate_goal_change", "Run a deterministic cashflow and goal what-if scenario."),
            ("get_spending_nudges", "Get category increases from the selected and previous month."),
            ("generate_monthly_report", "Generate selected-month financial aggregates and goal progress."),
        ]]
        tool = types.Tool(function_declarations=declarations)
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        selection = client.models.generate_content(model=model, contents=[
            f"Selected reporting month: {month}. Select exactly one read-only function for the user's question. Do not answer the question. The functions use no arguments. User question: " + user_message[:2000]
        ], config=types.GenerateContentConfig(tools=[tool], tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))))
        calls = selection.function_calls or []
        allowed = {item.name for item in declarations}
        if len(calls) != 1 or calls[0].name not in allowed or (calls[0].args or {}) != {}:
            return None
        name = calls[0].name
        verified = _json_safe(_external_coach_tool_result(db, name, month, user_message, as_of))
        answer = _explain_verified_tool_result(name, verified, month)
        return {"tool_selected": name, "reason": "The optional AI model selected this bounded read-only tool; ArthaTwin executed it locally and generated the explanation from verified values.", "verified_result": verified, "ai_enabled": True, "reply": answer}
    except Exception:
        return None
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _explain_verified_tool_result(name: str, result: dict, month: str) -> str:
    """Return financial prose with figures sourced only from the deterministic tool result."""
    if name == "get_financial_profile":
        return (f"Your saved profile lists monthly income of ₹{Decimal(result['monthly_income']):,.2f}, fixed costs of ₹{Decimal(result['fixed_costs']):,.2f}, "
                f"and emergency savings of ₹{Decimal(result['emergency_fund_current']):,.2f} against ₹{Decimal(result['emergency_fund_target']):,.2f}. "
                "These are user-entered assumptions, not bank-verified balances.")
    if name in {"get_monthly_summary", "generate_monthly_report"}:
        observed_expenses = Decimal(str(result.get("observed_expenses", "0")))
        observed_income = Decimal(str(result.get("observed_income", "0")))
        modeled = Decimal(str(result.get("modeled_surplus", "0")))
        return (f"For {month}, imported income is ₹{observed_income:,.2f}, net observed expenses are ₹{observed_expenses:,.2f}, "
                f"and profile-based modeled monthly surplus is ₹{modeled:,.2f}. Statement completeness is unknown; this is not a bank-verified forecast.")
    if name == "simulate_goal_change":
        base = Decimal(str(result["base_monthly_surplus"]))
        scenario = Decimal(str(result["simulated_monthly_surplus"]))
        return f"For {month}, the deterministic scenario changes modeled monthly surplus from ₹{base:,.2f} to ₹{scenario:,.2f}. Statement completeness is unknown."
    if name == "detect_recurring_payments":
        return f"I found {len(result)} recurring-payment candidate(s) from dated debit patterns. Confirm service usage yourself; a payment record does not prove whether you use a service."
    if name in {"analyze_category_spending", "get_spending_nudges"}:
        nudges = result.get("nudges", [])
        warnings = result.get("warnings", [])
        if warnings:
            return "I did not compare spending because both statements are not confirmed complete. " + " ".join(warnings)
        if not nudges:
            return f"No category passed the review threshold for {month}."
        first = nudges[0]
        return f"{first['category']} increased by ₹{Decimal(str(first['change'])):,.2f} ({first['change_percent']}%) in {month}; compare only if both statements cover the full months."
    return f"I ran a read-only ArthaTwin analysis for {month}. Review the verified result shown with this response."


def coach_response(db: Session, user_message: str, month: str | None = None, as_of: date | None = None, allow_external_ai: bool = False) -> dict:
    if any(re.search(pattern, user_message, re.I) for pattern in BLOCKED_INVESTMENT_PATTERNS):
        return {
            "guardrail_triggered": True,
            "reply": "ArthaTwin cannot recommend specific stocks, mutual funds, crypto assets, or other securities, and it cannot promise investment returns. I can help explain cashflow or model a savings scenario instead.",
            "agent_trace": {"tool_selected": None, "reason": "The request asks for a specific investment recommendation, which is outside the product's allowed scope.", "verified_result": None},
        }
    public_demo = os.getenv("ARTHATWIN_PUBLIC_DEMO", "0") == "1"
    transaction_query = db.query(Transaction)
    profile_query = db.query(FinancialProfile)
    goal_query = db.query(FinancialGoal)
    if public_demo:
        transaction_query = transaction_query.filter(Transaction.is_demo.is_(True))
        profile_query = profile_query.filter(FinancialProfile.is_demo.is_(True))
        goal_query = goal_query.filter(FinancialGoal.is_demo.is_(True))
    transactions = transaction_query.all()
    profile = profile_query.first() or FinancialProfile()
    goals = goal_query.all()
    selected_month = month_for_transactions(transactions, month, as_of)
    lowered = user_message.lower()
    scenario_requested = bool(re.search(r"\b(goal|rent|dining|what if|what-if|simulate|save faster)\b", lowered))
    income_change_requested = "income" in lowered and bool(re.search(r"\b(increase|up|decrease|down|drop|fall)\b", lowered))
    if scenario_requested or income_change_requested:
        match = re.search(r"(\d{1,3})\s*%", lowered)
        rent_match = re.search(r"rent.{0,30}?(?:by|increase|up)\s*(?:₹|rs\.?\s*)?([\d,]+)", lowered)
        income_match = re.search(r"income.{0,30}?(?:by|increase|up|decrease|down|drop|fall)\s*(?:₹|rs\.?\s*)?([\d,]+)", lowered)
        income_delta = float(income_match.group(1).replace(",", "")) if income_match else 0
        if income_match and re.search(r"(?:decrease|down|drop|fall)", lowered[income_match.start():income_match.end()]):
            income_delta *= -1
        result = run_what_if_simulation(
            db,
            dining_cut_pct=float(match.group(1)) if match else (30 if "dining" in lowered else 0),
            rent_change=float(rent_match.group(1).replace(",", "")) if rent_match else 0,
            extra_income=income_delta,
            month=selected_month,
            as_of=as_of,
        )
        tool = "simulate_goal_change"
        reason = "The question asks about a budget or goal change, so the deterministic scenario calculator was used."
        result_line = f"For {selected_month}, the modeled monthly surplus changes from ₹{result['base_monthly_surplus']:,.2f} to ₹{result['simulated_monthly_surplus']:,.2f}."
        if result["goal_impacts"]:
            goal = result["goal_impacts"][0]
            result_line += f" {goal['goal_name']} is projected for {goal['projected_completion'] or 'an unavailable date'} under the scenario."
        result_line += " Statement completeness is unknown, so this is a scenario rather than a prediction."
    elif re.search(r"\b(subscription|recurring|payment|charge)\b", lowered):
        result = detect_recurring_and_creep(db)
        tool = "detect_recurring_payments"
        reason = "The question asks about repeated payments; recurring candidates were derived from dated ledger entries."
        result_line = f"I found {len(result)} recurring-payment candidate(s). Each candidate shows its observed cadence and dates; service usage still needs your confirmation."
    elif re.search(r"\b(profile|emergency fund|fixed cost|income)\b", lowered):
        result = {"monthly_income": decimal_money(profile.monthly_income), "fixed_costs": decimal_money(profile.fixed_costs), "emergency_fund_current": decimal_money(profile.emergency_fund_current), "emergency_fund_target": decimal_money(profile.emergency_fund_target), "goals": [{"name": goal.name, "target": goal.target_amount, "saved": goal.saved_amount, "target_date": goal.target_date} for goal in goals]}
        tool = "get_financial_profile"
        reason = "The question asks about saved profile assumptions or goals; those fields were read from persistent storage."
        result_line = f"Your profile states monthly income of ₹{result['monthly_income']:,.2f}, fixed costs of ₹{result['fixed_costs']:,.2f}, and emergency savings of ₹{result['emergency_fund_current']:,.2f} against a target of ₹{result['emergency_fund_target']:,.2f}. These are profile entries, not bank-verified facts."
    else:
        result = monthly_summary(profile, transactions, selected_month)
        tool = "get_monthly_summary"
        reason = "A monthly cashflow question was interpreted as a request for the selected period summary."
        result_line = f"For {selected_month}, imported outflows total ₹{result['observed_expenses']:,.2f}; the profile-based modeled surplus is ₹{result['modeled_surplus']:,.2f}. {result['transactions_count']} transaction(s) fall in that month. Statement completeness is unknown."
    if allow_external_ai:
        external = _optional_external_coach(db, user_message, selected_month, as_of)
        if external:
            return {"guardrail_triggered": False, "reply": external["reply"], "agent_trace": {key: value for key, value in external.items() if key != "reply"}}
    trace = {"tool_selected": tool, "reason": reason, "verified_result": _json_safe(result), "ai_enabled": False}
    return {"guardrail_triggered": False, "reply": result_line, "agent_trace": trace}


def generate_guardrailed_coach_reply(db: Session, user_message: str) -> dict:
    return coach_response(db, user_message)
