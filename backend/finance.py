from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Iterable

from importers import normalize_date

ZERO = Decimal("0.00")
FIXED_CATEGORIES = {"Housing", "Utilities", "Insurance", "Debt Payment", "Fixed Costs"}
TRANSFER_CATEGORIES = {"Transfers", "Transfers / People", "Transfer", "Cash Withdrawal"}


def decimal_money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return ZERO


def amount_sum(transactions: Iterable[object]) -> Decimal:
    return sum((decimal_money(getattr(item, "amount", 0)) for item in transactions), ZERO)


def month_for_transactions(transactions: list[object], requested: str | None = None, today: date | None = None) -> str:
    if requested:
        try:
            return datetime.strptime(requested, "%Y-%m").strftime("%Y-%m")
        except ValueError as error:
            raise ValueError("month must use YYYY-MM format") from error
    dates = [str(getattr(row, "date", "")) for row in transactions]
    valid = [value[:7] for value in dates if len(value) >= 7 and value[4:5] == "-"]
    if valid:
        return max(valid)
    return (today or date.today()).strftime("%Y-%m")


def month_bounds(month: str) -> tuple[date, date]:
    start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    last = calendar.monthrange(start.year, start.month)[1]
    return start, start.replace(day=last)


def prior_month(month: str) -> str:
    start, _ = month_bounds(month)
    previous = start - timedelta(days=1)
    return previous.strftime("%Y-%m")


def day_for_transaction(row: object) -> date | None:
    try:
        return date.fromisoformat(normalize_date(getattr(row, "date", "")))
    except ValueError:
        return None


def filter_month(transactions: Iterable[object], month: str) -> list[object]:
    start, end = month_bounds(month)
    return [row for row in transactions if (day := day_for_transaction(row)) is not None and start <= day <= end]


def _is_transfer(row: object) -> bool:
    return getattr(row, "category", "") in TRANSFER_CATEGORIES


def _is_refund(row: object) -> bool:
    category = str(getattr(row, "category", "")).lower()
    narration = str(getattr(row, "raw_narration", "")).lower()
    return category == "refund" or (getattr(row, "txn_type", "") == "CREDIT" and any(term in narration for term in ("refund", "reversal", "chargeback")))


def refund_total(transactions: Iterable[object]) -> Decimal:
    return amount_sum(row for row in transactions if getattr(row, "txn_type", "") == "CREDIT" and _is_refund(row))


def category_totals(transactions: Iterable[object]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for row in transactions:
        if getattr(row, "txn_type", "") != "DEBIT" or _is_transfer(row):
            continue
        category = str(getattr(row, "category", "Uncategorised"))
        totals[category] = totals.get(category, ZERO) + decimal_money(getattr(row, "amount", 0))
    return totals


def monthly_summary(profile: object, transactions: list[object], month: str) -> dict:
    start, end = month_bounds(month)
    selected = filter_month(transactions, month)
    expenses = [row for row in selected if getattr(row, "txn_type", "") == "DEBIT" and not _is_transfer(row)]
    refunds = [row for row in selected if getattr(row, "txn_type", "") == "CREDIT" and _is_refund(row)]
    income_rows = [row for row in selected if getattr(row, "txn_type", "") == "CREDIT" and not _is_transfer(row) and not _is_refund(row)]
    fixed_rows = [row for row in expenses if getattr(row, "category", "") in FIXED_CATEGORIES]
    variable_rows = [row for row in expenses if getattr(row, "category", "") not in FIXED_CATEGORIES]
    observed_expenses = max(ZERO, amount_sum(expenses) - amount_sum(refunds))
    fixed_profile = decimal_money(getattr(profile, "fixed_costs", 0))
    fixed_observed = amount_sum(fixed_rows)
    fixed_for_model = max(fixed_profile, fixed_observed)
    variable_expenses = amount_sum(variable_rows)
    profile_income = decimal_money(getattr(profile, "monthly_income", 0))
    refund_amount = amount_sum(refunds)
    modeled_surplus = profile_income - fixed_for_model - variable_expenses + refund_amount

    by_category = category_totals(selected)
    if refunds:
        refund_total = amount_sum(refunds)
        by_category["Refunds"] = -refund_total

    row_days = sorted({day_for_transaction(row) for row in selected if day_for_transaction(row) is not None})
    actual_income = amount_sum(income_rows)
    net_observed_savings = actual_income - observed_expenses if income_rows else None
    period_complete = start <= (date.today() if date.today().strftime("%Y-%m") == month else end)
    return {
        "month": month,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "period_status": "month-to-date" if month == date.today().strftime("%Y-%m") else "calendar-month",
        "transactions_count": len(selected),
        "observed_income": actual_income,
        "profile_monthly_income": profile_income,
        "observed_expenses": observed_expenses,
        "observed_refunds": amount_sum(refunds),
        "modeled_surplus": modeled_surplus,
        "net_observed_savings": net_observed_savings,
        "fixed_cost_assumption": fixed_profile,
        "fixed_cost_observed": fixed_observed,
        "variable_expenses": variable_expenses,
        "category_breakdown": [{"name": key, "value": value} for key, value in sorted(by_category.items())],
        "data_quality": {
            "statement_completeness": "unknown; transaction dates do not prove a complete statement",
            "observed_first_date": row_days[0].isoformat() if row_days else None,
            "observed_last_date": row_days[-1].isoformat() if row_days else None,
            "rows_in_period": len(selected),
            "is_current_month": month == date.today().strftime("%Y-%m"),
            "model_note": "Modeled surplus = profile monthly income − max(profile fixed-cost assumption, observed fixed-category debits) − observed variable debits + identified refunds. Transfers are excluded. This model uses the selected period's observed debits and credits plus profile assumptions.",
        },
        "transactions": selected,
        "raw_expense_rows": expenses,
        "income_rows": income_rows,
    }


def compare_category_spending(current: list[object], previous: list[object], month: str) -> list[dict]:
    current_by = category_totals(current)
    previous_by = category_totals(previous)
    result = []
    for category in sorted(set(current_by) | set(previous_by)):
        now = current_by.get(category, ZERO)
        before = previous_by.get(category, ZERO)
        if before <= ZERO:
            continue
        delta = now - before
        percent = (delta / before * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if percent >= Decimal(20) and delta >= Decimal(500):
            result.append({"category": category, "current": now, "previous": before, "change": delta, "change_percent": percent, "month": month})
    return result


def _add_months(day: date, months: int) -> date:
    month_index = day.year * 12 + (day.month - 1) + months
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def project_goals(goals: Iterable[object], base_surplus: Decimal, scenario_surplus: Decimal, as_of: date | None = None) -> list[dict]:
    start = as_of or date.today()
    result = []
    for goal in goals:
        remaining = max(ZERO, decimal_money(getattr(goal, "target_amount", 0)) - decimal_money(getattr(goal, "saved_amount", 0)))
        months_base = int((remaining / base_surplus).to_integral_value(rounding=ROUND_CEILING)) if base_surplus > ZERO and remaining > ZERO else (0 if remaining == ZERO else None)
        months_scenario = int((remaining / scenario_surplus).to_integral_value(rounding=ROUND_CEILING)) if scenario_surplus > ZERO and remaining > ZERO else (0 if remaining == ZERO else None)
        base_date = _add_months(start, months_base) if months_base is not None else None
        projected = _add_months(start, months_scenario) if months_scenario is not None else None
        try:
            target = date.fromisoformat(normalize_date(getattr(goal, "target_date", "")))
        except ValueError:
            target = None
        result.append({
            "goal_name": getattr(goal, "name", "Financial goal"),
            "remaining": remaining,
            "base_months": months_base,
            "new_months": months_scenario,
            "base_completion": base_date.isoformat() if base_date else None,
            "projected_completion": projected.isoformat() if projected else None,
            "days_saved": (base_date - projected).days if base_date and projected else (0 if remaining == ZERO else None),
            "target_date": target.isoformat() if target else None,
            "days_vs_target": (target - projected).days if target and projected else None,
        })
    return result
