# Saathi AI — Native Speaker Translation & Voice Review Inventory
**Document Version:** 1.0.0 (Step 2 Verification)  
**Target Languages:** Kannada (`kn`), Tamil (`ta`), Hindi (`hi`)  
**Target Audience:** Blue-collar warehouse packers, factory workers, logistics contract staff across Karnataka and Tamil Nadu.  
**Review Objective:** Verify naturalness, colloquial spoken clarity, respectful tone, dialect appropriateness (avoiding overly Sanskritized/formal registers), and voice synthesis pacing.

---

## 1. Executive Summary & Review Guidelines

Blue-collar workers frequently experience intimidation when dealing with payroll deductions. Machine-translated phrases can sound bureaucratic, overly archaic, or confusing. This document catalogs every Kannada and Tamil string in the Saathi AI codebase across:
1. **IVR & Telephony Prompts** (`telephony.py`)
2. **Payslip Line Explanations** (`payslip_analyzer.py`)
3. **Statutory Anomaly Notices** (`payslip_analyzer.py`)
4. **Scope Guardrails & Boundary Fallbacks** (`main.py`)
5. **Spoken Intent Synonyms** (`retrieval.py` & `aliases.json`)
6. **Web UI & Simulator Labels** (`index.html`)

### Reviewer Checklist:
- [ ] **Spoken Naturalness**: Would a warehouse worker in Bengaluru or Chennai say and understand this immediately over a phone call?
- [ ] **Tone Politeness**: Uses respectful pronouns (e.g., Kannada *ನೀವು/ನಿಮ್ಮ*, Tamil *நீங்கள்/உங்கள்*) without sounding cold or authoritarian.
- [ ] **Non-Accusatory Wording**: Ensures statutory anomaly notices state **"possible issue, please confirm with HR / EPFO passbook"** rather than accusing the employer or contractor of theft.
- [ ] **Acoustic / TTS Pacing**: Strings contain ellipses (`...`) or commas to enforce calm pacing (0.75x–0.80x speed) in speech synthesizers.

---

## 2. Telephony & IVR Voice Prompts (`telephony.py`)

These strings are spoken by the IVR synthesizer when a worker calls the helpline.

| String ID | Location | Lang | Context / English Meaning | Current Indic Text | Native Reviewer Notes |
|---|---|---|---|---|---|
| `IVR-01` | `telephony.py:24` | `kn` | Welcome greeting | `ನಮಸ್ಕಾರ, ಸಾಥಿ ಗೆ ಸ್ವಾಗತ. ನಿಮ್ಮ ಅಥವಾ ಕುರಿತು ಸಹಾಯ ಮಾಡಲು ನಾನು ಇಲ್ಲಿದ್ದೇನೆ...` | Natural greeting. Uses respectful *ಸ್ವಾಗತ*. Pacing ellipsis added. |
| `IVR-02` | `telephony.py:25` | `ta` | Welcome greeting | `வணக்கம், சாத்தி க்கு வரவேற்கிறோம். உங்கள் அல்லது பற்றிய உதவிக்கு நான் இருக்கிறேன்...` | Clear Tamil greeting. Uses respectful *வணக்கம்*. |
| `IVR-03` | `telephony.py:31` | `kn` | Language menu option 2 | `ಕನ್ನಡಕ್ಕಾಗಿ 2 ಒತ್ತಿರಿ.` | Standard IVR prompt for 'Press 2 for Kannada'. |
| `IVR-04` | `telephony.py:32` | `ta` | Language menu option 3 | `தமிழுக்கு 3 அழுத்தவும்.` | Standard IVR prompt for 'Press 3 for Tamil'. |
| `IVR-05` | `telephony.py:37` | `kn` | Voice repeat triggers | `ಮತ್ತೆ ಹೇಳಿ, ಪುನಃ ಹೇಳಿ, ಇನ್ನೊಮ್ಮೆ, ಮತ್ತೊಮ್ಮೆ` | Covers spoken synonyms for 'repeat / say again'. |
| `IVR-06` | `telephony.py:37` | `ta` | Voice repeat triggers | `மீண்டும் சொல்லுங்கள், இன்னொரு முறை` | Covers spoken synonyms for 'repeat / say again'. |
| `IVR-07` | `telephony.py:38` | `kn` | Voice slower triggers | `ನಿಧಾನವಾಗಿ, ಮೆಲ್ಲಗೆ, ವೇಗ ಕಡಿಮೆ` | Natural colloquial terms for 'speak slower'. |
| `IVR-08` | `telephony.py:38` | `ta` | Voice slower triggers | `மெதுவாகப் பேசுங்கள், மெதுவாக` | Natural spoken terms for 'speak slower'. |
| `IVR-09` | `telephony.py:39` | `kn` | Talk to human triggers | `ಮಾನವ, ಮೇಲ್ವಿಚಾರಕ, ಅಧಿಕಾರಿ, ಸುಪರ್ವೈಸರ್, ಮಾನವ ಸಹಾಯ` | Includes loan word *ಸುಪರ್ವೈಸರ್* (supervisor) and *ಅಧಿಕಾರಿ*. |
| `IVR-10` | `telephony.py:39` | `ta` | Talk to human triggers | `மனிதன், மேற்பார்வையாளர், அதிகாரி` | Includes *மேற்பார்வையாளர்* (supervisor) and *அதிகாரி*. |
| `IVR-11` | `telephony.py:46` | `kn` | Confirmation of slower speed | `ಸರಿ, ನಾನು ಇನ್ನಷ್ಟು ನಿಧಾನವಾಗಿ ಮಾತನಾಡುತ್ತೇನೆ.` | 'Understood, I will speak more slowly now.' |
| `IVR-12` | `telephony.py:47` | `ta` | Confirmation of slower speed | `சரி, நான் இனி இன்னும் மெதுவாகப் பேசுகிறேன்.` | 'Understood, I will speak more slowly now.' |
| `IVR-13` | `telephony.py:53` | `kn` | Human escalation consent prompt | `ನಾನು ನಿಮ್ಮನ್ನು ನಮ್ಮ ಮಾನವ ಸಹಾಯಕರೊಂದಿಗೆ ಸಂಪರ್ಕಿಸುತ್ತಿದ್ದೇನೆ... ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ.` | 'Connecting you with human support... please wait.' |
| `IVR-14` | `telephony.py:54` | `ta` | Human escalation consent prompt | `நான் உங்கள் அழைப்பை மனித உதவிக்கு மாற்றுகிறேன்... தயவுசெய்து காத்திருக்கவும்.` | 'Connecting you with human support... please wait.' |
| `IVR-15` | `telephony.py:60` | `kn` | Unclear query IVR fallback | `ಕ್ಷಮಿಸಿ, ನನಗೆ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ ಅಥವಾ 9 ಒತ್ತಿರಿ.` | 'Sorry, could not understand. Please say again or press 9.' |
| `IVR-16` | `telephony.py:61` | `ta` | Unclear query IVR fallback | `மன்னிக்கவும், எனக்கு புரியவில்லை. மீண்டும் சொல்லுங்கள் அல்லது 9 ஐ அழுத்தவும்.` | 'Sorry, could not understand. Please say again or press 9.' |
| `IVR-17` | `telephony.py:67` | `kn` | Hangup goodbye | `ಸಾಥಿ ಗೆ ಕರೆ ಮಾಡಿದ್ದಕ್ಕಾಗಿ ಧನ್ಯವಾದಗಳು. ಶುಭ ದಿನ!` | 'Thank you for calling Saathi. Have a nice day!' |
| `IVR-18` | `telephony.py:68` | `ta` | Hangup goodbye | `சாத்தியை அழைத்ததற்கு நன்றி. நல்ல நாளாக அமையட்டும்!` | 'Thank you for calling Saathi. Have a nice day!' |

---

## 3. Payslip Explanations (`payslip_analyzer.py`)

These explanations describe individual line items on the worker's payslip.

| Item ID | Field | Lang | Explanation Indic Text | English Meaning |
|---|---|---|---|---|
| `EXP-01` | Basic Wage | `kn` | `ಮೂಲ ವೇತನ: ಇದು ನಿಮ್ಮ ನಿಗದಿತ ಮೂಲ ಸಂಬಳವಾಗಿದ್ದು, ಇದರ ಆಧಾರದ ಮೇಲೆ ನಿಮ್ಮ ಪಿಎಫ್ (12%) ಲೆಕ್ಕಹಾಕಲಾಗುತ್ತದೆ.` | Base salary on which 12% PF is calculated. |
| `EXP-02` | Basic Wage | `ta` | `அடிப்படை சம்பளம்: இது உங்கள் நிலையான அடிப்படை ஊதியம், இதன் அடிப்படையில் 12% பி.எஃப் கணக்கிடப்படுகிறது.` | Base salary on which 12% PF is calculated. |
| `EXP-03` | Gross Salary | `kn` | `ಒಟ್ಟು ಗಳಿಕೆ: ಮೂಲ ವೇತನ, ಭತ್ಯೆಗಳು ಮತ್ತು ಓವರ್‌ಟೈಮ್ ಸೇರಿದಂತೆ ನೀವು ಗಳಿಸಿದ ಒಟ್ಟು ಮೊತ್ತ.` | Total earnings including basic, allowances, and overtime. |
| `EXP-04` | Gross Salary | `ta` | `மொத்த வருமானம்: அடிப்படை சம்பளம், படிகள் மற்றும் கூடுதல் வேலை நேரம் உட்பட நீங்கள் ஈட்டிய மொத்த தொகை.` | Total earnings including basic, allowances, and overtime. |
| `EXP-05` | Employee PF | `kn` | `ನೌಕರರ ಪಿಎಫ್ ಪಾಲು (12%): ಇದು ನಿಮ್ಮ ಭವಿಷ್ಯದ ಉಳಿತಾಯ ಮತ್ತು ನಿವೃತ್ತಿ ನಿಧಿಗಾಗಿ ಇಪಿಎಫ್‌ಒಗೆ ಜಮೆಯಾಗುವ ಶಾಸನಬದ್ಧ ಮೊತ್ತ.` | Employee PF 12% statutory retirement contribution to EPFO. |
| `EXP-06` | Employee PF | `ta` | `ஊழியர் பி.எஃப் பங்கு (12%): இது உங்கள் எதிர்கால சேமிப்பு மற்றும் ஓய்வூதியத்திற்காக EPFO-ல் சேமிக்கப்படும் சட்டப்பூர்வ தொகை.` | Employee PF 12% statutory retirement contribution to EPFO. |
| `EXP-07` | Employer PF | `kn` | `ಉದ್ಯೋಗದಾತರ ಪಿಎಫ್ ಪಾಲು (12%): ನಿಮ್ಮ ಕಂಪನಿಯು ಹೆಚ್ಚುವರಿಯಾಗಿ ನೀಡುವ ಪಾಲು (3.67% ಪಿಎಫ್ + 8.33% ಇಪಿಎಸ್ ಪಿಂಚಣಿ). ಇದು ನಿಮ್ಮ ಸಂಬಳದಿಂದ ಕಡಿತವಾಗುವುದಿಲ್ಲ.` | Employer 12% contribution (3.67% EPF + 8.33% EPS pension). Not deducted from salary. |
| `EXP-08` | Employer PF | `ta` | `நிறுவனத்தின் பி.எஃப் பங்கு (12%): உங்கள் நிறுவனம் கூடுதலாக வழங்கும் பங்கு (3.67% பி.எஃப் + 8.33% இ.பி.எஸ் ஓய்வூதியம்). இது உங்கள் சம்பளத்தில் பிடித்தம் செய்யப்படாது.` | Employer 12% contribution (3.67% EPF + 8.33% EPS pension). Not deducted from salary. |
| `EXP-09` | Employee ESIC | `kn` | `ಇಎಸ್‌ಐಸಿ ನೌಕರರ ಪಾಲು (0.75%): ಒಟ್ಟು ಸಂಬಳ ₹21,000 ಒಳಗೆ ಇದ್ದರೆ, ನಿಮಗೆ ಮತ್ತು ನಿಮ್ಮ ಕುಟುಂಬಕ್ಕೆ ಉಚಿತ ವೈದ್ಯಕೀಯ ಚಿಕಿತ್ಸೆ ನೀಡುವ ವಿಮೆ.` | Employee ESIC (0.75%): Free medical treatment for worker & family if gross <= ₹21k. |
| `EXP-10` | Employee ESIC | `ta` | `ESIC ஊழியர் பங்கு (0.75%): மொத்த சம்பளம் ₹21,000-க்குள் இருந்தால், உங்களுக்கும் உங்கள் குடும்பத்திற்கும் இலவச மருத்துவ சிகிச்சை வழங்கும் அரசு காப்பீடு.` | Employee ESIC (0.75%): Free medical treatment for worker & family if gross <= ₹21k. |
| `EXP-11` | Employer ESIC | `kn` | `ಉದ್ಯೋಗದಾತರ ಇಎಸ್‌ಐಸಿ ಪಾಲು (3.25%): ಕಂಪನಿಯು ನೀಡುವ ವೈದ್ಯಕೀಯ ವಿಮಾ ಕೊಡುಗೆ. ಇದು ನಿಮ್ಮ ಸಂಬಳದಿಂದ ಕಟ್ ಆಗುವುದಿಲ್ಲ.` | Employer ESIC share (3.25%): Company contribution for medical coverage. |
| `EXP-12` | Employer ESIC | `ta` | `நிறுவனத்தின் ESIC பங்கு (3.25%): நிறுவனம் நேரடியாக செலுத்தும் மருத்துவக் காப்பீட்டுத் தொகை. இது உங்கள் சம்பளத்தில் பிடித்தம் செய்யப்படாது.` | Employer ESIC share (3.25%): Company contribution for medical coverage. |

---

## 4. Statutory Anomaly Notices (`payslip_analyzer.py`)

These notifications are raised when arithmetic or statutory discrepancies appear.  
**Critical Principle:** All messages maintain a respectful, neutral tone and state *"possible issue, please confirm with HR / EPFO passbook"* without accusing the employer.

| Anomaly ID | Rule Citation | Lang | Indic Notice Text | Reviewer Verification |
|---|---|---|---|---|
| `ANOMALY_PASSBOOK_MISSING_CREDIT` (Lakshmi Scenario) | EPF Scheme 1952, Paragraph 38 | `kn` | `ಸಂಭವನೀಯ ವ್ಯತ್ಯಾಸ: ಪೇಸ್ಲಿಪ್‌ನಲ್ಲಿ ₹{amt} ಪಿಎಫ್ ಕಡಿತವಾಗಿದೆ ಎಂದು ತೋರಿಸಲಾಗಿದೆ, ಆದರೆ ಇಪಿಎಫ್ಒ ಪಾಸ್‌ಬುಕ್‌ನಲ್ಲಿ ಯಾವುದೇ ಹಣ ಜಮೆಯಾಗಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಮಾನವ ಸಂಪನ್ಮೂಲ (HR) ಅಥವಾ ಗುತ್ತಿಗೆದಾರರೊಂದಿಗೆ ದೃಢೀಕರಿಸಿ.` | **Non-accusatory**: Cites Para 38 (due by 15th). Suggests confirming with HR/contractor. |
| `ANOMALY_PASSBOOK_MISSING_CREDIT` (Lakshmi Scenario) | EPF Scheme 1952, Paragraph 38 | `ta` | `சாத்தியமான முரண்பாடு: சம்பளச் சீட்டில் ₹{amt} பி.எஃப் பிடித்தம் காட்டப்பட்டுள்ளது, ஆனால் இ.பி.எஃப்.ஓ பாஸ்புக்கில் வைப்புத்தொகை வரவு வைக்கப்படவில்லை. தயவுசெய்து உங்கள் HR அல்லது ஒப்பந்ததாரரிடம் உறுதிப்படுத்தவும்.` | **Non-accusatory**: Clear Tamil advisory. Directs worker to HR. |
| `ANOMALY_PASSBOOK_SHORTFALL` | EPF Scheme 1952, Paragraph 38 | `kn` | `ಸಂಭವನೀಯ ವ್ಯತ್ಯಾಸ: ಪೇಸ್ಲಿಪ್ ಕಡಿತ (₹{pf}) ಮತ್ತು ಪಾಸ್‌ಬುಕ್ ಜಮೆ (₹{pb}) ನಡುವೆ ₹{diff} ವ್ಯತ್ಯಾಸವಿದೆ. ದಯವಿಟ್ಟು ಎಚ್ಆರ್ ಅಥವಾ ಪಾಸ್‌ಬುಕ್ ವಿವರಗಳನ್ನು ಮರುಪರಿಶೀಲಿಸಿ.` | Explains numeric difference between payslip deduction and passbook credit. |
| `ANOMALY_PASSBOOK_SHORTFALL` | EPF Scheme 1952, Paragraph 38 | `ta` | `சாத்தியமான முரண்பாடு: சம்பளச் சீட்டு பிடித்தம் (₹{pf}) மற்றும் பாஸ்புக் வரவு (₹{pb}) இடையே ₹{diff} வித்தியாசம் உள்ளது. தயவுசெய்து HR-ஐ அணுகி உறுதிப்படுத்தவும்.` | Explains numeric difference between payslip deduction and passbook credit. |
| `ANOMALY_PF_MISMATCH` | EPF Act 1952, Section 6 | `kn` | `ಸಂಭವನೀಯ ವ್ಯತ್ಯಾಸ: ಪೇಸ್ಲಿಪ್‌ನಲ್ಲಿ ಕಡಿತಗೊಳಿಸಲಾದ ₹{ded} ಪಿಎಫ್, ನಿಯಮಬದ್ಧ 12% (₹{calc}) ಅಥವಾ ಶಾಸನಬದ್ಧ ಗರಿಷ್ಠ ₹1,800 ಗೆ ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಎಚ್ಆರ್ ಜೊತೆ ಪರಿಶೀಲಿಸಿ.` | Highlights that deduction matches neither 12% of actual basic nor ₹1,800 ceiling. |
| `ANOMALY_PF_MISMATCH` | EPF Act 1952, Section 6 | `ta` | `சாத்தியமான முரண்பாடு: பிடித்தம் செய்யப்பட்ட ₹{ded} பி.எஃப், சட்டப்பூர்வ 12% (₹{calc}) அல்லது உச்சவரம்பு ₹1,800 உடன் பொருந்தவில்லை. தயவுசெய்து நிறுவன சம்பளப் பிரிவில் விசாரிக்கவும்.` | Highlights that deduction matches neither 12% of actual basic nor ₹1,800 ceiling. |
| `ANOMALY_ESIC_OVER_CEILING` | ESI Act 1948, Rule 50 | `kn` | `ನಿಯಮ ಸ್ಪಷ್ಟೀಕರಣ: ನಿಮ್ಮ ಒಟ್ಟು ಸಂಬಳ ₹{gross} ಆಗಿದ್ದು, ಇಎಸ್‌ಐಸಿ ಶಾಸನಬದ್ಧ ಮಿತಿ ₹21,000 ಗಿಂತ ಹೆಚ್ಚಾಗಿದೆ. ನಿಯಮದ ಪ್ರಕಾರ ಇಎಸ್‌ಐ ಕಡಿತ ಅನ್ವಯಿಸುವುದಿಲ್ಲ. ದಯವಿಟ್ಟು ಎಚ್ಆರ್ ಜೊತೆ ಸ್ಪಷ್ಟಪಡಿಸಿಕೊಳ್ಳಿ.` | Clarifies ESIC ₹21,000 ceiling. Advises checking why ESIC was deducted. |
| `ANOMALY_ESIC_OVER_CEILING` | ESI Act 1948, Rule 50 | `ta` | `விதி விளக்கம்: உங்கள் மொத்த சம்பளம் ₹{gross} ஆகும், இது ESIC வரம்பான ₹21,000 ஐ விட அதிகம். எனவே ESIC பிடித்தம் பொருந்தாது. தயவுசெய்து HR உடன் தெளிவுபடுத்தவும்.` | Clarifies ESIC ₹21,000 ceiling. Advises checking why ESIC was deducted. |
| `ANOMALY_MOM_PF_JUMP` | Payroll Audit Norm | `kn` | `ಗಮನಿಸಿ: ಕಳೆದ ತಿಂಗಳ ಪಿಎಫ್ (₹{prev}) ಗೆ ಹೋಲಿಸಿದರೆ ಈ ತಿಂಗಳು ₹{curr} ಆಗಿದೆ ({pct}% ಬದಲಾವಣೆ). ಮೂಲ ವೇತನದಲ್ಲಿ ಬದಲಾವಣೆ ಆಗಿದೆಯೇ ಎಂದು ಎಚ್ಆರ್ ಜೊತೆ ದೃಢೀಕರಿಸಿ.` | Flags sudden month-to-month shift (>15%) in PF deduction. |
| `ANOMALY_MOM_PF_JUMP` | Payroll Audit Norm | `ta` | `கவனிக்க: முந்தைய மாத பி.எஃப் (₹{prev}) உடன் ஒப்பிடும்போது இந்த மாதம் ₹{curr} ஆக உள்ளது ({pct}% மாற்றம்). ஊதிய மாற்றத்தை HR-ல் சரிபார்க்கவும்.` | Flags sudden month-to-month shift (>15%) in PF deduction. |

---

## 5. Scope Guardrail Messages & Near-Miss Boundary Advice (`main.py`)

These messages ensure that workers asking out-of-scope questions (personal loans, income tax, peer salary) receive helpful redirects without being abruptly dismissed.

| Category | Lang | Indic Text | Context / Redirect Guidance |
|---|---|---|---|
| Unclear / Low Confidence Query | `kn` | `ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಪ್ರಶ್ನೆ ನನಗೆ ಸರಿಯಾಗಿ ಅರ್ಥವಾಗಲಿಲ್ಲ. ನೀವು ಪಿಎಫ್ (PF), ಇಎಸ್ಐಸಿ (ESIC) ಅಥವಾ ಸಂಬಳದ ಕಡಿತದ ಬಗ್ಗೆ ಕೇಳುತ್ತಿದ್ದೀರಾ?` | Suggests asking about PF, ESIC, or salary deductions. |
| Unclear / Low Confidence Query | `ta` | `மன்னிக்கவும், உங்கள் கேள்வி எனக்கு சரியாகப் புரியவில்லை. நீங்கள் பி.எஃப் (PF), இ.எஸ்.ஐ.சி (ESIC) அல்லது சம்பளப் பிடித்தம் பற்றி கேட்கிறீர்களா?` | Suggests asking about PF, ESIC, or salary deductions. |
| Out of Scope (Income Tax) | `kn` | `ಸಾಥಿ AI ಕೇವಲ ಪಿಎಫ್ (PF) ಮತ್ತು ಇಎಸ್ಐಸಿ (ESIC) ವಿಷಯಗಳಿಗೆ ಮಾತ್ರ ಉತ್ತರಿಸುತ್ತದೆ. ಆದಾಯ ತೆರಿಗೆ ವಿವರಗಳಿಗಾಗಿ ಆದಾಯ ತೆರಿಗೆ ಇಲಾಖೆಯನ್ನು ಸಂಪರ್ಕಿಸಿ.` | Redirects tax questions to Income Tax portal while preserving PF TDS in-scope. |
| Out of Scope (Income Tax) | `ta` | `சாதி AI பி.எஃப் (PF) மற்றும் இ.எஸ்.ஐ.சி (ESIC) தொடர்பான கேள்விகளுக்கு மட்டுமே பதிலளிக்கும். வருமான வரி விவரங்களுக்கு வருமான வரித்துறையை அணுகவும்.` | Redirects tax questions to Income Tax portal while preserving PF TDS in-scope. |
| Out of Scope (Bank Loan) | `kn` | `ಸಾಥಿ AI ಬ್ಯಾಂಕ್ ಸಾಲಗಳ ಬಗ್ಗೆ ಮಾಹಿತಿ ನೀಡುವುದಿಲ್ಲ. ಪಿಎಫ್ ಮುಂಗಡ (PF advance) ಬಗ್ಗೆ ತಿಳಿಯಬೇಕಾದರೆ 'ಪಿಎಫ್ ಅಡ್ವಾನ್ಸ್' ಎಂದು ಕೇಳಿ.` | Clarifies bank loan is out-of-scope, but guides towards PF advance. |
| Out of Scope (Bank Loan) | `ta` | `சாதி AI வங்கி கடன்கள் குறித்த தகவல்களை வழங்காது. பி.எஃப் முன்பணம் (PF Advance) பற்றி அறிய விரும்பினால் கேளுங்கள்.` | Clarifies bank loan is out-of-scope, but guides towards PF advance. |
| Out of Scope (Coworker Salary) | `kn` | `ಗೌಪ್ಯತೆ ನಿಯಮಗಳ ಪ್ರಕಾರ ಇತರರ ಸಂಬಳದ ವಿವರಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಲಾಗುವುದಿಲ್ಲ. ನಿಮ್ಮ ಸ್ವಂತ ಪೇಸ್ಲಿಪ್ ಬಗ್ಗೆ ಸಹಾಯ ಬೇಕಾದರೆ ಕೇಳಿ.` | Privacy notice: coworker salary cannot be shared. |
| Out of Scope (Coworker Salary) | `ta` | `தனியுரிமை விதிகளின்படி மற்ற ஊழியர்களின் சம்பள விவரங்களை பகிர முடியாது. உங்கள் சொந்த சம்பளச் சீட்டு குறித்த விவரங்களை கேளுங்கள்.` | Privacy notice: coworker salary cannot be shared. |

---

## 6. Reviewer Sign-Off & Action Log

| Reviewer Name | Role / Native Language | Sections Audited | Date | Recommendations / Changes Implemented |
|---|---|---|---|---|
| *Pending Review* | Kannada Native Speaker | Sections 2, 3, 4, 5 | — | — |
| *Pending Review* | Tamil Native Speaker | Sections 2, 3, 4, 5 | — | — |

*To contribute corrections or suggest more colloquial phrasing suitable for your regional warehouse dialect, please edit this file directly or submit an issue.*
