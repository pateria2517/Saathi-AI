"""Saathi AI — Payslip Explainer & Anomaly Engine (Step 2).

Key Principles:
1. Deterministic code reading rules_config.py (not LLM judgment).
2. Every flag cites the statutory rule cataloged in rules_config.py and uses neutral wording:
   "possible issue, please confirm with HR / EPFO passbook" (never accuses employer).
3. Covers:
   - PF on actual basic vs. 15,000 statutory ceiling (both can be legitimate).
   - Passbook credit vs. payslip deduction discrepancy with due date + N grace days check:
     Only flags if remittance due date (15th of following month) + N grace days has passed.
     Otherwise provides an informative notice of when to check again.
   - ESIC applicability against the 21,000 wage ceiling with contribution-period rule:
     Workers covered at the start of a 6-month period remain covered even if gross crosses ceiling.
   - Employer contribution matching (12% split into 8.33% EPS + 3.67% EPF).
   - Month-to-month deduction jumps (> 15% variance) treated as informational notices (not anomalies).
4. Explanations available in Kannada, Hindi, Tamil, and English.
"""
from __future__ import annotations

import io
import math
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from rules_config import EPF_RULES, ESIC_RULES, STATUTORY_CITATIONS, EPFO_SERVICES, ESIC_SERVICES


class PayslipInput(BaseModel):
    worker_name: Optional[str] = Field(default="Employee", description="Worker name or identifier")
    wage_month: Optional[str] = Field(default=None, description="Month of payslip in YYYY-MM format, e.g. 2026-09")
    as_of_date: Optional[str] = Field(default=None, description="Date of evaluation in YYYY-MM-DD format (defaults to current date)")
    basic_wage: float = Field(..., ge=0, description="Monthly Basic Wage in INR")
    dearness_allowance: float = Field(default=0.0, ge=0, description="Dearness Allowance (DA) in INR")
    retaining_allowance: float = Field(default=0.0, ge=0, description="Retaining Allowance in INR")
    other_allowances: float = Field(default=0.0, ge=0, description="HRA, Special, Conveyance etc. in INR")
    gross_salary: float = Field(..., ge=0, description="Total Monthly Gross Earnings in INR")
    employee_pf_deducted: float = Field(..., ge=0, description="Employee PF deducted on payslip in INR")
    employer_pf_contribution: Optional[float] = Field(default=None, ge=0, description="Employer PF share shown on payslip in INR")
    employee_esic_deducted: Optional[float] = Field(default=None, ge=0, description="Employee ESIC deducted on payslip in INR")
    employer_esic_contribution: Optional[float] = Field(default=None, ge=0, description="Employer ESIC share in INR")
    passbook_deposit_credit: Optional[float] = Field(default=None, ge=0, description="Actual deposit appearing on EPFO passbook in INR")
    previous_month_pf_deducted: Optional[float] = Field(default=None, ge=0, description="Last month's PF deduction in INR (for jump checks)")
    was_covered_at_start_of_period: bool = Field(default=False, description="Whether worker was covered by ESIC at start of 6-month contribution period")
    is_disability: bool = Field(default=False, description="Person with disability (higher ESIC ceiling 25k)")
    language: str = Field(default="kn", description="Explanation language: hi, kn, ta, en")


class AnomalyItem(BaseModel):
    code: str
    severity: str  # "High", "Medium", "Low"
    title: str
    message: str
    message_indic: str
    rule_citation: str
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    recommendation: str


class InformationalNote(BaseModel):
    code: str
    title: str
    message: str
    message_indic: str
    rule_citation: str
    recommendation: str


class BreakdownItem(BaseModel):
    name: str
    category: str  # "earning", "deduction", "employer_share"
    amount: float
    explanation_indic: str
    explanation_en: str


class DraftHRTicket(BaseModel):
    title: str
    category: str
    priority: str
    language: str
    suggested_description: str
    requires_consent: bool = True
    evidence_payload: Dict[str, Any]


class PayslipAnalysisResult(BaseModel):
    pf_wage: float
    gross_salary: float
    net_take_home: float
    take_home_pay: float
    total_deductions: float
    employer_contributions: float
    expected_pf_actual_wage: float
    expected_pf_statutory_ceiling: float
    expected_esic: float
    anomalies: List[AnomalyItem]
    has_anomalies: bool
    informational_notes: List[InformationalNote] = Field(default_factory=list)
    breakdown: List[BreakdownItem]
    summary_message: str
    ticket_draft: Optional[DraftHRTicket] = None
    language: str


# ==============================================================================
# MULTILINGUAL EXPLANATIONS FOR LINE ITEMS
# ==============================================================================

EXPLANATIONS = {
    "basic": {
        "hi": "मूल वेतन (Basic Pay) आपके वेतन का मुख्य हिस्सा है, जिस पर 12% पीएफ और अन्य शಾಸनಬದ್ಧ लाभ गिने जाते हैं।",
        "kn": "ಮೂಲ ವೇತನ (Basic Pay) ನಿಮ್ಮ ಸಂಬಳದ ಮುಖ್ಯ ಭಾಗವಾಗಿದ್ದು, ಇದರ ಮೇಲೆ ಶಾಸನಬದ್ಧ 12% ಪಿಎಫ್ ಕಡಿತವನ್ನು ಲೆಕ್ಕಹಾಕಲಾಗುತ್ತದೆ.",
        "ta": "அடிப்படை ஊதியம் (Basic Pay) உங்கள் சம்பளத்தின் பிரதான பகுதி; இதன் மீதே சட்டப்பூர்வ 12% பிஎஃப் கணக்கிடப்படுகிறது.",
        "en": "Basic Wage is the foundational salary component upon which 12% statutory PF is calculated."
    },
    "da": {
        "hi": "महंगाई भत्ता (DA) जीवनयापन की लागत के लिए दिया जाता है और इसे पीएफ वेतन का हिस्सा माना जाता है।",
        "kn": "ತುಟ್ಟಿಭತ್ಯೆ (DA) ಜೀವನ ವೆಚ್ಚಕ್ಕಾಗಿ ನೀಡಲಾಗುವ ಭತ್ಯೆಯಾಗಿದ್ದು, ಇದು ಪಿಎಫ್ ವೇತನದ ಭಾಗವಾಗಿರುತ್ತದೆ.",
        "ta": "அகவிலைப்படி (DA) வாழ்க்கைச் செலவுகளுக்காக வழங்கப்படுகிறது; இது பிஎஃப் ஊதியத்தின் பகுதியாகும்.",
        "en": "Dearness Allowance (DA) offsets cost of living and forms part of PF wages."
    },
    "allowances": {
        "hi": "अन्य भत्ते (जैसे मकान किराया HRA, विशेष भत्ता) सकल वेतन में जुड़ते हैं।",
        "kn": "ಇತರ ಭತ್ಯೆಗಳು (ಮನೆ ಬಾಡಿಗೆ HRA, ವಿಶೇಷ ಭತ್ಯೆ) ನಿಮ್ಮ ಒಟ್ಟು ಗಳಿಕೆಗೆ (Gross) ಸೇರ್ಪಡೆಯಾಗುತ್ತವೆ.",
        "ta": "பிற படிகள் (வீட்டு வாடகை HRA, சிறப்புப் படி) உங்கள் மொத்த ஊதியத்தில் இணைகின்றன.",
        "en": "Other allowances (HRA, special allowance) form part of Gross earnings."
    },
    "pf_employee": {
        "hi": "कर्मचारी पीएफ (12%): यह आपके वेतन से कटकर आपके ईपीएफ (EPF) खाते में जमा होता है और इस पर सरकार ब्याज देती है।",
        "kn": "ಉದ್ಯೋಗಿ ಪಿಎಫ್ (12%): ಇದು ನಿಮ್ಮ ಸಂಬಳದಿಂದ ಕಡಿತವಾಗಿ ನಿಮ್ಮ ಇಪಿಎಫ್ ಖಾತೆಗೆ ಜಮೆಯಾಗಲಿದ್ದು, ಸರಕಾರ ಬಡ್ಡಿ ನೀಡುತ್ತದೆ.",
        "ta": "ஊழியர் பிஎஃப் (12%): உங்கள் சம்பளத்தில் பிடித்தம் செய்யப்பட்டு உங்கள் இபிஎஃப் கணக்கில் சேமிக்கப்படுகிறது; அரசு வட்டி வழங்குகிறது.",
        "en": "Employee PF (12%): Deducted from your salary and credited to your EPF account with statutory interest."
    },
    "pf_employer": {
        "hi": "कंपनी का अंशदान (12%): 8.33% ईपीएस पेंशन में (अधिकतम ₹1,250) और 3.67% आपके ईपीएफ खाते में जमा होता है।",
        "kn": "ಕಂಪನಿಯ ಪಾಲು (12%): 8.33% ಇಪಿಎಸ್ ಪಿಂಚಣಿಗೆ (ಗರಿಷ್ಠ ₹1,250) ಮತ್ತು 3.67% ನಿಮ್ಮ ಇಪಿಎಫ್ ಖಾತೆಗೆ ಜಮೆಯಾಗುತ್ತದೆ.",
        "ta": "நிறுவனத்தின் பங்கு (12%): 8.33% இபிஎஸ் ஓய்வூதியத்திற்கும் (அதிகபட்சம் ₹1,250), 3.67% இபிஎஃப் கணக்கிற்கும் செல்கிறது.",
        "en": "Employer PF Contribution (12%): Split into 8.33% EPS pension (capped at Rs 1,250) and 3.67% EPF balance."
    },
    "esic_employee": {
        "hi": "ईएसआईसी कटौती (0.75%): यह आपको और आपके परिवार को ईएसआईसी डिस्पेंसरी और अस्पताल में मुफ्त चिकित्सा सुविधा प्रदान करता है।",
        "kn": "ಇಎಸ್ಐಸಿ ಕಡಿತ (0.75%): ಇದು ನಿಮಗೆ ಮತ್ತು ನಿಮ್ಮ ಕುಟುಂಬಕ್ಕೆ ಇಎಸ್ಐಸಿ ಚಿಕಿತ್ಸಾಲಯ ಮತ್ತು ಆಸ್ಪತ್ರೆಗಳಲ್ಲಿ ಉಚಿತ ವೈದ್ಯಕೀಯ ಸೇವೆ ನೀಡುತ್ತದೆ.",
        "ta": "இஎஸ்ஐசி பிடித்தம் (0.75%): உங்களுக்கும் உங்கள் குடும்பத்திற்கும் இஎஸ்ஐ மருத்துவமனைகளில் இலவச சிகிச்சை வழங்குகிறது.",
        "en": "Employee ESIC (0.75%): Provides free outpatient and hospital medical care for you and your dependents."
    },
    "esic_employer": {
        "hi": "कंपनी का ईएसआईसी अंशदान (3.25%): यह पूरी तरह कंपनी द्वारा चिकित्सा और मातृत्व निधि में दिया जाता है।",
        "kn": "ಕಂಪನಿಯ ಇಎಸ್ಐಸಿ ಪಾಲು (3.25%): ಕಂಪನಿಯು ವೈದ್ಯಕೀಯ ಮತ್ತು ಹೆರಿಗೆ ನಿಧಿಗೆ ಈ ಮೊತ್ತವನ್ನು ಭರಿಸುತ್ತದೆ.",
        "ta": "நிறுவனத்தின் இஎஸ்ஐ பங்கு (3.25%): மருத்துவ மற்றும் மகப்பேறு நிதிக்காக நிறுவனத்தால் முழுமையாக செலுத்தப்படுகிறது.",
        "en": "Employer ESIC share (3.25%): Paid by employer towards medical and social security benefit funds."
    }
}


def check_passbook_due_date(wage_month_str: Optional[str], as_of_date_str: Optional[str] = None) -> Tuple[bool, date, date]:
    """
    Checks whether the EPFO remittance due date (15th of following month + N grace days) has passed.
    Returns: (has_due_date_passed, due_date, grace_cutoff_date)
    """
    due_day = EPF_RULES.get("remittance_due_day", 15)
    grace_days = EPF_RULES.get("remittance_grace_days", 3)
    
    # Parse evaluation date
    if as_of_date_str:
        try:
            eval_date = date.fromisoformat(as_of_date_str)
        except Exception:
            eval_date = date.today()
    else:
        eval_date = date.today()
        
    # Determine wage month
    if wage_month_str:
        try:
            parts = wage_month_str.strip().split("-")
            year, month = int(parts[0]), int(parts[1])
        except Exception:
            year = eval_date.year if eval_date.month > 1 else eval_date.year - 1
            month = eval_date.month - 1 if eval_date.month > 1 else 12
    else:
        year = eval_date.year if eval_date.month > 1 else eval_date.year - 1
        month = eval_date.month - 1 if eval_date.month > 1 else 12
        
    next_month = (month % 12) + 1
    next_year = year + (1 if month == 12 else 0)
    due_date = date(next_year, next_month, due_day)
    cutoff_date = due_date + timedelta(days=grace_days)
    
    has_passed = eval_date > cutoff_date
    return has_passed, due_date, cutoff_date


def analyze_payslip(data: PayslipInput) -> PayslipAnalysisResult:
    """Performs deterministic statutory checks reading rules_config.py parameters."""
    lang = data.language if data.language in ("hi", "kn", "ta", "en") else "kn"
    
    # 1. Base Wage Computations
    pf_wage = data.basic_wage + data.dearness_allowance + data.retaining_allowance
    epf_rate = EPF_RULES["employee_contribution_rate"]  # 0.12
    statutory_pf_ceiling = EPF_RULES["statutory_wage_ceiling_monthly"]  # 15000.0
    
    # Both actual 12% and ceiling-capped 12% can be legitimate under EPFO rules
    expected_pf_actual = round(pf_wage * epf_rate, 2)
    expected_pf_ceiling = round(min(pf_wage, statutory_pf_ceiling) * epf_rate, 2)
    
    # ESIC computation
    esic_rate = ESIC_RULES["employee_contribution_rate"]  # 0.0075
    esic_ceiling = ESIC_RULES["statutory_wage_ceiling_disability_monthly"] if data.is_disability else ESIC_RULES["statutory_wage_ceiling_monthly"]  # 21000.0 / 25000.0
    expected_esic_full = round(data.gross_salary * esic_rate, 2)
    expected_esic = expected_esic_full if (data.gross_salary <= esic_ceiling or data.was_covered_at_start_of_period) else 0.0
    
    # Total deductions and take-home pay
    esic_ded = data.employee_esic_deducted if data.employee_esic_deducted is not None else 0.0
    total_deductions = round(data.employee_pf_deducted + esic_ded, 2)
    net_take_home = max(0.0, round(data.gross_salary - total_deductions, 2))
    take_home_pay = net_take_home

    # Employer contributions
    emp_pf = float(data.employer_pf_contribution) if data.employer_pf_contribution is not None else 0.0
    emp_esic = float(data.employer_esic_contribution) if data.employer_esic_contribution is not None else 0.0
    employer_contributions = round(emp_pf + emp_esic, 2)
    
    anomalies: List[AnomalyItem] = []
    informational_notes: List[InformationalNote] = []
    
    # ==============================================================================
    # ANOMALY CHECK 1: PF Rate Check (Actual Basic vs Statutory Ceiling)
    # ==============================================================================
    actual_diff = abs(data.employee_pf_deducted - expected_pf_actual)
    ceiling_diff = abs(data.employee_pf_deducted - expected_pf_ceiling)
    
    if actual_diff > 2.0 and ceiling_diff > 2.0:
        anomalies.append(AnomalyItem(
            code="ANOMALY_PF_RATE_MISMATCH",
            severity="Medium",
            title="PF Deduction Calculation Discrepancy",
            message=(
                f"Possible issue, please confirm with HR / EPFO passbook. Payslip shows Rs {data.employee_pf_deducted:.2f} deducted for PF, "
                f"which does not match standard 12% of PF wage Rs {expected_pf_actual:.2f} (nor the statutory Rs 15,000 wage ceiling deduction of Rs {expected_pf_ceiling:.2f})."
            ),
            message_indic=(
                f"ವೇತನ ಚೀಟಿಯಲ್ಲಿ ಪಿಎಫ್ ಕಡಿತ ₹{data.employee_pf_deducted:.2f} ಎಂದು ತೋರಿಸಲಾಗಿದೆ. ಆದರೆ 12% ನಿಯಮದ ಪ್ರಕಾರ ₹{expected_pf_actual:.2f} "
                f"(ಅಥವಾ ₹15,000 ಸೀಲಿಂಗ್ ಕಡಿತ ₹{expected_pf_ceiling:.2f}) ಆಗಿರಬೇಕು. ಇದು ಸಂಭವನೀಯ ವ್ಯತ್ಯಾಸವಾಗಿದ್ದು, ದಯವಿಟ್ಟು ಎಚ್‌ಆರ್ ಅಥವಾ ಇಪಿಎಫ್ಒ ಪಾಸ್‌ಬುಕ್ ಮೂಲಕ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ."
                if lang == "kn" else
                f"वेतन पर्ची में पीएफ कटौती ₹{data.employee_pf_deducted:.2f} दिखाई गई है, जबकि 12% के अनुसार यह ₹{expected_pf_actual:.2f} "
                f"(या ₹15,000 की वैधानिक सीमा पर ₹{expected_pf_ceiling:.2f}) होनी चाहिए। कृपया एचआर या ईपीएफओ पासबुक से पुष्टि करें।"
                if lang == "hi" else
                f"சம்பளச் சீட்டில் பிஎஃப் பிடித்தம் ₹{data.employee_pf_deducted:.2f} என உள்ளது. ஆனால் 12% கணக்கீட்டின்படி ₹{expected_pf_actual:.2f} "
                f"(அல்லது ₹15,000 உச்சவரம்புப் பிடித்தம் ₹{expected_pf_ceiling:.2f}) இருக்க வேண்டும். இது சாத்தியமான முரண்பாடாகும்; HR அல்லது EPFO பாஸ்புக் மூலம் சரிபார்க்கவும்."
                if lang == "ta" else
                f"Payslip shows PF deduction of Rs {data.employee_pf_deducted:.2f}. Expected 12% is Rs {expected_pf_actual:.2f} or Rs {expected_pf_ceiling:.2f}."
            ),
            rule_citation=STATUTORY_CITATIONS["epf_deduction_rule"]["citation"],
            expected_value=expected_pf_actual,
            actual_value=data.employee_pf_deducted,
            recommendation="Request a written clarification from company HR payroll regarding the wage components included in PF calculation."
        ))

    # ==============================================================================
    # ANOMALY CHECK 2: Key Scenario (Lakshmi) — Passbook Credit vs Remittance Due Date
    # ==============================================================================
    if data.passbook_deposit_credit is not None:
        has_due_date_passed, due_date, cutoff_date = check_passbook_due_date(data.wage_month, data.as_of_date)
        cutoff_str = cutoff_date.strftime("%d %B %Y")
        due_str = due_date.strftime("%d %B %Y")
        
        if data.passbook_deposit_credit == 0.0 or data.passbook_deposit_credit < data.employee_pf_deducted - 2.0:
            if not has_due_date_passed:
                # Due date + N grace days has NOT passed yet!
                # Do NOT flag as an anomaly. Emit an informational note.
                informational_notes.append(InformationalNote(
                    code="INFO_PASSBOOK_PENDING_REMITTANCE",
                    title="PF Deposit Grace Period Active (Pending Remittance)",
                    message=(
                        f"Your PF deposit for this wage month may not have posted yet. Under statutory rules, "
                        f"employers have until {due_str} (15th of the following month) plus {EPF_RULES.get('remittance_grace_days', 3)} days banking clearance "
                        f"(until {cutoff_str}) to remit contributions. Please check your EPFO passbook or UMANG app again after {cutoff_str}."
                    ),
                    message_indic=(
                        f"ಈ ತಿಂಗಳ ಪಿಎಫ್ ಜಮೆ ಇನ್ನು ಪಾಸ್‌ಬುಕ್‌ನಲ್ಲಿ ಬಂದಿಲ್ಲದಿರಬಹುದು. ಶಾಸನಬದ್ಧ ನಿಯಮಗಳ ಪ್ರಕಾರ, ಕಂಪನಿಗೆ ಮುಂದಿನ ತಿಂಗಳ 15 ರವರೆಗೆ "
                        f"(ಮತ್ತು 3 ದಿನಗಳ ಬ್ಯಾಂಕಿಂಗ್ ಕ್ಲಿಯರೆನ್ಸ್ — {cutoff_str} ವರೆಗೆ) ಸಮಯವಿರುತ್ತದೆ. ದಯವಿಟ್ಟು {cutoff_str} ರ ನಂತರ ಪಾಸ್‌ಬುಕ್ ಮತ್ತೆ ಪರಿಶೀಲಿಸಿ."
                        if lang == "kn" else
                        f"इस वेतन माह का पीएफ अंशदान अभी पासबुक में दर्ज नहीं हुआ हो सकता है। ईपीएफओ नियमों के अनुसार नियोक्ता के पास अगले महीने की 15 तारीख "
                        f"(तथा 3 दिन का बैंक क्लीयरेंस — {cutoff_str} तक) का समय होता है। कृपया {cutoff_str} के बाद पासबुक पुनः जांचें।"
                        if lang == "hi" else
                        f"இந்த மாத பிஎஃப் வரவு இன்னும் பாஸ்புக்கில் சேராமல் இருக்கலாம். விதிப்படி அடுத்த மாத 15-ஆம் தேதி வரை "
                        f"(மற்றும் 3 நாள் வங்கி அனுமதி — {cutoff_str} வரை) கால அவகாசம் உள்ளது. தயவுசெய்து {cutoff_str} அன்று மீண்டும் சரிபார்க்கவும்."
                        if lang == "ta" else
                        f"Deposit may not have posted yet. Statutory due date with grace is {cutoff_str}. Check passbook after {cutoff_str}."
                    ),
                    rule_citation=STATUTORY_CITATIONS["epf_remittance_rule"]["citation"],
                    recommendation=f"Check your EPFO passbook or send missed call to 9966044425 after {cutoff_str}."
                ))
            else:
                # Remittance cutoff HAS passed!
                if data.passbook_deposit_credit == 0.0:
                    anomalies.append(AnomalyItem(
                        code="ANOMALY_PASSBOOK_MISSING_CREDIT",
                        severity="High",
                        title="PF Passbook Credit Missing (Uncredited Deposit)",
                        message=(
                            f"Possible issue, please confirm with HR / EPFO passbook. Payslip shows Rs {data.employee_pf_deducted:.2f} deducted from salary, "
                            f"but no deposit was recorded in the EPFO passbook after the due date plus grace period ({cutoff_str}) (due date is the 15th)."
                        ),
                        message_indic=(
                            f"ಸಂಭವನೀಯ ವ್ಯತ್ಯಾಸ: ವೇತನ ಚೀಟಿಯಲ್ಲಿ ₹{data.employee_pf_deducted:.2f} ಪಿಎಫ್ ಕಡಿತವಾಗಿದೆ ಎಂದು ತೋರಿಸಲಾಗಿದೆ, ಆದರೆ ಜಮೆ ಅಂತಿಮ ದಿನಾಂಕ ಮತ್ತು ಗ್ರೇಸ್ ಅವಧಿ ({cutoff_str}) "
                            f"(ಅಂತಿಮ ದಿನಾಂಕ 15 ನೇ ತಾರೀಕು) ಮೀರಿದ ನಂತರವೂ ಇಪಿಎಫ್ಒ ಪಾಸ್‌ಬುಕ್‌ನಲ್ಲಿ ಯಾವುದೇ ಹಣ ಜಮೆಯಾಗಿಲ್ಲ (₹0). ದಯವಿಟ್ಟು ಎಚ್‌ಆರ್ ಅಥವಾ ಗುತ್ತಿಗೆದಾರರೊಂದಿಗೆ ದೃಢೀಕರಿಸಿ."
                            if lang == "kn" else
                            f"संभावित विसंगति: वेतन पर्ची में ₹{data.employee_pf_deducted:.2f} पीएफ काटा गया है, लेकिन देय तिथि और अनुग्रह अवधि ({cutoff_str}) "
                            f"(देय तिथि 15 तारीख है) बीतने के बाद भी ईपीएफओ पासबुक में कोई जमा नहीं दिख रहा है (₹0)। कृपया एचआर से पुष्टि करें।"
                            if lang == "hi" else
                            f"சாத்தியமான முரண்பாடு: சம்பளச் சீட்டில் ₹{data.employee_pf_deducted:.2f} பிஎஃப் பிடித்தம் செய்யப்பட்டுள்ளது, ஆனால் கடைசித் தேதி மற்றும் சலுகைக் காலம் ({cutoff_str}) "
                            f"(கடைசித் தேதி 15 ஆம் தேதி) முடிந்த பிறகும் பாஸ்புக்கில் தொகை வரவு வைக்கப்படவில்லை (₹0). தயவுசெய்து HR-ஐ அணுகவும்."
                            if lang == "ta" else
                            f"Payslip shows Rs {data.employee_pf_deducted:.2f} deducted, but passbook shows Rs 0.0 after the due date plus grace period ({cutoff_str}) (due date is the 15th)."
                        ),
                        rule_citation=STATUTORY_CITATIONS["epf_remittance_rule"]["citation"],
                        expected_value=data.employee_pf_deducted,
                        actual_value=data.passbook_deposit_credit,
                        recommendation="Raise an internal HR inquiry with payslip attachment, and verify through the EPFO Member Passbook portal."
                    ))
                else:
                    anomalies.append(AnomalyItem(
                        code="ANOMALY_PASSBOOK_SHORT_CREDIT",
                        severity="High",
                        title="PF Passbook Deposit Less Than Salary Deduction",
                        message=(
                            f"Possible issue, please confirm with HR / EPFO passbook. Payslip shows Rs {data.employee_pf_deducted:.2f} deducted, "
                            f"but only Rs {data.passbook_deposit_credit:.2f} was deposited to your EPFO passbook after the due date plus grace period ({cutoff_str}) (due date is the 15th)."
                        ),
                        message_indic=(
                            f"ಸಂಭವನೀಯ ವ್ಯತ್ಯಾಸ: ವೇತನ ಚೀಟಿಯಲ್ಲಿ ₹{data.employee_pf_deducted:.2f} ಕಡಿತವಾಗಿದೆ, ಆದರೆ ಪಾಸ್‌ಬುಕ್‌ನಲ್ಲಿ ಕೇವಲ ₹{data.passbook_deposit_credit:.2f} ಮಾತ್ರ ಜಮೆಯಾಗಿದೆ. "
                            f"ದಯವಿಟ್ಟು ಎಚ್‌ಆರ್ ಜೊತೆ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ."
                            if lang == "kn" else
                            f"संभावित विसंगति: वेतन पर्ची में ₹{data.employee_pf_deducted:.2f} कटौती है, लेकिन पासबुक में केवल ₹{data.passbook_deposit_credit:.2f} जमा हुआ है। "
                            f"कृपया एचआर से इस अंतर की पुष्टि करें।"
                            if lang == "hi" else
                            f"சாத்தியமான முரண்பாடு: சம்பளச் சீட்டில் ₹{data.employee_pf_deducted:.2f} பிடித்தம் உள்ளது, ஆனால் பாஸ்புக்கில் ₹{data.passbook_deposit_credit:.2f} மட்டுமே வந்துள்ளது. "
                            f"தயவுசெய்து HR-ஐ அணுகவும்."
                            if lang == "ta" else
                            f"Passbook credit Rs {data.passbook_deposit_credit:.2f} is lower than payslip deduction Rs {data.employee_pf_deducted:.2f} after the due date plus grace period ({cutoff_str}) (due date is the 15th)."
                        ),
                        rule_citation=STATUTORY_CITATIONS["epf_remittance_rule"]["citation"],
                        expected_value=data.employee_pf_deducted,
                        actual_value=data.passbook_deposit_credit,
                        recommendation="Request member ledger reconciliation from payroll department."
                    ))

    # ==============================================================================
    # ANOMALY CHECK 3: ESIC Applicability & Contribution Period Rule
    # ==============================================================================
    if data.gross_salary > esic_ceiling:
        if data.was_covered_at_start_of_period:
            # Under ESI Regulation 4 & Section 2(9) proviso: worker stays covered until 6-month contribution period ends
            if data.employee_esic_deducted is not None and abs(data.employee_esic_deducted - expected_esic_full) <= 2.0:
                informational_notes.append(InformationalNote(
                    code="INFO_ESIC_CONTRIBUTION_PERIOD_COVERED",
                    title="ESIC Continuous Coverage Active (Contribution Period Rule)",
                    message=(
                        f"Monthly gross wage of Rs {data.gross_salary:.2f} exceeds the Rs {esic_ceiling:.2f} ceiling, "
                        f"but ESIC coverage legitimately continues until the end of the current 6-month contribution period (April-Sept or Oct-March). "
                        f"The 0.75% deduction (Rs {data.employee_esic_deducted:.2f}) is compliant."
                    ),
                    message_indic=(
                        f"ನಿಮ್ಮ ಒಟ್ಟು ಸಂಬಳ ₹{data.gross_salary:.2f} ಆಗಿದ್ದು ಮಿತಿ ₹{esic_ceiling:.2f} ಮೀರಿದ್ದರೂ, 6-ತಿಂಗಳ ಕೊಡುಗೆ ಅವಧಿಯ ನಿಯಮದ ಪ್ರಕಾರ "
                        f"ಅವಧಿ ಮುಗಿಯುವವರೆಗೆ ಇಎಸ್ಐಸಿ ಸೌಲಭ್ಯ ಮತ್ತು ಕಡಿತ ಮುಂದುವರಿಯುತ್ತದೆ. ಈ ಕಡಿತ ಶಾಸನಬದ್ಧವಾಗಿದೆ."
                        if lang == "kn" else
                        f"सकल वेतन ₹{data.gross_salary:.2f} ईएसआईसी सीमा से अधिक है, किंतु 6-माह योगदान अवधि नियम के तहत अवधि समाप्त होने तक कटौती वैध है।"
                        if lang == "hi" else
                        f"மொத்த சம்பளம் ₹{data.gross_salary:.2f} உச்சவரம்பை தாண்டினாலும், 6 மாத பங்களிப்பு கால விதிப்படி இந்த பிடித்தம் சட்டப்பூர்வமானது."
                        if lang == "ta" else
                        f"Gross wage Rs {data.gross_salary:.2f} exceeds ceiling, but ESIC coverage continues until end of contribution period."
                    ),
                    rule_citation=STATUTORY_CITATIONS["esic_contribution_period_rule"]["citation"],
                    recommendation="No action needed. ESIC benefits remain active until the end of the current contribution period."
                ))
            elif data.employee_esic_deducted is not None and data.employee_esic_deducted > 0:
                anomalies.append(AnomalyItem(
                    code="ANOMALY_ESIC_RATE_MISMATCH",
                    severity="Medium",
                    title="ESIC Deduction Rate Discrepancy under Extended Coverage",
                    message=f"Possible issue, please confirm with HR / EPFO passbook. Expected 0.75% is Rs {expected_esic_full:.2f}, but Rs {data.employee_esic_deducted:.2f} was deducted.",
                    message_indic="ಇಎಸ್ಐಸಿ ಕಡಿತ ದರದಲ್ಲಿ ವ್ಯತ್ಯಾಸ ಕಂಡುಬಂದಿದೆ.",
                    rule_citation=STATUTORY_CITATIONS["esic_rate_rule"]["citation"],
                    expected_value=expected_esic_full,
                    actual_value=data.employee_esic_deducted,
                    recommendation="Confirm insurable wage calculation with payroll department."
                ))
        else:
            if data.employee_esic_deducted and data.employee_esic_deducted > 0:
                anomalies.append(AnomalyItem(
                    code="ANOMALY_ESIC_OVER_CEILING",
                    severity="Low",
                    title="ESIC Deducted on Wage Above Ceiling",
                    message=(
                        f"Possible issue, please confirm with HR / EPFO passbook. Monthly gross wage of Rs {data.gross_salary:.2f} exceeds "
                        f"statutory ESIC ceiling (Rs {esic_ceiling:.2f}). ESIC is not applicable unless worker was covered at start of contribution period."
                    ),
                    message_indic=(
                        f"ನಿಮ್ಮ ಒಟ್ಟು ಸಂಬಳ ₹{data.gross_salary:.2f} ಆಗಿದ್ದು, ಇಎಸ್ಐಸಿ ಮಿತಿ ₹{esic_ceiling:.2f} ಮೀರಿದೆ. ಕೊಡುಗೆ ಅವಧಿಯ ಮುಂದುವರಿಕೆ ಇಲ್ಲದಿದ್ದರೆ ಇಎಸ್ಐಸಿ ಕಡಿತ ಅನ್ವಯಿಸುವುದಿಲ್ಲ."
                        if lang == "kn" else
                        f"सकल वेतन ₹{data.gross_salary:.2f} ईएसआईसी सीमा (₹{esic_ceiling:.2f}) से अधिक है। यदि योगदान अवधि की निरंतरता नहीं है तो ईएसआईसी लागू नहीं होता।"
                        if lang == "hi" else
                        f"மொத்த சம்பளம் ₹{data.gross_salary:.2f} வரம்பை விட அதிகம். பங்களிப்பு கால தொடர்ச்சி இல்லையெனில் இஎஸ்ஐ பிடித்தம் பொருந்தாது."
                        if lang == "ta" else
                        f"Gross wage Rs {data.gross_salary:.2f} exceeds ESIC ceiling Rs {esic_ceiling:.2f}."
                    ),
                    rule_citation=STATUTORY_CITATIONS["esic_ceiling_rule"]["citation"],
                    expected_value=0.0,
                    actual_value=data.employee_esic_deducted,
                    recommendation="Verify whether you entered the current 6-month contribution period with wages below Rs 21,000."
                ))
    elif data.gross_salary <= esic_ceiling and data.employee_esic_deducted is not None:
        if abs(data.employee_esic_deducted - expected_esic) > 2.0:
            anomalies.append(AnomalyItem(
                code="ANOMALY_ESIC_RATE_MISMATCH",
                severity="Medium",
                title="ESIC Deduction Rate Discrepancy",
                message=(
                    f"Possible issue, please confirm with HR / EPFO passbook. Payslip shows Rs {data.employee_esic_deducted:.2f} deducted for ESIC, "
                    f"whereas statutory 0.75% of gross wage Rs {data.gross_salary:.2f} is Rs {expected_esic:.2f}."
                ),
                message_indic=(
                    f"ವೇತನ ಚೀಟಿಯಲ್ಲಿ ಇಎಸ್ಐಸಿ ಕಡಿತ ₹{data.employee_esic_deducted:.2f} ಇದೆ. ಆದರೆ ಒಟ್ಟು ಸಂಬಳದ 0.75% ನಿಯಮದಂತೆ ₹{expected_esic:.2f} ಆಗಿರಬೇಕು."
                    if lang == "kn" else
                    f"वेतन पर्ची में ईएसआईसी कटौती ₹{data.employee_esic_deducted:.2f} है, जबकि सकल वेतन का 0.75% ₹{expected_esic:.2f} बनता है।"
                    if lang == "hi" else
                    f"சம்பளச் சீட்டில் இஎஸ்ஐசி பிடித்தம் ₹{data.employee_esic_deducted:.2f} உள்ளது, ஆனால் 0.75% படி ₹{expected_esic:.2f} இருக்க வேண்டும்."
                    if lang == "ta" else
                    f"Expected 0.75% ESIC is Rs {expected_esic:.2f}, payslip has Rs {data.employee_esic_deducted:.2f}."
                ),
                rule_citation=STATUTORY_CITATIONS["esic_rate_rule"]["citation"],
                expected_value=expected_esic,
                actual_value=data.employee_esic_deducted,
                recommendation="Check if overtime or travel allowances were excluded from the ESIC insurable wage calculation."
            ))

    # ==============================================================================
    # ANOMALY CHECK 4: Employer Contribution Matching Check
    # ==============================================================================
    if data.employer_pf_contribution is not None:
        if data.employer_pf_contribution == 0.0:
            anomalies.append(AnomalyItem(
                code="ANOMALY_EMPLOYER_PF_ZERO",
                severity="High",
                title="Employer PF Contribution Missing (Rs 0)",
                message=(
                    f"Possible issue, please confirm with HR / EPFO passbook. Employer PF contribution is shown as Rs 0.0. "
                    f"Statutory rules obligate the employer to match the employee contribution (up to ceiling)."
                ),
                message_indic=(
                    f"ಕಂಪನಿಯ ಪಿಎಫ್ ಪಾಲು ₹0 ಎಂದು ತೋರಿಸಲಾಗಿದೆ. ಶಾಸನಬದ್ಧ ನಿಯಮಗಳ ಪ್ರಕಾರ ಮಾಲೀಕರು ಉದ್ಯೋಗಿಯಷ್ಟೇ ಪಾಲನ್ನು (12%) ಭರಿಸುವುದು ಕಡ್ಡಾಯವಾಗಿದೆ."
                    if lang == "kn" else
                    f"कंपनी का पीएफ अंशदान ₹0 दिखाया गया है। नियमों के अनुसार नियोक्ता को भी बराबर (12%) अंशदान देना अनिवार्य है।"
                    if lang == "hi" else
                    f"நிறுவனத்தின் பிஎஃப் பங்கு ₹0 என உள்ளது. சட்டப்படி நிறுவனமும் இணையான (12%) பங்கை செலுத்த வேண்டும்."
                    if lang == "ta" else
                    f"Employer PF share is Rs 0.0."
                ),
                rule_citation=STATUTORY_CITATIONS["epf_deduction_rule"]["citation"],
                expected_value=min(data.employee_pf_deducted, 1800.0),
                actual_value=0.0,
                recommendation="Confirm whether the employer share is remitted under a separate head or omitted on the payslip."
            ))
        elif data.employer_pf_contribution < min(data.employee_pf_deducted, 1800.0) - 2.0:
            anomalies.append(AnomalyItem(
                code="ANOMALY_EMPLOYER_PF_SHORT",
                severity="Medium",
                title="Employer PF Contribution Lower Than Statutory Expectation",
                message=(
                    f"Possible issue, please confirm with HR / EPFO passbook. Employer contribution of Rs {data.employer_pf_contribution:.2f} "
                    f"is lower than the expected statutory match Rs {min(data.employee_pf_deducted, 1800.0):.2f}."
                ),
                message_indic=(
                    f"ಕಂಪನಿಯ ಪಿಎಫ್ ಕೊಡುಗೆ ₹{data.employer_pf_contribution:.2f} ನಿರೀಕ್ಷಿತ ಶಾಸನಬದ್ಧ ಮೊತ್ತ ₹{min(data.employee_pf_deducted, 1800.0):.2f} ಗಿಂತ ಕಡಿಮೆಯಾಗಿದೆ."
                    if lang == "kn" else
                    f"कंपनी का पीएफ अंशदान ₹{data.employer_pf_contribution:.2f} अपेक्षित वैधानिक राशि ₹{min(data.employee_pf_deducted, 1800.0):.2f} से कम है।"
                    if lang == "hi" else
                    f"நிறுவனத்தின் பிஎஃப் பங்களிப்பு ₹{data.employer_pf_contribution:.2f} எதிர்பார்க்கப்படும் தொகையான ₹{min(data.employee_pf_deducted, 1800.0):.2f} ஐ விட குறைவாக உள்ளது."
                    if lang == "ta" else
                    f"Employer contribution Rs {data.employer_pf_contribution:.2f} is lower than expected match."
                ),
                rule_citation=STATUTORY_CITATIONS["epf_deduction_rule"]["citation"],
                expected_value=min(data.employee_pf_deducted, 1800.0),
                actual_value=data.employer_pf_contribution,
                recommendation="Check the EPS / EPF breakdown in the official EPFO passbook."
            ))

    # ==============================================================================
    # CHECK 5: Month-to-Month Variance (INFORMATIONAL NOTE, NOT AN ANOMALY)
    # ==============================================================================
    if data.previous_month_pf_deducted is not None and data.previous_month_pf_deducted > 0:
        prev = data.previous_month_pf_deducted
        curr = data.employee_pf_deducted
        diff = abs(curr - prev)
        ratio = diff / prev
        if ratio > 0.15 and diff > 100.0:
            informational_notes.append(InformationalNote(
                code="INFO_MOM_PF_JUMP",
                title="Month-over-Month PF Variance Notice (>15%)",
                message=(
                    f"Informational notice: PF deduction shifted from Rs {prev:.2f} last month to Rs {curr:.2f} this month "
                    f"({ratio * 100:.1f}% change). If basic wage, overtime, or working days changed, this may be legitimate; otherwise please verify with HR."
                ),
                message_indic=(
                    f"ಮಾಹಿತಿ ಸೂಚನೆ: ಹಿಂದಿನ ತಿಂಗಳಿಗಿಂತ ಪಿಎಫ್ ಕಡಿತದಲ್ಲಿ ಗಮನಾರ್ಹ ಬದಲಾವಣೆಯಾಗಿದೆ (ಹಿಂದಿನ ತಿಂಗಳು ₹{prev:.2f}, ಈ ತಿಂಗಳು ₹{curr:.2f}). "
                    f"ಕೆಲಸದ ದಿನಗಳು ಅಥವಾ ಮೂಲವೇತನ ಬದಲಾಗಿದ್ದರೆ ಇದು ಸರಿಯಾಗಿರಬಹುದು; ಇಲ್ಲವಾದಲ್ಲಿ ಎಚ್‌ಆರ್ ಮೂಲಕ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ."
                    if lang == "kn" else
                    f"सूचना: पिछले महीने की तुलना में पीएफ कटौती में 15% से अधिक का अंतर है (पिछला ₹{prev:.2f}, वर्तमान ₹{curr:.2f})। "
                    f"यदि कार्य दिवस या मूल वेतन बदला है तो यह सामान्य हो सकता है; अन्यथा एचआर से पुष्टि करें।"
                    if lang == "hi" else
                    f"தகவல் அறிவிப்பு: கடந்த மாதத்தை விட பிஎஃப் பிடித்தத்தில் 15% க்கும் மேல் மாற்றம் உள்ளது (முந்தைய ₹{prev:.2f}, தற்போதைய ₹{curr:.2f}). "
                    f"வேலை நாட்கள் மாறினால் இது சரியாக இருக்கலாம்; இல்லையெனில் HR-ஐ அணுகவும்."
                    if lang == "ta" else
                    f"PF deduction changed by {ratio * 100:.1f}% month-over-month."
                ),
                rule_citation="EPFO Wage Consistency Guidelines",
                recommendation="Check whether working days or paid leave deductions altered the base wage."
            ))

    # ==============================================================================
    # BUILD BREAKDOWN ITEMS
    # ==============================================================================
    breakdown: List[BreakdownItem] = [
        BreakdownItem(
            name="Basic Wage",
            category="earning",
            amount=data.basic_wage,
            explanation_indic=EXPLANATIONS["basic"].get(lang, EXPLANATIONS["basic"]["en"]),
            explanation_en=EXPLANATIONS["basic"]["en"]
        )
    ]
    if data.dearness_allowance > 0:
        breakdown.append(BreakdownItem(
            name="Dearness Allowance (DA)",
            category="earning",
            amount=data.dearness_allowance,
            explanation_indic=EXPLANATIONS["da"].get(lang, EXPLANATIONS["da"]["en"]),
            explanation_en=EXPLANATIONS["da"]["en"]
        ))
    if data.other_allowances > 0:
        breakdown.append(BreakdownItem(
            name="Other Allowances (HRA/Special)",
            category="earning",
            amount=data.other_allowances,
            explanation_indic=EXPLANATIONS["allowances"].get(lang, EXPLANATIONS["allowances"]["en"]),
            explanation_en=EXPLANATIONS["allowances"]["en"]
        ))
    breakdown.append(BreakdownItem(
        name="Employee PF (12%)",
        category="deduction",
        amount=data.employee_pf_deducted,
        explanation_indic=EXPLANATIONS["pf_employee"].get(lang, EXPLANATIONS["pf_employee"]["en"]),
        explanation_en=EXPLANATIONS["pf_employee"]["en"]
    ))
    if data.employee_esic_deducted is not None and data.employee_esic_deducted > 0:
        breakdown.append(BreakdownItem(
            name="Employee ESIC (0.75%)",
            category="deduction",
            amount=data.employee_esic_deducted,
            explanation_indic=EXPLANATIONS["esic_employee"].get(lang, EXPLANATIONS["esic_employee"]["en"]),
            explanation_en=EXPLANATIONS["esic_employee"]["en"]
        ))
    if data.employer_pf_contribution is not None and data.employer_pf_contribution > 0:
        breakdown.append(BreakdownItem(
            name="Employer PF Share (12%)",
            category="employer_share",
            amount=data.employer_pf_contribution,
            explanation_indic=EXPLANATIONS["pf_employer"].get(lang, EXPLANATIONS["pf_employer"]["en"]),
            explanation_en=EXPLANATIONS["pf_employer"]["en"]
        ))
    if data.employer_esic_contribution is not None and data.employer_esic_contribution > 0:
        breakdown.append(BreakdownItem(
            name="Employer ESIC Share (3.25%)",
            category="employer_share",
            amount=data.employer_esic_contribution,
            explanation_indic=EXPLANATIONS["esic_employer"].get(lang, EXPLANATIONS["esic_employer"]["en"]),
            explanation_en=EXPLANATIONS["esic_employer"]["en"]
        ))

    # ==============================================================================
    # DRAFT HR TICKET (IF ANOMALIES FOUND)
    # ==============================================================================
    ticket_draft: Optional[DraftHRTicket] = None
    if anomalies:
        highest_severity = "High" if any(a.severity == "High" for a in anomalies) else "Medium"
        top_anomaly = next((a for a in anomalies if a.severity == "High"), anomalies[0])
        
        ticket_draft = DraftHRTicket(
            title=f"Payslip vs Passbook Audit: {top_anomaly.title}",
            category="ESIC" if "ESIC" in top_anomaly.code else "PF / EPFO",
            priority=highest_severity,
            language=lang,
            suggested_description=(
                f"Discrepancy identified during worker payslip check:\n"
                f"- Gross Salary: Rs {data.gross_salary:.2f}\n"
                f"- Basic Wage: Rs {data.basic_wage:.2f}\n"
                f"- PF Deducted on Payslip: Rs {data.employee_pf_deducted:.2f}\n"
                f"- EPFO Passbook Credit: {'Rs ' + str(data.passbook_deposit_credit) if data.passbook_deposit_credit is not None else 'Not provided'}\n"
                f"- Identified Flag: {top_anomaly.title} ({top_anomaly.rule_citation})\n"
                f"- Detail: {top_anomaly.message}\n"
                f"Employee seeks verification with official payroll records."
            ),
            requires_consent=True,
            evidence_payload={
                "anomalies": [a.model_dump() if hasattr(a, "model_dump") else a.dict() for a in anomalies],
                "informational_notes": [n.model_dump() if hasattr(n, "model_dump") else n.dict() for n in informational_notes],
                "payslip_inputs": data.model_dump() if hasattr(data, "model_dump") else data.dict(),
                "statutory_rules_version": "EPF_1952_ESIC_1948"
            }
        )

    # Summary message in user language
    if anomalies:
        if lang == "kn":
            summary = f"ವೇತನ ಚೀಟಿ ಪರಿಶೀಲನೆಯಲ್ಲಿ {len(anomalies)} ಸಂಭವನೀಯ ವ್ಯತ್ಯಾಸಗಳು ಕಂಡುಬಂದಿವೆ. ದಯವಿಟ್ಟು ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ ಎಚ್‌ಆರ್ ಜೊತೆ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ."
        elif lang == "hi":
            summary = f"वेतन पर्ची विश्लेषण में {len(anomalies)} संभावित विसंगतियां पाई गई हैं। कृपया एचआर या आधिकारिक पासबुक से पुष्टि करें।"
        elif lang == "ta":
            summary = f"சம்பளச் சீட்டு ஆய்வில் {len(anomalies)} சாத்தியமான முரண்பாடுகள் கண்டறியப்பட்டுள்ளன. தயவுசெய்து HR அல்லது பாஸ்புக் மூலம் சரிபார்க்கவும்."
        else:
            summary = f"Payslip analysis identified {len(anomalies)} potential discrepancies. Please confirm with HR / EPFO passbook."
    else:
        if lang == "kn":
            summary = "ನಿಮ್ಮ ವೇತನ ಚೀಟಿಯ ಪಿಎಫ್ ಮತ್ತು ಇಎಸ್ಐಸಿ ಕಡಿತಗಳು ಶಾಸನಬದ್ಧ ನಿಯಮಗಳ ಪ್ರಕಾರ ಸರಿಯಾಗಿ ಕಂಡುಬಂದಿವೆ."
        elif lang == "hi":
            summary = "आपकी वेतन पर्ची की पीएफ और ईएसआईसी कटौतियां वैधानिक नियमों के अनुरूप सही पाई गई हैं।"
        elif lang == "ta":
            summary = "உங்கள் சம்பளச் சீட்டின் பிஎஃப் மற்றும் இஎஸ்ஐசி பிடித்தங்கள் சட்டப்பூர்வ விதிகளின்படி சரியாக உள்ளன."
        else:
            summary = "Your payslip statutory deductions align with statutory parameters."

    return PayslipAnalysisResult(
        pf_wage=pf_wage,
        gross_salary=data.gross_salary,
        net_take_home=net_take_home,
        take_home_pay=take_home_pay,
        total_deductions=total_deductions,
        employer_contributions=employer_contributions,
        expected_pf_actual_wage=expected_pf_actual,
        expected_pf_statutory_ceiling=expected_pf_ceiling,
        expected_esic=expected_esic,
        anomalies=anomalies,
        has_anomalies=bool(anomalies),
        informational_notes=informational_notes,
        breakdown=breakdown,
        summary_message=summary,
        ticket_draft=ticket_draft,
        language=lang
    )


# ==============================================================================
# OCR / TEXT EXTRACTION WITH GRACEFUL FALLBACK (IN-MEMORY ONLY)
# ==============================================================================

def extract_payslip_fields_from_text(text: str) -> Dict[str, Optional[float]]:
    """Extracts common payslip numbers using regex heuristics; does NOT store files."""
    extracted: Dict[str, Optional[float]] = {
        "basic_wage": None,
        "gross_salary": None,
        "employee_pf_deducted": None,
        "employee_esic_deducted": None,
        "employer_pf_contribution": None
    }
    
    basic_pat = re.search(r"(?i)\b(basic|basic pay|basic wage|मूल वेतन|ಮೂಲ ವೇತನ|அடிப்படை)[:\s\-₹Rs\.]*([0-9,]+(\.[0-9]{1,2})?)", text)
    if basic_pat:
        try: extracted["basic_wage"] = float(basic_pat.group(2).replace(",", ""))
        except Exception: pass
        
    gross_pat = re.search(r"(?i)\b(gross|gross earnings|gross salary|total earnings|सकल वेतन|ಒಟ್ಟು ಸಂಬಳ|மொத்த)[:\s\-₹Rs\.]*([0-9,]+(\.[0-9]{1,2})?)", text)
    if gross_pat:
        try: extracted["gross_salary"] = float(gross_pat.group(2).replace(",", ""))
        except Exception: pass
        
    pf_pat = re.search(r"(?i)\b(provident fund|epf|pf|employee pf|पीएफ|ಪಿಎಫ್|பிஎஃப்)[:\s\-₹Rs\.]*([0-9,]+(\.[0-9]{1,2})?)", text)
    if pf_pat:
        try: extracted["employee_pf_deducted"] = float(pf_pat.group(2).replace(",", ""))
        except Exception: pass
        
    esic_pat = re.search(r"(?i)\b(esic|esi|employee esic|ईएसआईसी|ಇಎಸ್ಐಸಿ|இஎஸ்ஐசி)[:\s\-₹Rs\.]*([0-9,]+(\.[0-9]{1,2})?)", text)
    if esic_pat:
        try: extracted["employee_esic_deducted"] = float(esic_pat.group(2).replace(",", ""))
        except Exception: pass

    return extracted
