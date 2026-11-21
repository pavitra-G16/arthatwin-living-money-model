from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import Base, FinancialGoal, FinancialProfile, LearnedRule, MonthCoverage, SubscriptionFeedback, Transaction, normalize_database_url
from finance import monthly_summary, project_goals
from importers import csv_preview, money, normalize_date, pdf_preview, sms_preview
from main import app, get_db


def test_database_url_uses_installed_psycopg_driver_for_neon_postgres():
    assert normalize_database_url("postgres://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalize_database_url("postgresql://user:pass@host/db?sslmode=require") == "postgresql+psycopg://user:pass@host/db?sslmode=require"
    assert normalize_database_url("sqlite:///./arthatwin.db") == "sqlite:///./arthatwin.db"


def test_money_and_date_normalization_keep_paise_and_reject_bad_dates():
    assert money("₹1,234.565") == Decimal("1234.57")
    assert money("(250.25)") == Decimal("-250.25")
    assert normalize_date("21/11/2026") == "2026-11-21"
    try:
        normalize_date("31/02/2026")
    except ValueError as error:
        assert "calendar date" in str(error)
    else:
        raise AssertionError("invalid calendar date must be rejected")


def test_csv_preview_reports_bad_rows_instead_of_silently_dropping_them():
    result = csv_preview("\ufeffTransaction Date,Narration,Debit Amount,Credit Amount\n2026-11-01,Cafe,10.50,\nnot-a-date,Shop,20,\n2026-11-03,,30,\n".encode())
    assert len(result["transactions"]) == 1
    assert [issue["row"] for issue in result["issues"]] == [3, 4]
    assert result["transactions"][0]["amount"] == Decimal("10.50")


def test_csv_negative_amount_respects_explicit_direction_and_infers_debit_without_one():
    result = csv_preview(b"Date,Description,Amount,Type\n2026-11-01,Shop,-100.25,DR\n2026-11-02,Refund,-50.00,CR\n2026-11-03,Shop,-25.00,\n")
    assert [(row["amount"], row["txn_type"]) for row in result["transactions"]] == [
        (Decimal("100.25"), "DEBIT"),
        (Decimal("50.00"), "CREDIT"),
        (Decimal("25.00"), "DEBIT"),
    ]


def test_sms_missing_date_is_reviewed_not_filled_with_today():
    result = sms_preview("Rs. 499 debited to Netflix")
    assert result["transactions"][0]["date"] is None
    assert result["transactions"][0]["requires_review"] is True
    assert "choose a transaction date" in result["issues"][0]["message"].lower()


def test_text_pdf_statement_extracts_normalized_transaction():
    from io import BytesIO
    from pdfplumber import open as open_pdf
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>", b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    stream = b"BT /F1 12 Tf 50 700 Td (2026-11-02 UPI Zomato 500.00 DR) Tj ET"
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, item in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{index} 0 obj\n".encode() + item + b"\nendobj\n"
    xref = len(data)
    data += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    data += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    with open_pdf(BytesIO(data)) as pdf:
        assert "Zomato" in (pdf.pages[0].extract_text() or "")
    parsed = pdf_preview(bytes(data))
    assert parsed["transactions"][0]["merchant"] == "ZOMATO"
    assert parsed["transactions"][0]["amount"] == Decimal("500.00")


def test_monthly_summary_is_period_aware_and_separates_transfers_and_refunds():
    profile = SimpleNamespace(monthly_income=Decimal("50000"), fixed_costs=Decimal("10000"))
    txns = [
        SimpleNamespace(date="2026-10-31", amount=Decimal("9000"), txn_type="DEBIT", category="Dining Out", raw_narration="Cafe"),
        SimpleNamespace(date="2026-11-01", amount=Decimal("1000"), txn_type="DEBIT", category="Dining Out", raw_narration="Cafe"),
        SimpleNamespace(date="2026-11-02", amount=Decimal("5000"), txn_type="DEBIT", category="Transfers / People", raw_narration="UPI transfer"),
        SimpleNamespace(date="2026-11-03", amount=Decimal("200"), txn_type="CREDIT", category="Refund", raw_narration="Merchant refund"),
    ]
    summary = monthly_summary(profile, txns, "2026-11")
    assert summary["transactions_count"] == 3
    assert summary["observed_expenses"] == Decimal("800.00")
    assert summary["observed_refunds"] == Decimal("200.00")
    assert summary["modeled_surplus"] == Decimal("39200.00")
    assert "unknown" in summary["data_quality"]["statement_completeness"]


def test_refunds_flow_into_modeled_surplus_and_simulation():
    from engine import run_what_if_simulation
    client, factory, engine = _test_client()
    try:
        with factory() as db:
            db.add(FinancialProfile(monthly_income=Decimal("50000"), fixed_costs=Decimal("10000")))
            db.add(Transaction(date="2026-11-02", raw_narration="Cafe", merchant="CAFE", amount=Decimal("1000"), txn_type="DEBIT", category="Dining Out", source="CSV"))
            db.add(Transaction(date="2026-11-03", raw_narration="Cafe refund", merchant="CAFE", amount=Decimal("200"), txn_type="CREDIT", category="Refund", source="CSV"))
            db.add(Transaction(date="2026-11-04", raw_narration="UPI transfer", merchant="RAHUL", amount=Decimal("5000"), txn_type="DEBIT", category="Transfers / People", source="CSV"))
            db.commit()
            profile = db.query(FinancialProfile).first()
            rows = db.query(Transaction).all()
            summary = monthly_summary(profile, rows, "2026-11")
            scenario = run_what_if_simulation(db, dining_cut_pct=30, month="2026-11", as_of=date(2026, 11, 21))
        assert summary["modeled_surplus"] == Decimal("39200.00")
        assert scenario["base_monthly_surplus"] == Decimal("39200.00")
        assert scenario["simulated_monthly_surplus"] == Decimal("39500.00")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_goal_projection_respects_calendar_dates_and_target_date():
    goal = SimpleNamespace(name="Buffer", target_amount=Decimal("6000"), saved_amount=Decimal("0"), target_date="2027-06-21")
    result = project_goals([goal], Decimal("1000"), Decimal("2000"), date(2026, 11, 21))[0]
    assert result["base_completion"] == "2027-05-21"
    assert result["projected_completion"] == "2027-02-21"
    assert result["days_saved"] == 89
    assert result["days_vs_target"] == 120


def test_file_import_preview_confirmation_and_repeat_upload_are_idempotent():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_db():
        db = factory()
        try:
            if not db.query(FinancialProfile).first():
                db.add(FinancialProfile())
                db.commit()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        data = b"Date,Narration,Debit Amount,Credit Amount\n2026-11-04,UPI Zomato,520.25,\n"
        first = TestClient(app).post("/api/ingest/file/preview", files={"file": ("sample.csv", data, "text/csv")})
        assert first.status_code == 200
        preview = first.json()
        assert preview["parsed_count"] == 1
        confirmed = TestClient(app).post("/api/ingest/confirm", json={"preview_id": preview["preview_id"]})
        assert confirmed.json()["imported"] == 1
        second = TestClient(app).post("/api/ingest/file/preview", files={"file": ("sample.csv", data, "text/csv")})
        assert second.json()["duplicate_count"] == 1
        confirmed_again = TestClient(app).post("/api/ingest/confirm", json={"preview_id": second.json()["preview_id"]})
        assert confirmed_again.json()["duplicates"] == 1
        with factory() as db:
            assert db.query(Transaction).count() == 1
            assert db.query(Transaction).first().amount == Decimal("520.25")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _test_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), factory, engine


def test_sms_preview_confirm_and_profile_goal_persist_between_requests():
    client, factory, engine = _test_client()
    try:
        preview = client.post("/api/ingest/sms/preview", json={"sms_text": "Rs. 499 debited to Netflix on 04-11-2026"})
        assert preview.status_code == 200
        result = client.post("/api/ingest/confirm", json={"preview_id": preview.json()["preview_id"]})
        assert result.json()["imported"] == 1
        profile = {"monthly_income": "50000.00", "fixed_costs": "15000.00", "emergency_fund_current": "20000.00", "emergency_fund_target": "100000.00", "discretionary_budget": "10000.00"}
        assert client.post("/api/profile", json=profile).status_code == 200
        goal = {"name": "Buffer", "target_amount": "100000.00", "saved_amount": "20000.00", "target_date": "2027-12-01", "priority": 1}
        assert client.post("/api/goals", json=goal).status_code == 200
        with factory() as db:
            assert db.query(Transaction).count() == 1
            assert db.query(FinancialProfile).first().monthly_income == Decimal("50000.00")
            assert db.query(FinancialGoal).first().target_amount == Decimal("100000.00")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_coverage_is_required_before_drift_nudges_and_report_is_month_scoped():
    from engine import _external_coach_tool_result
    client, factory, engine = _test_client()
    try:
        with factory() as db:
            db.add(FinancialProfile(monthly_income=Decimal("50000"), fixed_costs=Decimal("10000")))
            for day, amount in (("2026-10-03", "1000"), ("2026-11-03", "2000")):
                db.add(Transaction(date=day, raw_narration="Cafe", merchant="CAFE", amount=Decimal(amount), txn_type="DEBIT", category="Dining Out", source="CSV", fingerprint=day))
            db.commit()
            assert _external_coach_tool_result(db, "get_spending_nudges", "2026-11", "Compare spending")["nudges"] == []
            assert _external_coach_tool_result(db, "get_spending_nudges", "2026-11", "Compare spending")["warnings"]
        before = client.get("/api/dashboard?month=2026-11").json()
        assert before["nudges"] == []
        assert any("confirmed complete" in warning for warning in before["data_quality_warnings"])
        for month in ("2026-10", "2026-11"):
            assert client.post(f"/api/months/{month}/coverage", json={"confirmed_complete": True}).status_code == 200
        with factory() as db:
            ai_tool_result = _external_coach_tool_result(db, "get_spending_nudges", "2026-11", "Compare spending")
            assert ai_tool_result["nudges"][0]["category"] == "Dining Out"
            assert ai_tool_result["warnings"] == []
        after = client.get("/api/dashboard?month=2026-11").json()
        assert after["nudges"][0]["category"] == "Dining Out"
        report = client.get("/api/reports/monthly?month=2026-10").json()
        assert report["month"] == "2026-10"
        assert report["expenses"] == 1000
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_public_demo_blocks_personal_writes_and_filters_private_rows(monkeypatch):
    client, factory, engine = _test_client()
    monkeypatch.setenv("ARTHATWIN_PUBLIC_DEMO", "1")
    try:
        with factory() as db:
            db.add(FinancialProfile(monthly_income=Decimal("90000"), is_demo=False))
            db.add(FinancialProfile(monthly_income=Decimal("85000"), is_demo=True))
            db.add(Transaction(date="2026-11-01", raw_narration="Private", merchant="PRIVATE", amount=Decimal("250"), txn_type="DEBIT", category="Shopping", source="CSV", fingerprint="private", is_demo=False))
            db.add(Transaction(date="2026-11-02", raw_narration="Fictional", merchant="DEMO", amount=Decimal("150"), txn_type="DEBIT", category="Shopping", source="CSV", fingerprint="demo", is_demo=True))
            db.commit()
        response = client.get("/api/dashboard?month=2026-11")
        assert response.status_code == 200
        assert response.json()["profile"]["monthly_income"] == 85000
        assert [row["merchant"] for row in response.json()["transactions"]] == ["DEMO"]
        denied = client.post("/api/profile", json={"monthly_income": 1, "fixed_costs": 0, "emergency_fund_current": 0, "emergency_fund_target": 0, "discretionary_budget": 0})
        assert denied.status_code == 403
        denied_import = client.post("/api/ingest/sms/preview", json={"sms_text": "Rs. 5 debit"})
        assert denied_import.status_code == 403
    finally:
        monkeypatch.delenv("ARTHATWIN_PUBLIC_DEMO", raising=False)
        app.dependency_overrides.clear()
        engine.dispose()


def test_guardrail_and_external_ai_off_by_default(monkeypatch):
    from engine import coach_response
    client, factory, engine = _test_client()
    monkeypatch.delenv("EXTERNAL_AI_ENABLED", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    try:
        with factory() as db:
            guarded = coach_response(db, "Which stock should I buy?", allow_external_ai=True)
            assert guarded["guardrail_triggered"] is True
            ordinary = coach_response(db, "How much did I spend?", allow_external_ai=True)
            assert ordinary["agent_trace"]["tool_selected"] == "get_monthly_summary"
            assert ordinary["agent_trace"]["ai_enabled"] is False
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_coach_distinguishes_profile_income_question_from_income_change_scenario():
    from engine import coach_response
    client, factory, engine = _test_client()
    try:
        with factory() as db:
            db.add(FinancialProfile(monthly_income=Decimal("40000"), fixed_costs=Decimal("10000")))
            db.add(FinancialGoal(name="Buffer", target_amount=Decimal("100000"), saved_amount=Decimal("20000"), target_date="2027-11-01"))
            db.commit()
            profile_answer = coach_response(db, "What is my monthly income?", month="2026-11", as_of=date(2026, 11, 21))
            scenario_answer = coach_response(db, "What if my income decreases by ₹5,000?", month="2026-11", as_of=date(2026, 11, 21))
        assert profile_answer["agent_trace"]["tool_selected"] == "get_financial_profile"
        assert "40,000.00" in profile_answer["reply"]
        assert scenario_answer["agent_trace"]["tool_selected"] == "simulate_goal_change"
        assert Decimal(scenario_answer["agent_trace"]["verified_result"]["income_change"]) == Decimal("-5000.00")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_demo_seed_and_confirmed_deletion_preserve_safety_contract():
    client, factory, engine = _test_client()
    try:
        with factory() as db:
            db.add(FinancialProfile(monthly_income=Decimal("77777"), fixed_costs=Decimal("12345")))
            db.add(Transaction(date="2026-11-01", raw_narration="User row", merchant="USER SHOP", amount=Decimal("25.00"), txn_type="DEBIT", category="Shopping", source="CSV", fingerprint="preexisting-user-row", is_demo=False))
            db.commit()
        seeded = client.post("/api/seed-demo")
        assert seeded.status_code == 200
        with factory() as db:
            assert db.query(Transaction).filter(Transaction.fingerprint == "preexisting-user-row").count() == 1
            profile = db.query(FinancialProfile).first()
            assert profile.monthly_income == Decimal("77777.00")
            assert profile.fixed_costs == Decimal("12345.00")
        denied = client.delete("/api/data")
        assert denied.status_code == 400
        confirmed = client.delete("/api/data", headers={"X-Confirm-Delete": "DELETE ARTHATWIN DATA"})
        assert confirmed.status_code == 200
        with factory() as db:
            assert db.query(Transaction).count() == 0
            assert db.query(FinancialGoal).count() == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_read_only_coach_tools_return_aggregates_and_reject_unknown_names():
    from engine import _external_coach_tool_result, _json_safe
    client, factory, engine = _test_client()
    try:
        with factory() as db:
            db.add(FinancialProfile(monthly_income=Decimal("40000"), fixed_costs=Decimal("10000")))
            db.add(Transaction(date="2026-11-02", raw_narration="Do not transmit this narration", merchant="CAFE", amount=Decimal("200.00"), txn_type="DEBIT", category="Dining Out", source="CSV", fingerprint="coach-tool-row"))
            db.commit()
            result = _json_safe(_external_coach_tool_result(db, "get_monthly_summary", "2026-11", "How is my month?"))
            assert result["observed_expenses"] == "200.00"
            assert "transactions" not in result
            assert "Do not transmit this narration" not in str(result)
            try:
                _external_coach_tool_result(db, "delete_user_data", "2026-11", "clear it")
            except ValueError:
                pass
            else:
                raise AssertionError("unlisted coach tools must be rejected")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_external_model_selects_a_validated_tool_then_local_code_executes_it(monkeypatch):
    import google
    import types as pytypes
    from engine import _optional_external_coach

    observed = {"calls": 0, "closed": False, "prompt": "", "args": {}}

    class FakeSdkObject:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_types = pytypes.ModuleType("google.genai.types")
    for name in ("FunctionDeclaration", "Tool", "GenerateContentConfig", "ToolConfig", "FunctionCallingConfig"):
        setattr(fake_types, name, FakeSdkObject)

    class FakeModels:
        def generate_content(self, **kwargs):
            observed["calls"] += 1
            observed["prompt"] = str(kwargs.get("contents"))
            return pytypes.SimpleNamespace(function_calls=[pytypes.SimpleNamespace(name="get_monthly_summary", args=observed["args"])])

    fake_genai = pytypes.ModuleType("google.genai")

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "fake-test-only-key"
            self.models = FakeModels()

        def close(self):
            observed["closed"] = True

    fake_genai.Client = FakeClient
    fake_genai.types = fake_types
    monkeypatch.setattr(google, "genai", fake_genai, raising=False)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    monkeypatch.setenv("EXTERNAL_AI_ENABLED", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-only-key")

    client, factory, engine = _test_client()
    try:
        with factory() as db:
            db.add(FinancialProfile(monthly_income=Decimal("40000"), fixed_costs=Decimal("10000")))
            db.add(Transaction(date="2026-11-02", raw_narration="Private statement narration", merchant="CAFE", amount=Decimal("200.00"), txn_type="DEBIT", category="Dining Out", source="CSV"))
            db.commit()
            result = _optional_external_coach(db, "How much did I spend?", "2026-11")
            assert result is not None
            assert result["tool_selected"] == "get_monthly_summary"
            assert result["ai_enabled"] is True
            assert "₹200.00" in result["reply"]
            assert observed["calls"] == 1
            assert observed["closed"] is True
            assert "Private statement narration" not in observed["prompt"]
            observed["args"] = {"profile_id": 5}
            assert _optional_external_coach(db, "How much did I spend?", "2026-11") is None
            assert observed["calls"] == 2
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
