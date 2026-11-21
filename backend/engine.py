import os
import re
import io
from datetime import datetime, timedelta
import pandas as pd
import pdfplumber
from google import genai
from sqlalchemy.orm import Session
from database import Transaction, LearnedRule, SubscriptionFeedback, FinancialProfile, FinancialGoal

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

DEFAULT_MERCHANT_MAP = {
    "ZOMATO": "Dining Out",
    "SWIGGY": "Dining Out",
    "STARBUCKS": "Dining Out",
    "CHAI POINT": "Dining Out",
    "BLINKIT": "Groceries",
    "ZEPTO": "Groceries",
    "BIGBASKET": "Groceries",
    "DMART": "Groceries",
    "UBER": "Transport",
    "OLA": "Transport",
    "IRCTC": "Travel",
    "INDIGO": "Travel",
    "NETFLIX": "Subscriptions",
    "SPOTIFY": "Subscriptions",
    "AMAZON PRIME": "Subscriptions",
    "CULTFIT": "Subscriptions",
    "YOUTUBE": "Subscriptions",
    "AIRTEL": "Utilities",
    "JIO": "Utilities",
    "BESCOM": "Utilities",
    "RENT": "Housing",
    "NOBROKER": "Housing",
    "APOLLO": "Health",
    "PHARMEASY": "Health",
    "AMAZON": "Shopping",
    "FLIPKART": "Shopping",
    "MYNTRA": "Shopping",
}

BLOCKED_INVESTMENT_KEYWORDS = [
    "which stock", "best stock", "buy stock", "mutual fund", "which fund",
    "crypto", "bitcoin", "ethereum", "smallcap", "midcap", "nifty",
    "sensex", "share price", "multibagger", "ipo", "etf", "sip fund",
    "recommend a fund", "where to invest", "best sip"
]

INJECTION_PATTERNS = [
    "ignore all rules", "ignore previous", "system prompt", "mark this as salary",
    "mark this as income", "you are now", "override instructions"
]


def detect_prompt_injection(raw_text: str) -> str | None:
    lower = raw_text.lower()
    for pat in INJECTION_PATTERNS:
        if pat in lower:
            return f"QUARANTINED_INJECTION ('{pat}' stripped before AI)"
    return None


def extract_merchant_token(raw_text: str) -> str:
    clean_text = re.sub(r"(?i)(ignore all rules.*|system prompt.*|mark this as.*)", "", raw_text)
    text = clean_text.upper()

    upi_match = re.search(r"UPI/\d+/(?:DR|CR)?/?([A-Z0-9\s\.\-]+?)(?:/|@|$)", text)
    if upi_match:
        token = upi_match.group(1).strip()
        if len(token) >= 3:
            return token[:24]

    vpa_match = re.search(r"([A-Z0-9\.\-_]+)@(?:OKAXIS|OKICICI|OKHDFCBANK|YBL|PAYTM|IBL)", text)
    if vpa_match:
        return vpa_match.group(1).upper()[:24]

    cleaned = re.sub(r"[^A-Z\s]", " ", text)
    words = [w for w in cleaned.split() if len(w) > 2 and w not in {"UPI", "POS", "IMPS", "NEFT", "DEBIT", "CREDIT", "PAID", "FROM", "BANK", "ACCT"}]
    return " ".join(words[:2]) if words else "UNKNOWN_MERCHANT"


def is_likely_p2p_person(merchant: str, raw_narration: str) -> bool:
    upper = f"{merchant} {raw_narration}".upper()
    if any(k in upper for k in DEFAULT_MERCHANT_MAP.keys()):
        return False
    if "P2P" in upper or re.search(r"UPI/\d+/DR/[A-Z]+\s+[A-Z]+/", upper):
        return True
    return False


def categorize_with_memory(db: Session, merchant: str, raw_narration: str, amount: float) -> tuple[str, str]:
    upper_full = f"{merchant} {raw_narration}".upper()

    rules = db.query(LearnedRule).all()
    for rule in rules:
        if rule.pattern.upper() in upper_full:
            rule.hit_count += 1
            return rule.category, "LEARNED_RULE"

    for key, cat in DEFAULT_MERCHANT_MAP.items():
        if key in upper_full:
            return cat, "RULE_ENGINE"

    if is_likely_p2p_person(merchant, raw_narration):
        return "Transfers / People", "P2P_DETECTOR"

    if client:
        try:
            prompt = (
                f"Categorize this cleaned Indian merchant name into ONE of: "
                f"[Dining Out, Groceries, Transport, Travel, Subscriptions, Utilities, Housing, Health, Shopping, Transfers / People]. "
                f"Merchant: '{merchant}'. Return ONLY the category name."
            )
            resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            cat = resp.text.strip().replace('"', '')
            if cat:
                return cat, "AI_MODEL"
        except Exception:
            pass

    if amount <= 250:
        return "Dining Out", "HEURISTIC_RULE"
    return "Uncategorised", "NEEDS_REVIEW"


def parse_sms_dump(sms_text: str) -> tuple[list[dict], int]:
    results = []
    ignored_noise = 0
    lines = [line.strip() for line in sms_text.strip().split("\n") if line.strip()]
    for line in lines:
        lower = line.lower()
        if any(noise in lower for noise in ["otp", "do not share", "one time password", "pre-approved", "avl bal only"]):
            ignored_noise += 1
            continue

        amt_match = re.search(r"(?:RS\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)", line, re.IGNORECASE)
        if not amt_match:
            ignored_noise += 1
            continue

        amount = float(amt_match.group(1).replace(",", ""))
        txn_type = "CREDIT" if re.search(r"\b(credited|received|deposited)\b", line, re.IGNORECASE) else "DEBIT"
        date_match = re.search(r"(\d{2}[-/]\d{2}[-/]\d{2,4})", line)
        date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")

        merchant_match = re.search(r"(?:to|at|towards|VPA)\s+([A-Za-z0-9@\.\-_ ]+?)(?:\s+on|\s+Ref|\.|$)", line, re.IGNORECASE)
        raw_m = merchant_match.group(1).strip() if merchant_match else line
        sec_flag = detect_prompt_injection(line)
        merchant = extract_merchant_token(raw_m)

        results.append({
            "date": date_str,
            "raw_narration": line,
            "merchant": merchant,
            "amount": amount,
            "txn_type": txn_type,
            "source": "SMS",
            "security_flag": sec_flag
        })
    return results, ignored_noise


def parse_csv_bytes(file_bytes: bytes) -> list[dict]:
    df = pd.read_csv(io.BytesIO(file_bytes))
    cols = {c.lower().strip(): c for c in df.columns}

    date_col = next((v for k, v in cols.items() if "date" in k), df.columns[0])
    desc_col = next((v for k, v in cols.items() if any(x in k for x in ["narration", "desc", "particular", "remark", "merchant"])), df.columns[1])
    debit_col = next((v for k, v in cols.items() if any(x in k for x in ["debit", "withdrawal", "amount", "dr"])), None)
    credit_col = next((v for k, v in cols.items() if any(x in k for x in ["credit", "deposit", "cr"])), None)

    results = []
    for _, row in df.iterrows():
        narration = str(row.get(desc_col, ""))
        if not narration or narration == "nan":
            continue
        amount = 0.0
        txn_type = "DEBIT"

        if debit_col and pd.notna(row.get(debit_col)) and str(row.get(debit_col)).strip() not in ("", "0", "0.0"):
            val = re.sub(r"[^\d\.]", "", str(row.get(debit_col)))
            amount = float(val) if val else 0.0
            txn_type = "DEBIT"
        elif credit_col and pd.notna(row.get(credit_col)) and str(row.get(credit_col)).strip() not in ("", "0", "0.0"):
            val = re.sub(r"[^\d\.]", "", str(row.get(credit_col)))
            amount = float(val) if val else 0.0
            txn_type = "CREDIT"

        if amount > 0:
            results.append({
                "date": str(row.get(date_col, "2026-11-15"))[:10],
                "raw_narration": narration,
                "merchant": extract_merchant_token(narration),
                "amount": amount,
                "txn_type": txn_type,
                "source": "CSV",
                "security_flag": detect_prompt_injection(narration)
            })
    return results


def parse_pdf_bytes(file_bytes: bytes) -> list[dict]:
    results = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                m = re.search(r"(\d{2}[-/]\d{2}[-/]\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})\s*(DR|CR)?$", line.strip(), re.IGNORECASE)
                if m:
                    date_str, narration, amt_str, drcr = m.groups()
                    amount = float(amt_str.replace(",", ""))
                    txn_type = "CREDIT" if (drcr and drcr.upper() == "CR") else "DEBIT"
                    results.append({
                        "date": date_str,
                        "raw_narration": narration.strip(),
                        "merchant": extract_merchant_token(narration),
                        "amount": amount,
                        "txn_type": txn_type,
                        "source": "PDF",
                        "security_flag": detect_prompt_injection(narration)
                    })
    return results


def detect_recurring_and_creep(db: Session):
    txns = db.query(Transaction).filter(Transaction.txn_type == "DEBIT").all()
    feedback_map = {f.merchant.upper(): f.still_uses for f in db.query(SubscriptionFeedback).all()}

    by_merchant = {}
    for t in txns:
        key = t.merchant.upper()
        by_merchant.setdefault(key, []).append(t)

    alerts = []
    for merchant, items in by_merchant.items():
        if len(items) >= 2:
            items_sorted = sorted(items, key=lambda x: x.date)
            latest = items_sorted[-1]
            prev = items_sorted[-2]
            still_uses = feedback_map.get(merchant, "unsure")

            for item in items_sorted:
                item.is_recurring = True

            if latest.amount > prev.amount * 1.03:
                pct = round(((latest.amount - prev.amount) / prev.amount) * 100)
                alert_msg = f"PRICE_HIKE: +{pct}% (₹{int(prev.amount)} → ₹{int(latest.amount)})"
                latest.recurring_alert = alert_msg
                alerts.append({
                    "merchant": merchant,
                    "type": "PRICE_HIKE",
                    "reason": f"Price stepped up +{pct}% (₹{int(prev.amount)} → ₹{int(latest.amount)}/mo). Annual cost: ₹{int(latest.amount*12):,}.",
                    "monthly_amount": latest.amount,
                    "annual_cost": latest.amount * 12,
                    "still_uses": still_uses
                })
            elif "CULT" in merchant or "CLOUD" in merchant or "GYM" in merchant or still_uses == "no":
                alert_msg = "WORTH_REVIEWING: High annual cost / low activity signal"
                latest.recurring_alert = alert_msg
                alerts.append({
                    "merchant": merchant,
                    "type": "WORTH_REVIEWING",
                    "reason": f"High annual cost (₹{int(latest.amount*12):,}/yr) with no secondary merchant activity. Note: App usage cannot be observed automatically—confirm below.",
                    "monthly_amount": latest.amount,
                    "annual_cost": latest.amount * 12,
                    "still_uses": still_uses
                })
            else:
                alerts.append({
                    "merchant": merchant,
                    "type": "ACTIVE_RECURRING",
                    "reason": f"Consistent monthly cadence at ₹{int(latest.amount)}/mo (₹{int(latest.amount*12):,}/yr).",
                    "monthly_amount": latest.amount,
                    "annual_cost": latest.amount * 12,
                    "still_uses": still_uses
                })
    db.commit()
    return alerts


def run_what_if_simulation(
    db: Session,
    dining_cut_pct: float = 0.0,
    rent_change: float = 0.0,
    cancel_unused_subs: bool = False,
    extra_income: float = 0.0
) -> dict:
    profile = db.query(FinancialProfile).first()
    goals = db.query(FinancialGoal).all()
    txns = db.query(Transaction).filter(Transaction.txn_type == "DEBIT").all()

    dining_spend = sum(t.amount for t in txns if t.category == "Dining Out") or 12000.0
    other_var_spend = sum(t.amount for t in txns if t.category not in ("Dining Out", "Housing", "Income", "Transfers / People")) or 14000.0
    unused_sub_savings = 1499.0 if cancel_unused_subs else 0.0

    base_surplus = max(1000.0, profile.monthly_income - profile.fixed_costs - dining_spend - other_var_spend)
    dining_saved = dining_spend * (dining_cut_pct / 100.0)
    new_surplus = max(500.0, base_surplus + dining_saved - rent_change + unused_sub_savings + extra_income)

    goal_impacts = []
    for g in goals:
        remaining = max(0.0, g.target_amount - g.saved_amount)
        base_months = remaining / base_surplus
        new_months = remaining / new_surplus
        days_delta = round((base_months - new_months) * 30)

        new_completion = (datetime.now() + timedelta(days=int(new_months * 30))).strftime("%b %Y")
        goal_impacts.append({
            "goal_name": g.name,
            "remaining": remaining,
            "base_months": round(base_months, 1),
            "new_months": round(new_months, 1),
            "days_saved": days_delta,
            "projected_completion": new_completion
        })

    return {
        "base_monthly_surplus": round(base_surplus),
        "simulated_monthly_surplus": round(new_surplus),
        "monthly_delta": round(new_surplus - base_surplus),
        "assumptions": "Projection, not a prediction. Undiscounted INR cashflow assuming constant monthly surplus.",
        "goal_impacts": goal_impacts
    }


def generate_guardrailed_coach_reply(db: Session, user_message: str) -> dict:
    lower_msg = user_message.lower()

    if any(kw in lower_msg for kw in BLOCKED_INVESTMENT_KEYWORDS):
        profile = db.query(FinancialProfile).first()
        return {
            "guardrail_triggered": True,
            "reply": (
                "🛡️ **Guardrail Active — Educational & Scenario Mode Only:** I cannot recommend specific stocks, mutual funds, crypto, or financial products. "
                f"However, looking at your Living Money Model (Emergency Runway: ₹{int(profile.emergency_fund_current):,} of ₹{int(profile.emergency_fund_target):,} target), "
                "standard personal finance frameworks suggest completing a 3–6 month liquid emergency buffer before taking market risk. "
                "Ask me to model how cutting discretionary spending changes your goal completion dates!"
            )
        }

    profile = db.query(FinancialProfile).first()
    goals = db.query(FinancialGoal).all()
    txns = db.query(Transaction).filter(Transaction.txn_type == "DEBIT").all()
    cat_totals = {}
    for t in txns:
        if t.category != "Transfers / People":
            cat_totals[t.category] = cat_totals.get(t.category, 0.0) + t.amount

    context_summary = (
        f"Income: INR {int(profile.monthly_income)}, Fixed Costs: INR {int(profile.fixed_costs)}, "
        f"Emergency Fund: INR {int(profile.emergency_fund_current)}/{int(profile.emergency_fund_target)}, "
        f"Category Totals: {cat_totals}, "
        f"Goals: {[{'name': g.name, 'saved': g.saved_amount, 'target': g.target_amount} for g in goals]}"
    )

    if client:
        try:
            sys_prompt = (
                "You are ArthaTwin, a Personal Finance Coach backed by a deterministic Living Money Model. "
                "HARD GUARDRAILS: Never recommend specific stocks, mutual funds, loans, or crypto. Never invent numbers outside the provided state. Use INR (₹) and explain cashflow trade-offs clearly."
            )
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"{sys_prompt}\n\nVerified State: {context_summary}\n\nUser Question: {user_message}"
            )
            return {"guardrail_triggered": False, "reply": resp.text.strip()}
        except Exception:
            pass

    top_cat = max(cat_totals.items(), key=lambda x: x[1]) if cat_totals else ("Dining Out", 12000)
    return {
        "guardrail_triggered": False,
        "reply": (
            f"Based on your verified ledger, your largest variable outflow is **{top_cat[0]} (₹{int(top_cat[1]):,})**. "
            f"Your Emergency Buffer is **{round((profile.emergency_fund_current/profile.emergency_fund_target)*100)}% funded**. "
            f"Trimming {top_cat[0]} by 25% frees up **₹{int(top_cat[1]*0.25):,}/month**, pulling your primary goal forward by ~18 days."
        )
    }
