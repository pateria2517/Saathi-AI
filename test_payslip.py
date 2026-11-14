"""Saathi AI — Payslip Explainer & Anomaly Engine Verification Suite (Step 2).

Tests:
1. Lakshmi warehouse packer dilemma with due date passed (payslip shows PF deducted, passbook credit is 0 after due date + N grace days).
2. Passbook deposit pending remittance grace period (due date has NOT passed yet -> informational note, not an anomaly).
3. Clean, fully compliant payslip (no false positive anomalies).
4. PF calculation on actual basic vs 15,000 statutory ceiling (both legitimate).
5. ESIC statutory threshold (Rs 21,000) and contribution-period continuous coverage rule (stays covered if covered at start of period).
6. Employer contribution matching (12% split) and zero employer share detection.
7. Month-to-month unexplained deduction jumps (>15% variance) treated as informational notes (not anomalies).
8. FastAPI endpoint /api/payslip/explain integration.
9. In-memory digital PDF/text extraction vs honest image OCR fallback ('ocr_not_installed').
"""
from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from main import app
from payslip_analyzer import PayslipInput, analyze_payslip

client = TestClient(app)


def test_lakshmi_warehouse_discrepancy_due_date_passed():
    """Key Persona Scenario: Lakshmi has Rs 1,380 deducted for PF, checked after the remittance due date + grace."""
    lakshmi = PayslipInput(
        worker_name="Lakshmi (Packer)",
        wage_month="2026-08",          # August 2026 slip (due 15 Sept 2026 + 3 days = 18 Sept 2026)
        as_of_date="2026-10-01",        # Checked in October (due date has passed!)
        basic_wage=11500.0,
        gross_salary=14200.0,
        employee_pf_deducted=1380.0,
        employee_esic_deducted=106.50,
        employer_pf_contribution=1380.0,
        employer_esic_contribution=461.50,
        passbook_deposit_credit=0.0,    # Missing!
        language="kn"
    )
    result = analyze_payslip(lakshmi)
    assert result.has_anomalies is True
    assert len(result.anomalies) == 1
    
    anomaly = result.anomalies[0]
    assert anomaly.code == "ANOMALY_PASSBOOK_MISSING_CREDIT"
    assert anomaly.severity == "High"
    assert "Paragraph 38" in anomaly.rule_citation
    assert "ಇಪಿಎಫ್ಒ ಪಾಸ್‌ಬುಕ್‌ನಲ್ಲಿ ಯಾವುದೇ ಹಣ ಜಮೆಯಾಗಿಲ್ಲ" in anomaly.message_indic
    assert "after the due date plus grace period (18 September 2026) (due date is the 15th)" in anomaly.message
    assert result.take_home_pay == 12713.50
    assert result.total_deductions == 1486.50
    assert result.employer_contributions == 1841.50
    
    # Verify auto-drafted HR ticket
    ticket = result.ticket_draft
    assert ticket is not None
    assert ticket.category == "PF / EPFO"
    assert ticket.priority == "High"
    assert ticket.requires_consent is True
    assert "Rs 1380.00" in ticket.suggested_description
    assert "Rs 0.0" in ticket.suggested_description


def test_passbook_missing_before_remittance_due_date_grace():
    """Remittance grace check: If checked before due date + N grace days, do NOT flag as anomaly; give informative note."""
    pending = PayslipInput(
        worker_name="Lakshmi (Packer)",
        wage_month="2026-10",          # October 2026 wage month (due 15 Nov + 3 days = 18 Nov 2026)
        as_of_date="2026-11-05",        # Checked on 5th Nov (13 days before cutoff!)
        basic_wage=11500.0,
        gross_salary=14200.0,
        employee_pf_deducted=1380.0,
        employee_esic_deducted=106.50,
        employer_pf_contribution=1380.0,
        passbook_deposit_credit=0.0,    # 0 because contractor hasn't remitted by 5th Nov
        language="kn"
    )
    result = analyze_payslip(pending)
    # Must NOT be an anomaly!
    assert result.has_anomalies is False
    assert len(result.anomalies) == 0
    assert result.ticket_draft is None
    
    # Must have informational note telling worker when to check again
    assert len(result.informational_notes) >= 1
    info = next(n for n in result.informational_notes if n.code == "INFO_PASSBOOK_PENDING_REMITTANCE")
    assert "18 November 2026" in info.message or "18" in info.message
    assert "18" in info.message_indic


def test_normal_compliant_payslip():
    """Verify that a compliant payslip produces 0 false positive anomalies."""
    compliant = PayslipInput(
        basic_wage=15000.0,
        gross_salary=18000.0,
        employee_pf_deducted=1800.0,
        employer_pf_contribution=1800.0,
        employee_esic_deducted=135.0,
        employer_esic_contribution=585.0,
        passbook_deposit_credit=1800.0,
        language="hi"
    )
    result = analyze_payslip(compliant)
    assert result.has_anomalies is False
    assert len(result.anomalies) == 0
    assert result.ticket_draft is None
    assert "सही पाई गई हैं" in result.summary_message


def test_pf_actual_basic_vs_statutory_ceiling():
    """Verify that both actual basic (12%) and statutory ceiling (capped at 1,800) are recognized as legitimate."""
    # Higher basic salary: Rs 20,000
    # Option A: Capped at Rs 15,000 ceiling -> 12% = Rs 1,800
    capped = PayslipInput(
        basic_wage=20000.0,
        gross_salary=25000.0,
        employee_pf_deducted=1800.0,
        passbook_deposit_credit=1800.0,
        language="en"
    )
    res_capped = analyze_payslip(capped)
    assert not any(a.code == "ANOMALY_PF_RATE_MISMATCH" for a in res_capped.anomalies)

    # Option B: Contributed on full basic -> 12% of 20,000 = Rs 2,400
    actual = PayslipInput(
        basic_wage=20000.0,
        gross_salary=25000.0,
        employee_pf_deducted=2400.0,
        passbook_deposit_credit=2400.0,
        language="en"
    )
    res_actual = analyze_payslip(actual)
    assert not any(a.code == "ANOMALY_PF_RATE_MISMATCH" for a in res_actual.anomalies)

    # Option C: Arbitrary invalid deduction (Rs 1,500)
    invalid = PayslipInput(
        basic_wage=20000.0,
        gross_salary=25000.0,
        employee_pf_deducted=1500.0,
        language="en"
    )
    res_invalid = analyze_payslip(invalid)
    assert any(a.code == "ANOMALY_PF_RATE_MISMATCH" for a in res_invalid.anomalies)


def test_esic_contribution_period_rule():
    """Verify ESIC contribution-period rule: covered worker remains covered even if gross crosses Rs 21,000."""
    # Scenario 1: Worker was covered at start of 6-month period, wage increased to Rs 24,000
    covered_continuation = PayslipInput(
        basic_wage=18000.0,
        gross_salary=24000.0,
        employee_pf_deducted=1800.0,
        employee_esic_deducted=180.0,  # 0.75% of 24,000
        was_covered_at_start_of_period=True,
        passbook_deposit_credit=1800.0,
        language="en"
    )
    res_covered = analyze_payslip(covered_continuation)
    assert res_covered.has_anomalies is False
    assert not any(a.code == "ANOMALY_ESIC_OVER_CEILING" for a in res_covered.anomalies)
    assert any(n.code == "INFO_ESIC_CONTRIBUTION_PERIOD_COVERED" for n in res_covered.informational_notes)

    # Scenario 2: Worker was NOT covered at start of period (new hire or already above ceiling), wage Rs 24,000
    not_covered = PayslipInput(
        basic_wage=18000.0,
        gross_salary=24000.0,
        employee_pf_deducted=1800.0,
        employee_esic_deducted=180.0,
        was_covered_at_start_of_period=False,
        passbook_deposit_credit=1800.0,
        language="en"
    )
    res_not_covered = analyze_payslip(not_covered)
    assert res_not_covered.has_anomalies is True
    assert any(a.code == "ANOMALY_ESIC_OVER_CEILING" for a in res_not_covered.anomalies)


def test_employer_share_matching():
    """Verify employer PF contribution matching and missing employer share."""
    # 1. Employer share is Rs 0.0
    zero_share = PayslipInput(
        basic_wage=11500.0,
        gross_salary=14200.0,
        employee_pf_deducted=1380.0,
        employer_pf_contribution=0.0,
        language="kn"
    )
    res_zero = analyze_payslip(zero_share)
    assert any(a.code == "ANOMALY_EMPLOYER_PF_ZERO" for a in res_zero.anomalies)

    # 2. Employer share is significantly short (Rs 500 vs Rs 1,380)
    short_share = PayslipInput(
        basic_wage=11500.0,
        gross_salary=14200.0,
        employee_pf_deducted=1380.0,
        employer_pf_contribution=500.0,
        language="kn"
    )
    res_short = analyze_payslip(short_share)
    assert any(a.code == "ANOMALY_EMPLOYER_PF_SHORT" for a in res_short.anomalies)


def test_month_to_month_pf_jump_is_informational_not_anomaly():
    """Verify month-over-month variance (>15%) is categorized as an informational note, not an anomaly."""
    jump = PayslipInput(
        basic_wage=15000.0,
        gross_salary=18000.0,
        employee_pf_deducted=1800.0,
        previous_month_pf_deducted=1380.0,  # Jump from 1380 to 1800 is 30.4%
        passbook_deposit_credit=1800.0,
        language="en"
    )
    res = analyze_payslip(jump)
    # Must NOT be flagged as anomaly
    assert res.has_anomalies is False
    assert not any(a.code == "ANOMALY_MOM_PF_JUMP" for a in res.anomalies)
    
    # Must be logged in informational_notes
    assert any(n.code == "INFO_MOM_PF_JUMP" for n in res.informational_notes)


def test_api_payslip_explain_endpoint():
    """Verify POST /api/payslip/explain integration and assert every field renderPayslipAnalysis() reads."""
    payload = {
        "wage_month": "2026-08",
        "as_of_date": "2026-10-01",
        "basic_wage": 11500.0,
        "gross_salary": 14200.0,
        "employee_pf_deducted": 1380.0,
        "employer_pf_contribution": 1380.0,
        "employee_esic_deducted": 106.50,
        "employer_esic_contribution": 461.50,
        "passbook_deposit_credit": 0.0,
        "language": "kn"
    }
    res = client.post("/api/payslip/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    
    # 1. Summary metric fields read by renderPayslipAnalysis()
    assert "take_home_pay" in data and isinstance(data["take_home_pay"], (int, float))
    assert data["take_home_pay"] == 12713.50
    assert "total_deductions" in data and isinstance(data["total_deductions"], (int, float))
    assert data["total_deductions"] == 1486.50
    assert "employer_contributions" in data and isinstance(data["employer_contributions"], (int, float))
    assert data["employer_contributions"] == 1841.50
    assert "net_take_home" in data and data["net_take_home"] == 12713.50
    assert "gross_salary" in data and data["gross_salary"] == 14200.00
    assert "pf_wage" in data and data["pf_wage"] == 11500.00
    
    # 2. Status & flags
    assert "has_anomalies" in data and data["has_anomalies"] is True
    
    # 3. Anomalies array and item fields
    assert "anomalies" in data and len(data["anomalies"]) >= 1
    anom = data["anomalies"][0]
    for field in ("code", "severity", "title", "rule_citation", "message_indic", "message"):
        assert field in anom and anom[field], f"Missing or empty field {field} in anomaly item"
    assert anom["code"] == "ANOMALY_PASSBOOK_MISSING_CREDIT"
    assert "after the due date plus grace period (18 September 2026) (due date is the 15th)" in anom["message"]
    
    # 4. Informational notes array
    assert "informational_notes" in data and isinstance(data["informational_notes"], list)
    
    # 5. Line-by-line breakdown array and item fields
    assert "breakdown" in data and len(data["breakdown"]) >= 3
    for b in data["breakdown"]:
        for field in ("name", "category", "amount", "explanation_indic", "explanation_en"):
            assert field in b, f"Missing field {field} in breakdown item"
        assert b["category"] in {"earning", "deduction", "employer_share"}
        assert isinstance(b["amount"], (int, float))
        
    # 6. Ticket draft fields
    assert "ticket_draft" in data and data["ticket_draft"] is not None
    td = data["ticket_draft"]
    for field in ("title", "category", "priority", "language", "suggested_description", "requires_consent", "evidence_payload"):
        assert field in td, f"Missing field {field} in ticket_draft"
    assert td["priority"] == "High"
    assert td["requires_consent"] is True
    assert "after the due date plus grace period (18 September 2026) (due date is the 15th)" in td["suggested_description"]


def test_api_payslip_upload_ocr_honesty_for_images_and_pdfs():
    """Verify honesty: pypdf reads digital PDFs; images report ocr_not_installed with clear installation guide."""
    # 1. Text / Digital PDF text extraction works in memory
    sample_txt = "Salary Slip for October\nBasic Pay: 11500.00\nGross Earnings: 14200.00\nPF: 1380.00\nESIC: 106.50\n"
    files = {"file": ("payslip.txt", io.BytesIO(sample_txt.encode("utf-8")), "text/plain")}
    res = client.post("/api/payslip/upload-ocr", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["extracted_fields"]["basic_wage"] == 11500.0

    # 2. Raster image upload is honest: reports ocr_not_installed with pip install guide
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    img_files = {"file": ("payslip_photo.png", io.BytesIO(fake_png), "image/png")}
    img_res = client.post("/api/payslip/upload-ocr", files=img_files)
    assert img_res.status_code == 200
    img_data = img_res.json()
    assert img_data["success"] is False
    assert img_data["status"] == "ocr_not_installed"
    assert "pip install pytesseract" in img_data["how_to_install"]
    assert img_data["manual_entry_recommended"] is True
