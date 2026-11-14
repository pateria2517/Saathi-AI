"""Saathi AI — PF and ESIC Statutory Rules & Wage Thresholds Configuration.

IMPORTANT NOTICE:
Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition).
Statutory rates, wage limits, and employer contribution allocations are subject to gazette notifications
and judicial interpretations (e.g. Supreme Court 2019 ruling on basic wage allowances, and the four Labour
Codes on Social Security and Wages).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


# ==============================================================================
# EMPLOYEES' PROVIDENT FUND (EPFO / EPF / EPS / EDLI)
# ==============================================================================

# Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)
EPF_RULES: Dict[str, Any] = {
    "employee_contribution_rate": 0.12,  # 12% of PF wage (Basic + DA)
    "employer_total_contribution_rate": 0.12,  # 12% total matching contribution
    "employer_eps_share_rate": 0.0833,  # 8.33% directed to Employees' Pension Scheme (EPS)
    "employer_epf_share_rate": 0.0367,  # 3.67% directed to Employees' Provident Fund (EPF)
    "edli_contribution_rate": 0.0050,  # 0.50% Employees' Deposit Linked Insurance
    "epf_admin_charges_rate": 0.0050,  # 0.50% administrative charges (minimum Rs 500)
    "edli_admin_charges_rate": 0.0,  # Waived since 2017
    
    # Statutory PF wage ceiling (Rs 15,000 per month since 1 Sept 2014)
    # Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)
    "statutory_wage_ceiling_monthly": 15000.0,
    
    # Maximum statutory employee deduction when capped at ceiling: 12% of 15,000 = Rs 1,800
    "max_statutory_employee_deduction": 1800.0,
    
    # Maximum statutory employer EPS share when capped at ceiling: 8.33% of 15,000 = Rs 1,250 (max Rs 1,250/mo)
    "max_statutory_eps_share": 1250.0,
    
    # Statutory remittance due date: 15th of the month following the wage month
    # Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)
    "remittance_due_day": 15,
    # Number of grace days (N) for banking and electronic challan return (ECR) clearance before flagging missing deposit
    # Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)
    "remittance_grace_days": 3,
    
    # Voluntary Provident Fund (VPF) allows employee deduction up to 100% of Basic + DA,
    # but employer is not obligated to match beyond statutory 12%.
    "vpf_allowed": True,
    
    # Threshold for establishment coverage (20 or more employees)
    "establishment_coverage_threshold": 20,
    
    # Note on wage definition:
    "wage_definition_note": (
        "PF wages traditionally comprise Basic Pay + Dearness Allowance (DA) + Retaining Allowance. "
        "Under the Supreme Court 2019 ruling (Surya Roshni), universally paid special allowances form part of PF wages. "
        "Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition, capping exclusions at 50%)."
    ),
}

# Statutory citations catalog for user-facing audit citations
# Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)
STATUTORY_CITATIONS: Dict[str, Dict[str, str]] = {
    "epf_deduction_rule": {
        "citation": "EPF Act 1952, Section 6",
        "description": "Statutory 12% employee deduction and matching employer contribution",
        "verify_note": "Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)",
    },
    "epf_remittance_rule": {
        "citation": "EPF Scheme 1952, Paragraph 38",
        "description": "Employer must remit EPF contributions within 15 days of the close of the month",
        "verify_note": "Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)",
    },
    "epf_ceiling_rule": {
        "citation": "EPFO Notification G.S.R. 608(E) (w.e.f. 01-Sep-2014)",
        "description": "Statutory monthly PF wage threshold of Rs 15,000",
        "verify_note": "Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)",
    },
    "esic_rate_rule": {
        "citation": "ESI (Central) Rules 1950, Rule 51 (w.e.f. 01-Jul-2019)",
        "description": "Employee 0.75% and employer 3.25% insurable wage contribution",
        "verify_note": "Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)",
    },
    "esic_ceiling_rule": {
        "citation": "ESI (Central) Rules 1950, Rule 50 (w.e.f. 01-Jan-2017)",
        "description": "Statutory monthly gross wage coverage threshold of Rs 21,000",
        "verify_note": "Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)",
    },
    "esic_contribution_period_rule": {
        "citation": "ESI Act 1948, Section 2(9) Proviso & ESI Regulation 4",
        "description": "Employee whose wages exceed ceiling mid-period remains covered until period ends",
        "verify_note": "Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)",
    },
}


# ==============================================================================
# EMPLOYEES' STATE INSURANCE (ESIC / ESI)
# ==============================================================================

# Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)
ESIC_RULES: Dict[str, Any] = {
    "employee_contribution_rate": 0.0075,  # 0.75% of gross insurable wage (reduced from 1.75% in July 2019)
    "employer_contribution_rate": 0.0325,  # 3.25% of gross insurable wage (reduced from 4.75% in July 2019)
    "total_contribution_rate": 0.0400,  # 4.00% combined
    
    # Statutory gross wage threshold for ESIC coverage (Rs 21,000 per month since 1 Jan 2017)
    # For employees with disability (PWD), ceiling is Rs 25,000 per month
    # Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)
    "statutory_wage_ceiling_monthly": 21000.0,
    "statutory_wage_ceiling_disability_monthly": 25000.0,
    
    # Daily wage exemption threshold: employees earning average daily wage up to Rs 176 (updated to Rs 176/day)
    # are exempted from employee contribution, but employer share must still be paid.
    "daily_wage_exemption_limit": 176.0,
    
    # Contribution periods:
    # 1. 1st April to 30th September (Benefit: 1st January to 30th June next year)
    # 2. 1st October to 31st March (Benefit: 1st July to 31st December)
    # Rule: If an employee's wage exceeds Rs 21,000 during a contribution period, they remain covered
    # until the end of that contribution period.
    "contribution_period_rule": (
        "If gross wage exceeds Rs 21,000 after the start of a contribution period, deductions continue "
        "until the end of that 6-month contribution period."
    ),
    
    # Note on insurable wage definition:
    "insurable_wage_note": (
        "ESIC insurable wage includes all cash remuneration paid to an employee, including basic, DA, HRA, "
        "overtime, production incentives, and shift allowance, but excludes travelling allowance or annual bonus. "
        "Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition)."
    ),
}


# ==============================================================================
# OFFICIAL STATUTORY CONTACTS & PORTALS (NO DIRECT EXTERNAL BALANCE API)
# ==============================================================================

EPFO_SERVICES = {
    "official_portal": "https://unifiedportal-mem.epfindia.gov.in/memberinterface/",
    "passbook_portal": "https://passbook.epfindia.gov.in/MemberPassBook/Login",
    "umang_app_url": "https://web.umang.gov.in/",
    "missed_call_number": "011-22901406",  # From Aadhaar-registered mobile
    "sms_shortcode": "7738299899",  # Format: EPFOHO UAN ENG
    "grievance_portal_epfigms": "https://epfigms.gov.in/",
    "balance_api_disclaimer": (
        "EPFO does not provide a public developer API for fetching member passbook balance. "
        "The agent guides members to the official Passbook portal, UMANG app, missed-call service, or SMS service."
    ),
}

ESIC_SERVICES = {
    "official_portal": "https://www.esic.gov.in/",
    "insurance_portal": "https://portal.esic.in/MemberPortal/login.aspx",
    "toll_free_helpline": "1800-11-2526",
    "grievance_portal": "https://pgportal.gov.in/",
}
