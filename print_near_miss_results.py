"""Script to verify and print results for the 15 in-scope queries that must NOT be blocked by near-miss patterns.

Covers:
1. TDS on PF withdrawal (hi, kn, ta)
2. Income tax on PF withdrawal (hi, kn, ta)
3. Joining a new job, how do I transfer my PF (hi, kn, ta)
4. Is ESIC insurance (hi, kn, ta)
5. My supervisor says my PF is not deducted (hi, kn, ta)
"""
from main import detect_out_of_scope_near_miss, topic_from, KB
from normalization import full_normalize

QUERIES = [
    # 1. TDS on PF withdrawal
    {"intent": "TDS on PF withdrawal", "lang": "hi", "query": "पीएफ निकालने पर टीडीएस कटता है क्या?"},
    {"intent": "TDS on PF withdrawal", "lang": "kn", "query": "ಪಿಎಫ್ ಹಿಂಪಡೆಯುವಾಗ ಟಿಡಿಎಸ್ ಕಡಿತವಾಗುತ್ತದೆಯೇ?"},
    {"intent": "TDS on PF withdrawal", "lang": "ta", "query": "பிஎஃப் பணம் எடுக்கும் போது டிடிஎஸ் பிடித்தம் உண்டா?"},
    
    # 2. Income tax on PF withdrawal
    {"intent": "Income tax on PF withdrawal", "lang": "hi", "query": "पीएफ निकासी पर इनकम टैक्स नियम क्या हैं?"},
    {"intent": "Income tax on PF withdrawal", "lang": "kn", "query": "ಪಿಎಫ್ ಹಿಂಪಡೆಯುವಿಕೆಯ ಮೇಲೆ ಆದಾಯ ತೆರಿಗೆ ನಿಯಮಗಳೇನು?"},
    {"intent": "Income tax on PF withdrawal", "lang": "ta", "query": "பிஎஃப் எடுப்பதில் வருமான வரி விதிமுறைகள் என்ன?"},
    
    # 3. Joining a new job, how do I transfer my PF
    {"intent": "New job PF transfer", "lang": "hi", "query": "नई नौकरी में पुराना पीएफ कैसे ट्रांसफर करें?"},
    {"intent": "New job PF transfer", "lang": "kn", "query": "ಹೊಸ ಕೆಲಸ ಸೇರಿದಾಗ ಹಳೆಯ ಪಿಎಫ್ ವರ್ಗಾವಣೆ ಹೇಗೆ?"},
    {"intent": "New job PF transfer", "lang": "ta", "query": "புதிய வேலைக்கு மாறும் போது பழைய பிஎஃப் மாற்றுவது எப்படி?"},
    
    # 4. Is ESIC insurance
    {"intent": "Is ESIC insurance", "lang": "hi", "query": "क्या ईएसआईसी एक सरकारी बीमा है?"},
    {"intent": "Is ESIC insurance", "lang": "kn", "query": "ಇಎಸ್ಐಸಿ ಒಂದು ಸರ್ಕಾರಿ ವಿಮೆಯೇ?"},
    {"intent": "Is ESIC insurance", "lang": "ta", "query": "இஎஸ்ஐசி என்பது ஒரு அரசாங்க காப்பீடா?"},
    
    # 5. My supervisor says my PF is not deducted
    {"intent": "Supervisor says PF not deducted", "lang": "hi", "query": "सुपरवाइजर कहता है कि पीएफ नहीं कटेगा क्या यह सही है?"},
    {"intent": "Supervisor says PF not deducted", "lang": "kn", "query": "ಸೂಪರ್‌ವೈಸರ್ ಪಿಎಫ್ ಕಡಿತವಾಗುವುದಿಲ್ಲ ಎನ್ನುತ್ತಾರೆ ಇದು ಸರಿಯೇ?"},
    {"intent": "Supervisor says PF not deducted", "lang": "ta", "query": "மேற்பார்வையாளர் பிஎஃப் பிடிக்கப்படாது என்கிறார் இது சரியா?"},
]

def main():
    print("=" * 110)
    print(f"{'#':<3} | {'INTENT':<30} | {'LANG':<4} | {'STATUS':<8} | {'FAQ ID':<8} | {'CONF':<6} | {'MATCH MODE':<14} | {'ANSWER SNIPPET'}")
    print("=" * 110)
    
    all_passed = True
    for i, item in enumerate(QUERIES, 1):
        q = item["query"]
        lang = item["lang"]
        intent = item["intent"]
        norm_q = full_normalize(q)
        
        is_blocked, block_cat = detect_out_of_scope_near_miss(q, norm_q)
        top = topic_from(q)
        res = KB.retrieve(q, topic=top)
        
        meta = res.meta if hasattr(res, "meta") else {}
        faq_id = res.record.get("id") if res.record else "NONE"
        conf = meta.get("confidence_score", res.score if res else 0.0)
        mode = meta.get("match_mode", "unknown")
        
        # Get answer in language
        answers = res.record.get("answers", {}) if res.record else {}
        ans = answers.get(lang) or answers.get("en", "")
        ans_snippet = ans.replace("\n", " ")[:60] + "..." if len(ans) > 60 else ans
        
        status = "BLOCKED" if is_blocked else "PASS"
        if is_blocked:
            all_passed = False
            
        print(f"{i:<3} | {intent:<30} | {lang:<4} | {status:<8} | {faq_id:<8} | {conf:<6.3f} | {mode:<14} | {ans_snippet}")
        
    print("=" * 110)
    print(f"Overall result: {'ALL 15 IN-SCOPE QUERIES PASSED (UNBLOCKED)' if all_passed else 'SOME QUERIES BLOCKED'}")

if __name__ == "__main__":
    main()
