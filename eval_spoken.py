"""Saathi AI — Regression Evaluation Suite for Spoken Queries.

NOTE: These are regression tests (the system has been tuned on these cases).
A separate, un-tuned held-out evaluation set is available in `eval_heldout.json`.
"""
from __future__ import annotations

import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

TEST_CASES = {
    "hi": [
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
    ],
    "kn": [
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
    ],
    "ta": [
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
}

GENERAL_OUT_OF_SCOPE = {
    "hi": [
        "चॉकलेट केक बनाने की विधि क्या है?",
        "कल दिल्ली का मौसम कैसा रहेगा?",
        "क्रिकेट वर्ल्ड कप का मैच कौन जीता?"
    ],
    "kn": [
        "ಚಾಕೊಲೇಟ್ ಕೇಕ್ ಮಾಡುವುದು ಹೇಗೆ?",
        "ನಾಳೆ ಬೆಂಗಳೂರಿನ ಹವಾಮಾನ ಹೇಗಿರುತ್ತದೆ?",
        "ಕ್ರಿಕೆಟ್ ಪಂದ್ಯದ ಸ್ಕೋರ್ ಎಷ್ಟು?"
    ],
    "ta": [
        "சாக்லேட் கேக் செய்வது எப்படி?",
        "நாளை சென்னையின் வானிலை எப்படி இருக்கும்?",
        "கிரிக்கெட் மேட்ச் ஸ்கோர் என்ன?"
    ]
}

HARD_NEAR_MISS_OUT_OF_SCOPE = {
    "hi": [
        ("मेरी सैलरी से इनकम टैक्स या टीडीएस कितना कटेगा?", "income_tax"),
        ("एलआईसी जीवन बीमा पॉलिसी का प्रीमियम कैसे जमा करें?", "lic_private_insurance"),
        ("मुझे बैंक से 50000 रुपये का पर्सनल लोन चाहिए, कैसे मिलेगा?", "bank_loan"),
        ("मुझे आपके वेयरहाउस में नई नौकरी चाहिए, वैकेंसी है क्या?", "job_search"),
        ("मेरे सुपरवाइजर या मैनेजर का वेतन कितना है मुझे बताओ?", "coworker_salary"),
    ],
    "kn": [
        ("ನನ್ನ ಸಂಬಳದಿಂದ ಆದಾಯ ತೆರಿಗೆ ಅಥವಾ ಟಿಡಿಎಸ್ ಎಷ್ಟು ಕಡಿತವಾಗುತ್ತದೆ?", "income_tax"),
        ("ಎಲ್ಐಸಿ ಜೀವ ವಿಮೆ ಪಾಲಿಸಿಯ ಪ್ರೀಮಿಯಂ ಹೇಗೆ ಪಾವತಿಸುವುದು?", "lic_private_insurance"),
        ("ನನಗೆ ಬ್ಯಾಂಕಿನಿಂದ 50000 ರೂಪಾಯಿ ಪರ್ಸನಲ್ ಲೋನ್ ಬೇಕು, ಹೇಗೆ ಪಡೆಯುವುದು?", "bank_loan"),
        ("ನನಗೆ ನಿಮ್ಮ ವೇರ್‌ಹೌಸ್‌ನಲ್ಲಿ ಹೊಸ ಕೆಲಸ ಬೇಕು, ಖಾಲಿ ಹುದ್ದೆ ಇದೆಯೇ?", "job_search"),
        ("ನನ್ನ ಸೂಪರ್‌ವೈಸರ್ ಅಥವಾ ಮ್ಯಾನೇಜರ್ ಸಂಬಳ ಎಷ್ಟು ಎಂದು ತಿಳಿಸಿ?", "coworker_salary"),
    ],
    "ta": [
        ("என் சம்பளத்தில் வருமான வரி அல்லது டிடிஎஸ் எவ்வளவு பிடித்தம் செய்யப்படும்?", "income_tax"),
        ("எல்ஐசி ஆயுள் காப்பீட்டு பாலிசியின் பிரீமியம் எப்படி செலுத்துவது?", "lic_private_insurance"),
        ("எனக்கு வங்கியில் 50000 ரூபாய் தனிநபர் கடன் வேண்டும், எப்படி பெறுவது?", "bank_loan"),
        ("எனக்கு உங்கள் கிடங்கில் புதிய வேலை வேண்டும், காலி பணியிடம் உள்ளதா?", "job_search"),
        ("என் மேற்பார்வையாளர் அல்லது மேலாளரின் சம்பளம் எவ்வளவு என்று சொல்லுங்கள்?", "coworker_salary"),
    ]
}


def run_regression_suite():
    print("==================================================")
    print("REGRESSION TESTS (Tuned on these)")
    print("==================================================")

    total = 0
    passed = 0
    failures = []

    for lang, cases in TEST_CASES.items():
        print(f"\n--- Language: {lang.upper()} (In-Scope Regression) ---")
        for q, expected_id in cases:
            total += 1
            res = client.post("/api/ask", json={"question": q, "language": lang})
            data = res.json()
            matched_id = data.get("faq_id")
            understood = data.get("understood")
            conf_score = data.get("confidence_score", data.get("retrieval_score", 0.0))
            lex_score = data.get("lexical_score", 0.0)
            mode = data.get("match_mode", "unknown")
            
            ok = understood is True and matched_id == expected_id
            if ok:
                passed += 1
                print(f"PASS: [{matched_id}] conf={conf_score:.3f} lex={lex_score:.3f} mode={mode} | {q}")
            else:
                failures.append({
                    "lang": lang,
                    "query": q,
                    "expected": expected_id,
                    "actual": matched_id,
                    "understood": understood,
                    "conf_score": conf_score,
                    "lex_score": lex_score,
                    "mode": mode
                })
                print(f"FAIL: Got [{matched_id}] (understood={understood}, conf={conf_score:.3f}), Expected [{expected_id}] | {q}")

    print("\n==================================================")
    print("TESTING GENERAL OUT-OF-SCOPE (MUST REJECT)")
    print("==================================================")

    oos_total = 0
    oos_passed = 0
    for lang, questions in GENERAL_OUT_OF_SCOPE.items():
        print(f"\n--- Language: {lang.upper()} (General Out-of-Scope) ---")
        for q in questions:
            oos_total += 1
            res = client.post("/api/ask", json={"question": q, "language": lang})
            data = res.json()
            understood = data.get("understood")
            scope = data.get("scope")
            if understood is False and scope == "out_of_scope":
                oos_passed += 1
                print(f"PASS: Correctly rejected (understood=False, scope=out_of_scope) | {q}")
            else:
                print(f"FAIL: Not rejected properly (understood={understood}, scope={scope}) | {q}")

    print("\n==================================================")
    print("TESTING HARD OUT-OF-SCOPE NEAR-MISSES (MUST REJECT)")
    print("==================================================")

    nm_total = 0
    nm_passed = 0
    for lang, cases in HARD_NEAR_MISS_OUT_OF_SCOPE.items():
        print(f"\n--- Language: {lang.upper()} (Hard Near-Misses) ---")
        for q, expected_cat in cases:
            nm_total += 1
            res = client.post("/api/ask", json={"question": q, "language": lang})
            data = res.json()
            understood = data.get("understood")
            scope = data.get("scope")
            cat = data.get("out_of_scope_category")
            if understood is False and scope == "out_of_scope":
                nm_passed += 1
                print(f"PASS: Near-miss blocked [{cat or expected_cat}] | {q}")
            else:
                print(f"FAIL: Near-miss leaked through (understood={understood}, scope={scope}) | {q}")

    print("\n==================================================")
    print(f"SUMMARY: In-scope regression passed:       {passed}/{total}")
    print(f"SUMMARY: General out-of-scope passed:     {oos_passed}/{oos_total}")
    print(f"SUMMARY: Hard near-miss out-of-scope:     {nm_passed}/{nm_total}")
    print(f"TOTAL EVALUATION RESULT:                  {passed + oos_passed + nm_passed}/{total + oos_total + nm_total}")
    print("==================================================")

    return failures


if __name__ == "__main__":
    run_regression_suite()
