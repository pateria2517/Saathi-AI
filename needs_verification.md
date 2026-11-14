# Saathi AI — Statutory Citations Verification Matrix (`needs_verification.md`)
**Version:** 2.1.0  
**Notice:** *Verify against current EPFO/ESIC rules (note: Labour Codes may change the wage definition).*  
**Last Updated:** November 2026  
**Auditor Focus:** University Project (TLM Course) — Legal & Statutory Compliance Grounding

---

## 1. Executive Summary

Saathi AI provides statutory deduction explanations and anomaly audits for blue-collar warehouse and factory workers. To prevent misinformation or unjustified accusations against employers, **no statutory section or rule number is surfaced in user-facing flags unless it is cataloged in `rules_config.py` with an explicit verification notice**.

This document lists every statutory citation used in Saathi AI, its formal legal source, current operational status, and how the upcoming **Four Labour Codes** (specifically the *Code on Wages, 2019* and *Code on Social Security, 2020*) will affect the rule once fully implemented by central and state gazettes.

---

## 2. Master Statutory Citation Catalog

| Citation Key in `rules_config.py` | Official Statutory Reference | Primary Regulatory Text | Current Threshold / Rate | Labour Code Impact (Future) | Verification Status |
|---|---|---|---|---|---|
| `epf_deduction_rule` | **EPF Act 1952, Section 6** | Employees' Provident Funds and Miscellaneous Provisions Act, 1952 | Employee: 12% of Basic + DA. Employer: 12% (3.67% EPF + 8.33% EPS). | Replaced by *Section 16, Code on Social Security 2020*. Central Government may notify 10% rate for certain industries. | **VERIFIED (Active)** |
| `epf_remittance_rule` | **EPF Scheme 1952, Paragraph 38** | Employees' Provident Funds Scheme, 1952 | Remittance due within 15 days of month close (i.e. by 15th of following month). Saathi adds N=3 grace days before flagging missing passbook deposit. | Due date mechanism preserved under Social Security Code electronic challan-cum-return (ECR) regulations. | **VERIFIED (Active)** |
| `epf_ceiling_rule` | **EPFO Notification G.S.R. 608(E)** | Ministry of Labour & Employment Gazette (22-Aug-2014, w.e.f. 01-Sep-2014) | Statutory wage ceiling: ₹15,000/month. Capped deduction: ₹1,800/mo. | Proposed revision to ₹21,000 or ₹25,000 under draft rules; pending final gazette notification. | **VERIFIED (Active)** |
| `esic_rate_rule` | **ESI (Central) Rules 1950, Rule 51** | Gazette Notification S.O. 2016(E) (w.e.f. 01-Jul-2019) | Employee: 0.75% of gross insurable wage. Employer: 3.25% of gross insurable wage. | Rates carry over under *Code on Social Security 2020*, Chapter IV. | **VERIFIED (Active)** |
| `esic_ceiling_rule` | **ESI (Central) Rules 1950, Rule 50** | Gazette Notification S.O. 4212(E) (w.e.f. 01-Jan-2017) | Statutory gross wage coverage ceiling: ₹21,000/month (₹25,000 for Persons with Disabilities). | Ceiling can be altered by Central Government notification under Section 1(5) of the Social Security Code. | **VERIFIED (Active)** |
| `esic_contribution_period_rule` | **ESI Act 1948, Section 2(9) Proviso & Regulation 4** | ESI (General) Regulations, 1950 (Reg 4) & ESI Act Section 2(9) Proviso | Two 6-month contribution periods (April–Sept and Oct–March). If wages exceed ₹21,000 during a period, coverage continues until the end of that period. | Preserved to guarantee continuity of medical and sickness benefits during treatment. | **VERIFIED (Active)** |

---

## 3. High-Priority Statutory Caveats for Legal & Course Review

### A. The 50% Wage Definition Rule (Code on Wages, 2019, Section 2(y))
- **Current Law (pre-Code enforcement)**: PF wages are Basic + Dearness Allowance (DA) + Retaining Allowance. Under the Supreme Court's 2019 *Surya Roshni* judgment, allowances that are universally paid without specific contingency conditions form part of basic wages.
- **Labour Code Impact**: Exclusions (HRA, conveyance, overtime, bonuses) cannot exceed 50% of total remuneration. If exclusions exceed 50%, the excess is deemed wages for PF/ESIC computation.
- **Saathi AI Engine Implementation**: [rules_config.py](file:///c:/Users/pater/Downloads/Saathi%20ai/rules_config.py) documents this caveat in `wage_definition_note`. The engine evaluates basic wages as stated on the payslip and alerts if PF wages differ significantly from the 12% statutory computation.

### B. Voluntary Higher PF (Joint Declaration under Paragraph 26(6))
- **Statutory Provision**: An employee earning above ₹15,000 may opt to contribute 12% on actual basic pay (e.g. 12% of ₹25,000 = ₹3,000) rather than capping at ₹1,800, provided employer and employee submit a joint declaration.
- **Saathi AI Engine Implementation**: [payslip_analyzer.py](file:///c:/Users/pater/Downloads/Saathi%20ai/payslip_analyzer.py) recognizes BOTH calculations as compliant:
  1. Capped at ₹1,800 (Statutory limit).
  2. 12% of actual basic pay.
  Neither triggers an anomaly flag if mathematically correct.

### C. ESIC Wage Crossing Mid-Period (Proviso to Section 2(9))
- **Statutory Provision**: If a warehouse worker receives an increment or overtime pushing monthly gross from ₹19,500 to ₹23,000 during July (inside the April–September contribution period), ESIC deductions **must continue** through 30 September.
- **Saathi AI Engine Implementation**: Accepts `was_covered_at_start_of_period=True` on `PayslipInput` and validates the 0.75% deduction as compliant rather than improperly flagging it as exceeding the ceiling.

---

## 4. Auditor Sign-Off & Verification Process

To verify or update any statutory parameter:
1. Check the official EPFO notifications at [epfindia.gov.in](https://www.epfindia.gov.in).
2. Check official ESIC notifications at [esic.gov.in](https://www.esic.gov.in).
3. Update [rules_config.py](file:///c:/Users/pater/Downloads/Saathi%20ai/rules_config.py) and update the corresponding entry in this file.
