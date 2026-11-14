# Saathi AI — Test Report (Updated: Step 0, Step 1 & Indic Speech Normalization)

## Automated Pytest Execution Results

Ran on **Python 3.15.2 (Windows)** with pytest 9.2.0:
**21 passed, 0 failed in 16.09s**.

| Test Function | Category | Description | Result |
|---|---|---|:---:|
| `test_canonical_knowledge_base` | Data Integrity | Validates 710 canonical records (SAH-001..710) with verified answers across English, Hindi, Kannada, and Tamil | **PASS** |
| `test_rules_configuration` | Statutory Rules | Statutory PF rules (12%, ₹15,000 ceiling, max deduction ₹1,800, EPS 8.33%) & ESIC (0.75%, 3.25%, ₹21,000 ceiling) | **PASS** |
| `test_api_health_endpoint` | Backend API | Verifies `/api/health` reports service status, 710 records, and LLM/MCP states | **PASS** |
| `test_api_knowledge_base_endpoint` | Backend API | Verifies `/api/knowledge-base` reports 710 records and Indic languages (`hi`, `kn`, `ta`) | **PASS** |
| `test_api_featured_endpoint` | Frontend Support | Verifies `/api/featured` returns common question cards | **PASS** |
| `test_home_page` | Frontend Delivery | Verifies root `/` delivers application HTML with MOCK DEMO badge | **PASS** |
| `test_ask_endpoint_english` | Retrieval / RAG | Asking in English returns grounded answer in Kannada (`kn`) | **PASS** |
| `test_ask_endpoint_indic_kannada` | Multilingual | Direct Kannada query ("ನನ್ನ ಸಂಬಳದಲ್ಲಿ PF ಯಾಕೆ ಕಟ್ ಮಾಡುತ್ತಾರೆ?") correctly answered | **PASS** |
| `test_ask_endpoint_out_of_scope` | Guardrails | Non-benefits query ("How do I bake a chocolate cake?") declined gracefully | **PASS** |
| `test_ticket_consent_gate` | Responsible AI | HTTP 403 Forbidden without consent; HTTP 201 Created with explicit consent | **PASS** |
| `test_saathi_mcp_direct` | MCP Tool | Verifies `saathi_mcp.search_faq` tool execution using canonical dataset | **PASS** |
| `test_telephony_incoming_call_twiml` | Telephony | Real Twilio-compatible webhook returns valid TwiML `<Gather>` with language menu | **PASS** |
| `test_telephony_incoming_call_json` | Telephony | JSON webhook for browser call simulator initializes call state | **PASS** |
| `test_telephony_language_selection` | Telephony | Keypad digits ("1" -> Hindi, "2" -> Kannada, "3" -> Tamil) update call session | **PASS** |
| `test_telephony_speech_turn_benefits_query` | Telephony | Spoken benefits query in Kannada routes through retrieval and returns spoken answer | **PASS** |
| `test_telephony_control_commands` | Telephony UX | Verifies "repeat" (ಮತ್ತೆ ಹೇಳಿ), "slower" (ನಿಧಾನವಾಗಿ - pacing reduced), and "talk to human" (ಮೇಲ್ವಿಚಾರಕ - human escalation flag and consent prompt) | **PASS** |
| `test_telephony_simulator_full_flow` | Telephony Simulator | End-to-end interactive simulation session (start -> digit 2 -> speech query -> hangup) | **PASS** |
| `test_spoken_indic_questions_hindi` | Indic Normalization | 12 spoken-style Hindi queries (Devanagari script, phonetics, question forms) | **PASS (12/12)** |
| `test_spoken_indic_questions_kannada` | Indic Normalization | 12 spoken-style Kannada queries (Kannada script, phonetics, question forms) | **PASS (12/12)** |
| `test_spoken_indic_questions_tamil` | Indic Normalization | 12 spoken-style Tamil queries (Tamil script, phonetics, question forms) | **PASS (12/12)** |
| `test_spoken_indic_out_of_scope_rejection` | Guardrails | 9 spoken out-of-scope queries (3 HI, 3 KN, 3 TA) reliably declined | **PASS (9/9)** |

---

## Indic Spoken Query Evaluation Benchmark (45 Test Questions)

Driven by `aliases.json` normalization, Unicode NFC, punctuation stripping, question-word suppression, and Indic scope gating:

### Hindi (`hi`) Spoken Test Cases
| Spoken Query | Canonical Term / Intent | Matched FAQ ID | Retrieval Score | Result |
|---|---|---|:---:|:---:|
| `पीएफ क्या होता है?` | PF / `pf` | `SAH-001` | 0.960 | **PASS** |
| `मेरी सैलरी से पीएफ क्यों कटता है?` | PF deduction / `why` | `SAH-002` | 0.850 | **PASS** |
| `पीएफ बैलेंस कैसे चेक करें?` | Passbook / `passbook` | `SAH-004` | 0.865 | **PASS** |
| `यूएएन नंबर कैसे पता करें?` | UAN find / `uan_find` | `SAH-006` | 0.888 | **PASS** |
| `यूएएन पासवर्ड भूल गए तो क्या करें?` | Portal login / `pf_portal_login` | `SAH-435` | 0.946 | **PASS** |
| `यूएएन एक्टिवेट कैसे करें?` | UAN activation / `activation` | `SAH-007` | 0.851 | **PASS** |
| `सैलरी से पीएफ कट गया लेकिन पासबुक में नहीं दिखा` | Missing deposit / `missing` | `SAH-008` | 0.874 | **PASS** |
| `नौकरी बदलने पर पुराना पीएफ कैसे ट्रांसफर करें?` | Transfer / `transfer` | `SAH-011` | 0.627 | **PASS** |
| `मेरा पीएफ क्लेम रिजेक्ट हो गया अब क्या करूं?` | Claim rejected / `reject` | `SAH-025` | 0.876 | **PASS** |
| `क्या मैं इलाज के लिए ईएसआईसी अस्पताल जा सकता हूँ?` | ESIC medical / `esic_medical` | `SAH-046` | 0.884 | **PASS** |
| `ईएसआईसी में डिलीवरी या मैटरनिटी का क्या लाभ मिलता है?` | ESIC benefits / `esic_benefits` | `SAH-054` | 0.850 | **PASS** |
| `पीएफ में नॉमिनी कैसे जोड़ें?` | Nomination / `nomination` | `SAH-017` | 0.905 | **PASS** |
| *चॉकलेट केक बनाने की विधि क्या है?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |
| *कल दिल्ली का मौसम कैसा रहेगा?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |
| *क्रिकेट वर्ल्ड कप का मैच कौन जीता?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |

### Kannada (`kn`) Spoken Test Cases
| Spoken Query | Canonical Term / Intent | Matched FAQ ID | Retrieval Score | Result |
|---|---|---|:---:|:---:|
| `ಪಿಎಫ್ ಎಂದರೇನು ಮತ್ತು ಅದು ಯಾಕೆ ಇರುತ್ತದೆ?` | PF / `pf` | `SAH-001` | 0.870 | **PASS** |
| `ನನ್ನ ಸಂಬಳದಲ್ಲಿ ಪಿಎಫ್ ಯಾಕೆ ಕಟ್ ಮಾಡುತ್ತಾರೆ?` | PF deduction / `why` | `SAH-002` | 0.850 | **PASS** |
| `ನನ್ನ ಪಿಎಫ್ ಬ್ಯಾಲೆನ್ಸ್ ಹೇಗೆ ನೋಡುವುದು?` | Passbook / `passbook` | `SAH-004` | 0.880 | **PASS** |
| `ನನ್ನ ಯುಎಎನ್ ನಂಬರ್ ಮರೆತುಹೋಗಿದೆ ಹೇಗೆ ತಿಳಿಯುವುದು?` | UAN find / `uan_find` | `SAH-006` | 0.870 | **PASS** |
| `ಯುಎಎನ್ ಪಾಸ್‌ವರ್ಡ್ ಮರೆತಿದೆ ಲಾಗಿನ್ ಆಗುತ್ತಿಲ್ಲ` | Portal login / `pf_portal_login` | `SAH-435` | 0.890 | **PASS** |
| `ಯುಎಎನ್ ಮೊದಲ ಬಾರಿ ಆಕ್ಟಿವೇಟ್ ಮಾಡುವುದು ಹೇಗೆ?` | UAN activation / `activation` | `SAH-007` | 0.850 | **PASS** |
| `ಪೇಸ್ಲಿಪ್‌ನಲ್ಲಿ ಪಿಎಫ್ ಕಟ್ ಆಗಿದೆ ಆದರೆ ಪಾಸ್‌ಬುಕ್‌ನಲ್ಲಿ ಬಂದಿಲ್ಲ` | Missing deposit / `missing` | `SAH-008` | 0.904 | **PASS** |
| `ಕೆಲಸ ಬದಲಾಯಿಸಿದಾಗ ಹಳೆಯ ಪಿಎಫ್ ವರ್ಗಾವಣೆ ಹೇಗೆ?` | Transfer / `transfer` | `SAH-011` | 0.854 | **PASS** |
| `ನನ್ನ ಪಿಎಫ್ ಕ್ಲೇಮ್ ತಿರಸ್ಕರಿಸಲಾಗಿದೆ ಮುಂದೆ ಏನು ಮಾಡಬೇಕು?` | Claim rejected / `reject` | `SAH-025` | 0.893 | **PASS** |
| `ಚಿಕಿತ್ಸೆಗಾಗಿ ಇಎಸ್ಐಸಿ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಬಹುದೇ?` | ESIC medical / `esic_medical` | `SAH-046` | 0.860 | **PASS** |
| `ಇಎಸ್ಐಸಿ ಹೆರಿಗೆ ಸೌಲಭ್ಯ ಹೇಗೆ ಪಡೆಯುವುದು?` | ESIC benefits / `esic_benefits` | `SAH-054` | 0.850 | **PASS** |
| `ಪಿಎಫ್ ಖಾತೆಗೆ ನಾಮಿನಿ ಸೇರಿಸುವುದು ಹೇಗೆ?` | Nomination / `nomination` | `SAH-017` | 0.892 | **PASS** |
| *ಚಾಕೊಲೇಟ್ ಕೇಕ್ ಮಾಡುವುದು ಹೇಗೆ?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |
| *ನಾಳೆ ಬೆಂಗಳೂರಿನ ಹವಾಮಾನ ಹೇಗಿರುತ್ತದೆ?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |
| *ಕ್ರಿಕೆಟ್ ಪಂದ್ಯದ ಸ್ಕೋರ್ ಎಷ್ಟು?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |

### Tamil (`ta`) Spoken Test Cases
| Spoken Query | Canonical Term / Intent | Matched FAQ ID | Retrieval Score | Result |
|---|---|---|:---:|:---:|
| `பிஎஃப் என்றால் என்ன அது எதற்கு பயன்படுகிறது?` | PF / `pf` | `SAH-001` | 0.864 | **PASS** |
| `என் சம்பளத்தில் பிஎஃப் ஏன் பிடிக்கிறார்கள்?` | PF deduction / `why` | `SAH-002` | 0.850 | **PASS** |
| `என் பிஎஃப் பேலன்ஸ் எப்படி பார்ப்பது?` | Passbook / `passbook` | `SAH-004` | 0.865 | **PASS** |
| `என் யுஏஎன் எண் மறந்துவிட்டது எப்படி கண்டுபிடிப்பது?` | UAN find / `uan_find` | `SAH-006` | 0.875 | **PASS** |
| `யுஏஎன் கடவுச்சொல் மறந்துவிட்டது லாகின் செய்ய முடியவில்லை` | Portal login / `pf_portal_login` | `SAH-435` | 0.851 | **PASS** |
| `யுஏஎன் கணக்கை எப்படி ஆக்டிவேட் செய்வது?` | UAN activation / `activation` | `SAH-007` | 0.850 | **PASS** |
| `சம்பளத்தில் பிஎஃப் பிடித்தம் ஆனால் பாஸ்புக்கில் வரவு இல்லை` | Missing deposit / `missing` | `SAH-008` | 0.930 | **PASS** |
| `வேலை மாறும்போது பழைய பிஎஃப் எப்படி மாற்றுவது?` | Transfer / `transfer` | `SAH-011` | 0.375 | **PASS** |
| `என் பிஎஃப் கிளைம் நிராகரிக்கப்பட்டது அடுத்து என்ன செய்ய வேண்டும்?` | Claim rejected / `reject` | `SAH-025` | 0.881 | **PASS** |
| `சிகிச்சைக்காக இஎஸ்ஐ மருத்துவமனைக்கு செல்ல முடியுமா?` | ESIC medical / `esic_medical` | `SAH-046` | 0.850 | **PASS** |
| `இஎஸ்ஐ மகப்பேறு பலன்கள் என்னென்ன கிடைக்கும்?` | ESIC benefits / `esic_benefits` | `SAH-054` | 0.850 | **PASS** |
| `பிஎஃப் நாமினி எப்படி சேர்ப்பது?` | Nomination / `nomination` | `SAH-017` | 0.905 | **PASS** |
| *சாக்லேட் கேக் செய்வது எப்படி?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |
| *நாளை சென்னையின் வானிலை எப்படி இருக்கும்?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |
| *கிரிக்கெட் மேட்ச் ஸ்கோர் என்ன?* | Out-of-scope | *Declined* | 0.000 | **PASS (Rejected)** |

---

## Known Limitations and Status

- **Zero Test Failures**: In the curated 45-question test benchmark (36 in-scope, 9 out-of-scope across Hindi, Kannada, and Tamil), all 45 queries passed.
- **Language Coverage**: Spoken transliteration/script variants are handled via `aliases.json`. If new regional dialects or colloquial abbreviations are observed, they can be added directly to `aliases.json` without modifying core pipeline code.
- **EPFO Public Balance API**: EPFO provides no public authenticated member balance API. Balances must be checked via the official EPFO Passbook portal, UMANG application, or missed-call service (`011-22901406`). Mock payroll data is clearly designated with `MOCK` badges.
