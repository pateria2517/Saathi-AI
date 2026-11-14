"""Saathi AI — Verification and Smoke Test Suite (Step 0).

Tests:
1. Single canonical 710-record knowledge base integrity.
2. Settings and rules configuration (statutory PF/ESIC rates and ceilings).
3. FastAPI application health, knowledge-base, and ask endpoints.
4. Multilingual question handling (English, Hindi, Kannada, Tamil).
5. Ticket consent gating (HTTP 403 without consent, HTTP 201 with consent).
6. saathi_mcp.py tool execution.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from config import settings, BASE_DIR
import rules_config
from main import app, KB
import saathi_mcp


client = TestClient(app)


def test_canonical_knowledge_base():
    """Verify that the canonical 710-record JSON is valid and intact."""
    kb_path = Path(settings.knowledge_path)
    assert kb_path.is_file(), f"Knowledge base missing at {kb_path}"
    with open(kb_path, encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("records", data) if isinstance(data, dict) else data
    assert len(records) == 710, f"Expected 710 records, found {len(records)}"
    
    first = records[0]
    assert first["id"] == "SAH-001"
    assert "answers" in first
    for lang in ("en", "hi", "kn", "ta"):
        assert lang in first["answers"], f"Missing answer for language {lang}"
        assert len(first["answers"][lang]) > 0


def test_rules_configuration():
    """Verify that every PF and ESIC statutory rule and ceiling is properly configured."""
    epf = rules_config.EPF_RULES
    esic = rules_config.ESIC_RULES
    
    # Statutory PF
    assert epf["employee_contribution_rate"] == 0.12
    assert epf["employer_total_contribution_rate"] == 0.12
    assert epf["employer_eps_share_rate"] == 0.0833
    assert epf["statutory_wage_ceiling_monthly"] == 15000.0
    assert epf["max_statutory_employee_deduction"] == 1800.0
    
    # Statutory ESIC
    assert esic["employee_contribution_rate"] == 0.0075
    assert esic["employer_contribution_rate"] == 0.0325
    assert esic["statutory_wage_ceiling_monthly"] == 21000.0
    assert esic["total_contribution_rate"] == 0.04


def test_api_health_endpoint():
    """Verify /api/health returns 710 total records and valid status."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["knowledge_records_total"] == 710
    assert "llm_provider" in data


def test_api_knowledge_base_endpoint():
    """Verify /api/knowledge-base returns metadata."""
    res = client.get("/api/knowledge-base")
    assert res.status_code == 200
    data = res.json()
    assert data["record_count"] == 710
    assert set(data["languages"]) == {"hi", "kn", "ta"}


def test_api_featured_endpoint():
    """Verify /api/featured returns question cards for UI."""
    res = client.get("/api/featured")
    assert res.status_code == 200
    data = res.json()
    assert "questions" in data
    assert len(data["questions"]) >= 5


def test_home_page():
    """Verify root / serves HTML with MOCK labels."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "Saathi AI" in res.text
    assert "MOCK" in res.text


def test_index_html_script_syntax_and_dom_ids():
    """Extract every <script> block from index.html, run node --check, and verify all JS IDs exist in HTML."""
    from test_index_html import test_script_syntax_with_node_check, test_all_js_referenced_ids_exist_in_html
    test_script_syntax_with_node_check("index.html")
    test_all_js_referenced_ids_exist_in_html("index.html")


def test_ask_endpoint_english():
    """Verify asking in English returns grounded answer in Kannada."""
    res = client.post("/api/ask", json={
        "question": "Why is PF deducted from my salary every month?",
        "language": "kn",
        "include_english": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["understood"] is True
    assert len(data["answer"]) > 0
    assert data["scope"] == "pf_esic"
    assert data["faq_id"] in ("SAH-002", "SAH-050", "SAH-001")


def test_ask_endpoint_indic_kannada():
    """Verify asking directly in Kannada is accepted and answered."""
    res = client.post("/api/ask", json={
        "question": "ನನ್ನ ಸಂಬಳದಲ್ಲಿ PF ಯಾಕೆ ಕಟ್ ಮಾಡುತ್ತಾರೆ?",
        "language": "kn",
        "include_english": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["understood"] is True
    assert len(data["answer"]) > 0


def test_ask_endpoint_out_of_scope():
    """Verify unrelated questions are declined gracefully."""
    res = client.post("/api/ask", json={
        "question": "How do I bake a chocolate cake?",
        "language": "hi",
        "include_english": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["understood"] is False
    assert data["scope"] == "out_of_scope"


def test_ticket_consent_gate():
    """Verify tickets require explicit consent (HTTP 403 without consent, HTTP 201 with consent)."""
    # 1. Without consent -> 403 Forbidden
    res_no_consent = client.post("/api/tickets", json={
        "consent": False,
        "question": "My PF was not deposited by the warehouse contractor.",
        "category": "PF / EPFO",
        "language": "kn"
    })
    assert res_no_consent.status_code == 403
    
    # 2. With consent -> 201 Created
    res_consent = client.post("/api/tickets", json={
        "consent": True,
        "question": "My PF was not deposited by the warehouse contractor.",
        "title": "Missing PF Deposit (MOCK)",
        "description": "Lakshmi reports PF deduction on payslip but no credit in EPFO passbook.",
        "category": "PF / EPFO",
        "language": "kn",
        "source": "unit-test"
    })
    assert res_consent.status_code == 201
    ticket_data = res_consent.json()["ticket"]
    assert ticket_data["id"].startswith("SAT-")
    assert ticket_data["status"] == "Open"


def test_saathi_mcp_direct():
    """Verify saathi_mcp tool execution using the canonical dataset."""
    res = saathi_mcp.search_faq("Why is PF deducted from my salary?", language="kn", k=2)
    assert res["understood"] is True
    assert len(res["matches"]) > 0
    assert res["matches"][0]["id"] in ("SAH-002", "SAH-050", "SAH-001")


def test_telephony_incoming_call_twiml():
    """Verify Twilio-style webhook returns standard TwiML with language IVR."""
    res = client.post(
        "/api/telephony/incoming",
        data={"CallSid": "CALL-TEST-TWILIO-001", "From": "+919876543210"},
        headers={"User-Agent": "TwilioProxy/1.1", "Content-Type": "application/x-www-form-urlencoded"}
    )
    assert res.status_code == 200
    assert "application/xml" in res.headers.get("content-type", "")
    assert "<Response>" in res.text
    assert "<Gather" in res.text
    assert "1" in res.text and "2" in res.text and "3" in res.text


def test_telephony_incoming_call_json():
    """Verify JSON webhook for browser call simulator."""
    res = client.post("/api/telephony/incoming", json={"call_id": "CALL-TEST-JSON-001"})
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert data["gather_digits"] is True
    assert "हिंदी" in data["message"] or "ಕನ್ನಡ" in data["message"]


def test_telephony_language_selection():
    """Verify pressing 2 selects Kannada and pressing 1 selects Hindi."""
    # Press 2 for Kannada
    res_kn = client.post(
        "/api/telephony/language",
        json={"call_id": "CALL-LANG-001", "digits": "2"}
    )
    assert res_kn.status_code == 200
    d_kn = res_kn.json()
    assert d_kn["language"] == "kn"
    assert "ಸ್ವಾಗತ" in d_kn["message"]

    # Press 1 for Hindi
    res_hi = client.post(
        "/api/telephony/language",
        json={"call_id": "CALL-LANG-002", "digits": "1"}
    )
    assert res_hi.status_code == 200
    d_hi = res_hi.json()
    assert d_hi["language"] == "hi"
    assert "स्वागत" in d_hi["message"]


def test_telephony_speech_turn_benefits_query():
    """Verify caller speech is routed through retrieval and answered in caller's language."""
    cid = "CALL-SPEECH-001"
    # 1. Establish session in Kannada
    client.post("/api/telephony/language", json={"call_id": cid, "digits": "2"})
    
    # 2. Ask why PF is deducted
    res = client.post(
        "/api/telephony/gather",
        json={"call_id": cid, "speech_text": "ನನ್ನ ಸಂಬಳದಲ್ಲಿ PF ಯಾಕೆ ಕಟ್ ಮಾಡುತ್ತಾರೆ?"}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["message"]) > 0
    assert data["language"] == "kn"
    assert data["gather_speech"] is True


def test_telephony_control_commands():
    """Verify 'repeat', 'slower', and 'talk to human' telephony control commands."""
    cid = "CALL-CTRL-001"
    # Select Kannada
    client.post("/api/telephony/language", json={"call_id": cid, "digits": "2"})
    
    # Question turn
    res_q = client.post(
        "/api/telephony/gather",
        json={"call_id": cid, "speech_text": "ನನ್ನ ಸಂಬಳದಲ್ಲಿ PF ಯಾಕೆ ಕಟ್ ಮಾಡುತ್ತಾರೆ?"}
    )
    original_answer = res_q.json()["message"]
    
    # Command: Repeat (ಮತ್ತೆ ಹೇಳಿ)
    res_repeat = client.post(
        "/api/telephony/gather",
        json={"call_id": cid, "speech_text": "ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ"}
    )
    assert res_repeat.status_code == 200
    assert original_answer in res_repeat.json()["message"]

    # Command: Slower (ನಿಧಾನವಾಗಿ)
    res_slower = client.post(
        "/api/telephony/gather",
        json={"call_id": cid, "speech_text": "ತುಂಬಾ ವೇಗವಾಗಿದೆ, ನಿಧಾನವಾಗಿ ಮಾತನಾಡಿ"}
    )
    assert res_slower.status_code == 200
    d_slower = res_slower.json()
    assert d_slower["speed"] < 0.80  # Pacing decreased

    # Command: Talk to Human / Supervisor (ಮಾನವ ಅಧಿಕಾರಿಯೊಂದಿಗೆ ಮಾತನಾಡಿ)
    res_human = client.post(
        "/api/telephony/gather",
        json={"call_id": cid, "speech_text": "ನನಗೆ ಮೇಲ್ವಿಚಾರಕರೊಂದಿಗೆ ಅಥವಾ ಮಾನವ ಅಧಿಕಾರಿಯೊಂದಿಗೆ ಮಾತನಾಡಬೇಕು"}
    )
    assert res_human.status_code == 200
    d_human = res_human.json()
    assert "ಮಾನವ HR ಅಧಿಕಾರಿಗೆ" in d_human["message"]
    
    # Verify session recorded human escalation
    sess_res = client.get(f"/api/telephony/session/{cid}")
    assert sess_res.status_code == 200
    sess = sess_res.json()["session"]
    assert sess["human_escalated"] is True
    assert sess["state"] == "HUMAN_ESCALATED"


def test_telephony_simulator_full_flow():
    """Verify the /api/telephony/simulate interactive endpoint used by the browser simulator."""
    cid = "CALL-SIM-TEST"
    # 1. Start call
    r1 = client.post("/api/telephony/simulate", json={"action": "start", "call_id": cid})
    assert r1.status_code == 200
    assert r1.json()["session"]["state"] == "MENU"

    # 2. Keypad digit '2' for Kannada
    r2 = client.post("/api/telephony/simulate", json={"action": "digit", "call_id": cid, "input": "2"})
    assert r2.status_code == 200
    assert r2.json()["session"]["language"] == "kn"
    assert r2.json()["session"]["state"] == "CONVERSATION"

    # 3. Speak question
    r3 = client.post("/api/telephony/simulate", json={"action": "speech", "call_id": cid, "input": "ನನ್ನ PF ಬ್ಯಾಲೆನ್ಸ್ ಹೇಗೆ ನೋಡುವುದು?"})
    assert r3.status_code == 200
    assert len(r3.json()["response"]["message"]) > 0

    # 4. Hangup
    r4 = client.post("/api/telephony/simulate", json={"action": "hangup", "call_id": cid})
    assert r4.status_code == 200
    assert r4.json()["session"]["state"] == "ENDED"


def test_spoken_indic_questions_hindi():
    """Verify 12 spoken-style Hindi queries map to verified canonical FAQ IDs."""
    cases = [
        ("पीएफ क्या होता है?", "SAH-001"),
        ("मेरी सैलरी से पीएफ क्यों कटता है?", "SAH-002"),
        ("पीएफ बैलेंस कैसे चेक करें?", "SAH-004"),
        ("यूएएन नंबर कैसे पता करें?", "SAH-006"),
        ("यूएएन पासवर्ड भूल गए तो क्या करें?", "SAH-435"),
        ("यूएएन एक्टिवेट कैसे करें?", "SAH-007"),
        ("सैलरी से पीएफ कट गया लेकिन पासबुक में नहीं दिखा", "SAH-008"),
        ("नौकरी बदलने पर पुराना पीएफ कैसे ट्रांसफर करें?", "SAH-011"),
        ("मेरा पीएफ क्लेम रिजेक्ट हो गया अब क्या करूं?", "SAH-025"),
        ("क्या मैं इलाज के लिए ईएसआईसी अस्पताल जा सकता हूँ?", "SAH-046"),
        ("ईएसआईसी में डिलीवरी या मैटरनिटी का क्या लाभ मिलता है?", "SAH-054"),
        ("पीएफ में नॉमिनी कैसे जोड़ें?", "SAH-017"),
    ]
    for q, expected_id in cases:
        res = client.post("/api/ask", json={"question": q, "language": "hi"})
        assert res.status_code == 200
        d = res.json()
        assert d["understood"] is True, f"Failed for {q}: {d}"
        assert d["faq_id"] == expected_id, f"Expected {expected_id}, got {d.get('faq_id')} for {q}"
        assert d["retrieval_score"] >= 0.60


def test_spoken_indic_questions_kannada():
    """Verify 12 spoken-style Kannada queries map to verified canonical FAQ IDs."""
    cases = [
        ("ಪಿಎಫ್ ಎಂದರೇನು ಮತ್ತು ಅದು ಯಾಕೆ ಇರುತ್ತದೆ?", "SAH-001"),
        ("ನನ್ನ ಸಂಬಳದಲ್ಲಿ ಪಿಎಫ್ ಯಾಕೆ ಕಟ್ ಮಾಡುತ್ತಾರೆ?", "SAH-002"),
        ("ನನ್ನ ಪಿಎಫ್ ಬ್ಯಾಲೆನ್ಸ್ ಹೇಗೆ ನೋಡುವುದು?", "SAH-004"),
        ("ನನ್ನ ಯುಎಎನ್ ನಂಬರ್ ಮರೆತುಹೋಗಿದೆ ಹೇಗೆ ತಿಳಿಯುವುದು?", "SAH-006"),
        ("ಯುಎಎನ್ ಪಾಸ್‌ವರ್ಡ್ ಮರೆತಿದೆ ಲಾಗಿನ್ ಆಗುತ್ತಿಲ್ಲ", "SAH-435"),
        ("ಯುಎಎನ್ ಮೊದಲ ಬಾರಿ ಆಕ್ಟಿವೇಟ್ ಮಾಡುವುದು ಹೇಗೆ?", "SAH-007"),
        ("ಪೇಸ್ಲಿಪ್‌ನಲ್ಲಿ ಪಿಎಫ್ ಕಟ್ ಆಗಿದೆ ಆದರೆ ಪಾಸ್‌ಬುಕ್‌ನಲ್ಲಿ ಬಂದಿಲ್ಲ", "SAH-008"),
        ("ಕೆಲಸ ಬದಲಾಯಿಸಿದಾಗ ಹಳೆಯ ಪಿಎಫ್ ವರ್ಗಾವಣೆ ಹೇಗೆ?", "SAH-011"),
        ("ನನ್ನ ಪಿಎಫ್ ಕ್ಲೇಮ್ ತಿರಸ್ಕರಿಸಲಾಗಿದೆ ಮುಂದೆ ಏನು ಮಾಡಬೇಕು?", "SAH-025"),
        ("ಚಿಕಿತ್ಸೆಗಾಗಿ ಇಎಸ್ಐಸಿ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಬಹುದೇ?", "SAH-046"),
        ("ಇಎಸ್ಐಸಿ ಹೆರಿಗೆ ಸೌಲಭ್ಯ ಹೇಗೆ ಪಡೆಯುವುದು?", "SAH-054"),
        ("ಪಿಎಫ್ ಖಾತೆಗೆ ನಾಮಿನಿ ಸೇರಿಸುವುದು ಹೇಗೆ?", "SAH-017"),
    ]
    for q, expected_id in cases:
        res = client.post("/api/ask", json={"question": q, "language": "kn"})
        assert res.status_code == 200
        d = res.json()
        assert d["understood"] is True, f"Failed for {q}: {d}"
        assert d["faq_id"] == expected_id, f"Expected {expected_id}, got {d.get('faq_id')} for {q}"
        assert d["retrieval_score"] >= 0.60


def test_spoken_indic_questions_tamil():
    """Verify 12 spoken-style Tamil queries map to verified canonical FAQ IDs."""
    cases = [
        ("பிஎஃப் என்றால் என்ன அது எதற்கு பயன்படுகிறது?", "SAH-001"),
        ("என் சம்பளத்தில் பிஎஃப் ஏன் பிடிக்கிறார்கள்?", "SAH-002"),
        ("என் பிஎஃப் பேலன்ஸ் எப்படி பார்ப்பது?", "SAH-004"),
        ("என் யுஏஎன் எண் மறந்துவிட்டது எப்படி கண்டுபிடிப்பது?", "SAH-006"),
        ("யுஏஎன் கடவுச்சொல் மறந்துவிட்டது லாகின் செய்ய முடியவில்லை", "SAH-435"),
        ("யுஏஎன் கணக்கை எப்படி ஆக்டிவேட் செய்வது?", "SAH-007"),
        ("சம்பளத்தில் பிஎஃப் பிடித்தம் ஆனால் பாஸ்புக்கில் வரவு இல்லை", "SAH-008"),
        ("வேலை மாறும்போது பழைய பிஎஃப் எப்படி மாற்றுவது?", "SAH-011"),
        ("என் பிஎஃப் கிளைம் நிராகரிக்கப்பட்டது அடுத்து என்ன செய்ய வேண்டும்?", "SAH-025"),
        ("சிகிச்சைக்காக இஎஸ்ஐ மருத்துவமனைக்கு செல்ல முடியுமா?", "SAH-046"),
        ("இஎஸ்ஐ மகப்பேறு பலன்கள் என்னென்ன கிடைக்கும்?", "SAH-054"),
        ("பிஎஃப் நாமினி எப்படி சேர்ப்பது?", "SAH-017"),
    ]
    for q, expected_id in cases:
        res = client.post("/api/ask", json={"question": q, "language": "ta"})
        assert res.status_code == 200
        d = res.json()
        assert d["understood"] is True, f"Failed for {q}: {d}"
        assert d["faq_id"] == expected_id, f"Expected {expected_id}, got {d.get('faq_id')} for {q}"
        assert d["confidence_score"] >= 0.80, f"Confidence too low for {q}: {d}"
        assert "match_mode" in d
        assert "lexical_score" in d


def test_spoken_indic_out_of_scope_rejection():
    """Verify 3 out-of-scope queries per language (9 total) are rejected gracefully."""
    oos_cases = [
        # Hindi
        ("चॉकलेट केक बनाने की विधि क्या है?", "hi"),
        ("कल दिल्ली का मौसम कैसा रहेगा?", "hi"),
        ("क्रिकेट वर्ल्ड कप का मैच कौन जीता?", "hi"),
        # Kannada
        ("ಚಾಕೊಲೇಟ್ ಕೇಕ್ ಮಾಡುವುದು ಹೇಗೆ?", "kn"),
        ("ನಾಳೆ ಬೆಂಗಳೂರಿನ ಹವಾಮಾನ ಹೇಗಿರುತ್ತದೆ?", "kn"),
        ("ಕ್ರಿಕೆಟ್ ಪಂದ್ಯದ ಸ್ಕೋರ್ ಎಷ್ಟು?", "kn"),
        # Tamil
        ("சாக்லேட் கேக் செய்வது எப்படி?", "ta"),
        ("நாளை சென்னையின் வானிலை எப்படி இருக்கும்?", "ta"),
        ("கிரிக்கெட் மேட்ச் ஸ்கோர் என்ன?", "ta"),
    ]
    for q, lang in oos_cases:
        res = client.post("/api/ask", json={"question": q, "language": lang})
        assert res.status_code == 200
        d = res.json()
        assert d["understood"] is False, f"Should be declined: {q}"
        assert d["scope"] == "out_of_scope", f"Should be out_of_scope: {q}"


def test_hard_near_miss_out_of_scope_rejection():
    """Verify 5 hard near-misses per language (15 total: income tax, LIC, bank loan, job search, coworker salary) are rejected."""
    near_misses = [
        # Hindi (5)
        ("मेरी सैलरी से इनकम टैक्स या टीडीएस कितना कटेगा?", "hi", "income_tax"),
        ("एलआईसी जीवन बीमा पॉलिसी का प्रीमियम कैसे जमा करें?", "hi", "lic_private_insurance"),
        ("मुझे बैंक से 50000 रुपये का पर्सनल लोन चाहिए, कैसे मिलेगा?", "hi", "bank_loan"),
        ("मुझे आपके वेयरहाउस में नई नौकरी चाहिए, वैकेंसी है क्या?", "hi", "job_search"),
        ("मेरे सुपरवाइजर या मैनेजर का वेतन कितना है मुझे बताओ?", "hi", "coworker_salary"),
        # Kannada (5)
        ("ನನ್ನ ಸಂಬಳದಿಂದ ಆದಾಯ ತೆರಿಗೆ ಅಥವಾ ಟಿಡಿಎಸ್ ಎಷ್ಟು ಕಡಿತವಾಗುತ್ತದೆ?", "kn", "income_tax"),
        ("ಎಲ್ಐಸಿ ಜೀವ ವಿಮೆ ಪಾಲಿಸಿಯ ಪ್ರೀಮಿಯಂ ಹೇಗೆ ಪಾವತಿಸುವುದು?", "kn", "lic_private_insurance"),
        ("ನನಗೆ ಬ್ಯಾಂಕಿನಿಂದ 50000 ರೂಪಾಯಿ ಪರ್ಸನಲ್ ಲೋನ್ ಬೇಕು, ಹೇಗೆ ಪಡೆಯುವುದು?", "kn", "bank_loan"),
        ("ನನಗೆ ನಿಮ್ಮ ವೇರ್‌ಹೌಸ್‌ನಲ್ಲಿ ಹೊಸ ಕೆಲಸ ಬೇಕು, ಖಾಲಿ ಹುದ್ದೆ ಇದೆಯೇ?", "kn", "job_search"),
        ("ನನ್ನ ಸೂಪರ್‌ವೈಸರ್ ಅಥವಾ ಮ್ಯಾನೇಜರ್ ಸಂಬಳ ಎಷ್ಟು ಎಂದು ತಿಳಿಸಿ?", "kn", "coworker_salary"),
        # Tamil (5)
        ("என் சம்பளத்தில் வருமான வரி அல்லது டிடிஎஸ் எவ்வளவு பிடித்தம் செய்யப்படும்?", "ta", "income_tax"),
        ("எல்ஐசி ஆயுள் காப்பீட்டு பாலிசியின் பிரீமியம் எப்படி செலுத்துவது?", "ta", "lic_private_insurance"),
        ("எனக்கு வங்கியில் 50000 ரூபாய் தனிநபர் கடன் வேண்டும், எப்படி பெறுவது?", "ta", "bank_loan"),
        ("எனக்கு உங்கள் கிடங்கில் புதிய வேலை வேண்டும், காலி பணியிடம் உள்ளதா?", "ta", "job_search"),
        ("என் மேற்பார்வையாளர் அல்லது மேலாளரின் சம்பளம் எவ்வளவு என்று சொல்லுங்கள்?", "ta", "coworker_salary"),
    ]
    for q, lang, expected_cat in near_misses:
        res = client.post("/api/ask", json={"question": q, "language": lang})
        assert res.status_code == 200
        d = res.json()
        assert d["understood"] is False, f"Near-miss should be declined: {q} -> {d}"
        assert d["scope"] == "out_of_scope", f"Near-miss should have scope out_of_scope: {q} -> {d}"
        assert d.get("out_of_scope_category") == expected_cat, f"Expected category {expected_cat}, got {d.get('out_of_scope_category')}"


def test_speech_transcripts_logging():
    """Verify that speech queries are logged to speech_transcripts.jsonl and accessible via API."""
    res = client.get("/api/speech-transcripts?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "transcripts" in data
    assert "total" in data
    assert data["total"] >= 1
    recent = data["transcripts"][-1]
    assert "timestamp" in recent
    assert "raw_transcript" in recent
    assert "match_mode" in recent


if __name__ == "__main__":
    pytest.main(["-v", __file__])
