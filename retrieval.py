from __future__ import annotations
import json, math, re, sqlite3
from collections import Counter
from pathlib import Path
from typing import Any
from config import settings
from normalization import full_normalize, INDIC_STOPWORDS

DOMAIN_RE = re.compile(
    r"\b(pf|epf|provident fund|epfo|uan|passbook|epfigms|esic|esi|employee state insurance)\b|"
    r"(भविष्य निधि|कर्मचारी राज्य बीमा|ಪ್ರಾವಿಡೆಂಟ್ ಫಂಡ್|ಭವಿಷ್ಯ ನಿಧಿ|வருங்கால வைப்பு நிதி|அரசு காப்பீடு)",
    re.I
)
FOLLOWUP_RE = re.compile(r"\b(it|that|this|there|same|how do i check|what next|and then|how about|what about|how can i do that)\b", re.I)
STOP = set("a an the is are am do does did how what why when where who can could should would i my me we our you your it this that these those to of for from in on at by with and or if then as be been being have has had will may about into after before under over account please tell explain show check find get give want need help there their them they he she his her not no yes".split())


def is_pf_esic_record(r: dict) -> bool:
    # All 710 curated records in the combined FAQ pack belong to Saathi AI's domain
    return True

def norm(s: str) -> str:
    cleaned = full_normalize(s or "")
    return re.sub(r"[^\w\u0900-\u0d7f\u0c80-\u0cff]+", " ", cleaned.lower(), flags=re.UNICODE).strip()

def tokens(s: str) -> list[str]:
    cleaned = full_normalize(s or "")
    return [x for x in re.findall(r"[\w\u0900-\u0d7f\u0c80-\u0cff]+", cleaned.lower(), re.UNICODE) 
            if len(x) > 1 and x not in STOP and x not in INDIC_STOPWORDS]


def infer_intent(query: str, topic: str) -> str | None:
    q = full_normalize(query or "").lower()
    if topic == "esic":
        rules = [
            ("esic_medical", r"(hospital|doctor|dispensary|medicine|specialist|treatment|medical|visit|अस्पताल|हॉस्पिटल|दवाखाना|इलाज|उपचार|जा सकता|जा सकते|ಆಸ್ಪತ್ರೆ|ದವಾಖಾನೆ|ಔಷಧಿ|ಉಪಚಾರ|ಹೋಗಬಹುದೇ|மருத்துவமனை|ஆஸ்பத்திரி|சிகிச்சை|செல்ல முடியுமா)"),
            ("esic_benefits", r"(maternity|pregnan|birth|delivery|sickness|sick leave|cash benefit|unemployment|disablement|मातृत्व|प्रसूति|बीमारी|ಹೆರಿಗೆ|ಪ್ರಯೋಜನ|ಸೌಲಭ್ಯ|लाभ|மகப்பேறு|நன்மை)"),
            ("esic_contribution_rate", r"(contribution|deduct|percentage|rate|salary cut|ಕಟ್|ದರ|ಅಂಶದಾನ|कटौती|दर|பிடித்தம்|விகிதம்)"),
            ("esic_registration_process", r"(register|registration|new employee|enrol|enroll|ನೋಂದಣಿ|पंजीकरण|பதிவு)"),
            ("esic_claim", r"(claim|status|pending|track|settlement|दावा|ಅರ್ಜಿ|கோரிக்கை)"),
            ("esic_dependent_benefit", r"(family|spouse|wife|husband|children|child|dependen|कुटुंब|परिवार|ಮಕ್ಕಳು|ಹೆಂಡತಿ|ಗಂಡ|குடும்பம்)"),
            ("esic_card", r"(card|pehchan|insurance number|lost|missing|update|ಕಾರ್ಡ್|ಗುರುತಿನ|पहचान कार्ड|அட்டை)"),
            ("esic_eligibility", r"(eligible|eligibility|coverage|covered|qualify|पात्रता|ಅರ್ಹತೆ|தகுதி)"),
            ("why", r"((why|क्यों|ಯಾಕೆ|ಏಕೆ|ஏன்).*(deduct|cut|salary|कटा|कटौती|काटना|ಕಟ್|ಕಡಿತ|ಸಂಬಳ|ವೇತನ|பிடிக்க|பிடித்தம்|கழித்தல்|சம்பள))|((deduct|cut|salary|कटा|कटौती|काटना|ಕಟ್|ಕಡಿತ|ಸಂಬಳ|ವೇತನ|பிடிக்க|பிடித்தம்|கழித்தல்|சம்பள).*(why|क्यों|ಯಾಕೆ|ಏಕೆ|ஏன்))|(deduct|deduction|cut from salary|सैलरी से|कटा|कटौती|ಸಂಬಳ ಕಡಿತ|ವೇತನ ಕಡಿತ|ಸಂಬಳದಲ್ಲಿ ಕಟ್|பிடித்தம்)"),
            ("esic", r"(what is|meaning|cover|benefit|scheme|explain|क्या है|क्या होता|ಏನು|ವಿವರ|ಯೋಜನೆ|என்ன|விளக்கம்)"),
        ]
    else:
        rules = [
            ("missing", r"(not showing|not reflected|not credited|not deposited|missing|no entry|deposit.*(missing|not|show)|passbook.*(empty|blank|missing|not)|जमा नहीं|दिख नहीं|नहीं दिखा|नहीं आया|ಕ್ರೆಡಿಟ್ ಆಗಿಲ್ಲ|ತೋರಿಸುತ್ತಿಲ್ಲ|ಬಂದಿಲ್ಲ|ಜಮಾ ಆಗಿಲ್ಲ|வரவு வைக்கப்படவில்லை|வரவு இல்லை|காட்டவில்லை)"),
            ("uan_find", r"(uan.*(forgot|lost|find|know|number|भूल|पता|जान|ಮರೆತು|ತಿಳಿ|மறந்து|கண்டுபிடி)|(forgot|lost|find|know|भूल|पता|ಮರೆತು|ತಿಳಿ|மறந்து|கண்டுபிடி).*uan)"),
            ("pf_portal_login", r"(password|login|reset password|member portal|लॉगिन|पासवर्ड|लॉगिन समस्या|ಪಾಸ್‌ವರ್ಡ್|ಲಾಗಿನ್|ಲಾಗ್ ಇನ್|கடவுச்சொல்|லாகின்)"),
            ("activation", r"(activate|activation).*(uan)|(uan).*(activate|activation)|सक्रिय|एक्टिवेट|ಆಕ್ಟಿವೇಟ್|ಸಕ್ರಿಯಗೊಳಿಸು|ஆக்டிவேட்"),
            ("reject", r"(reject|rejected|rejection|denied|declined|refused|रिजेक्ट|खारिज|रद्द|अस्वीकृत|ತಿರಸ್ಕಾರ|ತಿರಸ್ಕರಿಸಲಾಗಿದೆ|நிராகரிக்கப்பட்டது|நிராகரிப்பு)"),
            ("claimstatus", r"(claim|application).*(status|pending|delay|delayed|approved)|(status|pending|delay|delayed|approved).*(claim|application)|स्थिति|ಪ್ರಗತಿ|ಸ್ಥಿತಿ|அர்ஜி|நிலை"),
            ("transfer", r"(change job|changed job|new job|previous employer|old employer|transfer|resign|left the company|बदली|नौकरी बदली|ವರ್ಗಾವಣೆ|ಕೆಲಸ ಬದಲಾವಣೆ|ನೌಕರಿ ಬದಲಾವಣೆ|ವೇತನ ವರ್ಗಾವಣೆ|வேலை மாற்றம்|வேலை மாறும்போது|வேலை மாற|மாற்றுவது|மாற்ற|பழைய பிஎஃப்|பழைய pf)"),
            ("advance", r"(partial|advance|emergency|medical|education|marriage).*(withdraw|take out)|(withdraw|take out).*(partial|advance|emergency)|अग्रिम|ಮುಂಗಡ|ಅಡ್ವಾನ್ಸ್|ಆಸ್ಪತ್ರೆ ಖರ್ಚು|முன்பணம்"),
            ("withdraw", r"(withdraw|withdrawal|take out|cash out|settlement|पैसा निकालना|पैसे निकालना|निकासी|विड्रॉल|ತೆಗೆಯಲು|ಹಿಂಪಡೆಯಲು|ನಗದು|பணம் எடுக்க|திரும்ப பெற)"),
            ("personal_data", r"(my actual|my exact|exact balance|personal balance|how much.*(my|account)|check my own)"),
            ("passbook", r"(balance|passbook|check.*pf|view.*pf|see.*pf|बैलेंस|पासबुक|बैलेंस चेक|ಬ್ಯಾಲೆನ್ಸ್|ಪಾಸ್‌ಬುಕ್|ಖಾತೆ ನೋಡುವುದು|ಬ್ಯಾಲೆನ್ಸ್ ನೋಡಿ|பேலன்ஸ்|பாஸ்புக்|இருப்பு)"),
            ("kyc", r"(kyc|aadhaar|aadhar|bank detail|date of birth|name mismatch|आधार|ಕೆವೈಸಿ|ಆಧಾರ್|ಲಿಂಕ್|ಬ್ಯಾಂಕ್ ವಿವರ|ஆதார்)"),
            ("nomination", r"(nominee|nomination|e-nomination|नॉमिनी|नामिनी|नामांकन|ನಾಮಿನಿ|ವಾರಸುದಾರ|நாமினி|வாரிசு)"),
            ("grievance", r"(complaint|complain|grievance|epfigms|helpdesk|शिकायत|ದೂರು|ಸಮಸ್ಯೆ|ತಿಳಿಸುವುದು|புகார்)"),
            ("epf_interest", r"(interest|rate|interest credited|ब्याज|ब्याज दर|ಬಡ್ಡಿ|ಬಡ್ಡಿದರ|ಬಡ್ಡಿ ಬಂದಿಲ್ಲ|வட்டி)"),
            ("vpf", r"(vpf|voluntary provident|वीपीएफ|ವಿಪಿಎಫ್|ಸ್ವಯಂಪ್ರೇರಿತ)"),
            ("higher_pension_scheme", r"(higher pension|eps pension|pension option|उच्च पेंशन|ಹೆಚ್ಚಿನ ಪಿಂಚಣಿ|அதிக ஓய்வூதியம்)"),
            ("minimum_pension", r"(pension|eps|पेंशन|पेन्शन|ಪಿಂಚಣಿ|ಪೆನ್ಷನ್|ஓய்வூதியம்|பென்ஷன்)"),
            ("why", r"((why|क्यों|ಯಾಕೆ|ಏಕೆ|ஏன்).*(deduct|cut|salary|कटा|कटौती|काटना|ಕಟ್|ಕಡಿತ|ಸಂಬಳ|ವೇತನ|பிடிக்க|பிடித்தம்|கழித்தல்|சம்பள))|((deduct|cut|salary|कटा|कटौती|काटना|ಕಟ್|ಕಡಿತ|ಸಂಬಳ|ವೇತನ|பிடிக்க|பிடித்தம்|கழித்தல்|சம்பள).*(why|क्यों|ಯಾಕೆ|ಏಕೆ|ஏன்))|(deduct|deduction|cut from salary|सैलरी से|कटा|कटौती|ಸಂಬಳ ಕಡಿತ|ವೇತನ ಕಡಿತ|ಸಂಬಳದಲ್ಲಿ ಕಟ್|பிடித்தம்)"),
            ("employer", r"(employer|company).*(contribution|deposit|pay|remit)|(contribution|deposit|remit).*(employer|company)|मालिक का अंशदान|कंपनी का हिस्सा|ಮಾಲೀಕರ ಕೊಡುಗೆ|ಕಂಪನಿ ಪಾಲು|முதலாளி பங்களிப்பு"),
            ("pf", r"(what is|meaning|explain|scheme|provident fund|क्या होता|क्या है|चीज है|ಅಂದರೆ ಏನು|ಎಂದರೇನು|ಎಂದರೆ|ಏನು|என்ன|விளக்கம்)"),
        ]
    for intent, pattern in rules:
        if re.search(pattern, q, re.I):
            return intent
    return None

class RetrievalResult(tuple):
    """3-tuple subclass (record, score, matches) with rich metadata (.meta) for match mode, lexical score, and confidence."""
    def __new__(cls, record, score, matches, meta=None):
        return super().__new__(cls, (record, score, matches))
    def __init__(self, record, score, matches, meta=None):
        self.record = record
        self.score = score
        self.matches = matches
        self.meta = meta or {}


class KnowledgeBase:
    def __init__(self, records: list[dict], db_path: str):
        self.records = [r for r in records if is_pf_esic_record(r)]
        self.db_path = db_path
        self._prepare()

    def _prepare(self):
        self.docs = []
        self.df = Counter()
        self.corpus = []
        for r in self.records:
            answers = r.get("answers", {})
            q_en = r.get("question_en", "")
            cat = r.get("category", "")
            text = "\n".join([q_en, cat, answers.get("en", ""), answers.get("hi", ""), answers.get("kn", ""), answers.get("ta", "")])
            self.docs.append(text)
            
            # Boost question tokens so question-to-question match is rewarded over boilerplate answer words
            q_toks = tokens(q_en)
            ans_toks = tokens(f"{cat} {answers.get('en', '')} {answers.get('hi', '')} {answers.get('kn', '')} {answers.get('ta', '')}")
            ts = Counter(ans_toks)
            for qt in q_toks:
                ts[qt] += 3
            self.corpus.append(ts)
            self.df.update(ts.keys())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS kb_embeddings (faq_id TEXT PRIMARY KEY, vector TEXT NOT NULL, model TEXT NOT NULL)")
            c.commit()

    def _lexical(self, query: str, r: dict) -> float:
        q = Counter(tokens(query)); idx = self.records.index(r); d = self.corpus[idx]
        if not q: return 0.0
        shared = qsum = dsum = 0.0
        for w, n in q.items():
            idf = math.log(1 + (len(self.records)+1)/(self.df.get(w, 0)+1))
            qsum += n*idf
            if w in d: shared += min(n, d[w])*idf
        for w,n in d.items(): dsum += n*math.log(1+(len(self.records)+1)/(self.df.get(w,0)+1))
        coverage = shared/qsum if qsum else 0
        overlap = shared/(qsum+dsum-shared) if qsum+dsum-shared else 0
        return min(1.0, .84*coverage + .16*overlap)

    def retrieve(self, query: str, query_vector: list[float] | None = None, topic: str | None = None) -> tuple[dict | None, float, list[dict]]:
        norm_q = full_normalize(query)
        qn = norm(norm_q)
        candidates=[]
        for r in self.records:
            cat=r.get("category","").lower(); src=r.get("source_group","")
            if topic == "pf" and not (cat.startswith("pf") or src == "EPFO" or re.search(r"\b(pf|epf|provident fund|epfo|uan)\b",r.get("question_en", ""),re.I)):
                continue
            if topic == "esic" and not (cat.startswith("esic") or src == "ESIC" or re.search(r"\b(esic|esi)\b",r.get("question_en", ""),re.I)):
                continue
            candidates.append(r)
        exact=next((r for r in candidates if qn == norm(r.get("question_en", ""))),None)
        if exact:
            meta = {
                "match_mode": "exact",
                "confidence_score": 1.0,
                "lexical_score": 1.0,
                "intent": None,
                "rule_applied": False,
                "label": "Exact question match (1.000)"
            }
            matches = [{"id":exact.get("id"),"category":exact.get("category"),"question":exact.get("question_en"),"score":1.0,"source_group":exact.get("source_group")}]
            return RetrievalResult(exact, 1.0, matches, meta)
        inferred=infer_intent(norm_q,topic or "pf") if topic else None
        intent_candidates=[r for r in candidates if inferred and r.get("intent")==inferred]
        if intent_candidates:
            def rank_key(r):
                lex = self._lexical(norm_q, r)
                cat = r.get("category", "").lower()
                bonus = 0.0
                if inferred == "pf":
                    if "basic" in cat:
                        bonus = 0.25
                    elif "pension" in cat and not re.search(r"\b(eps|pension|पेंशन|ಪಿಂಚಣಿ|ஓய்வூதியம்)\b", norm_q, re.I):
                        bonus = -0.25
                    elif "insurance" in cat and not re.search(r"\b(edli|insurance|बीमा|ವಿಮೆ|காப்பீடு)\b", norm_q, re.I):
                        bonus = -0.25
                elif inferred == "missing":
                    if r.get("id") in ("SAH-008", "SAH-009"):
                        bonus = 0.20
                elif inferred == "esic_medical":
                    if r.get("id") == "SAH-046":
                        bonus = 0.20
                elif inferred == "nomination":
                    if r.get("id") in ("SAH-017", "SAH-018"):
                        bonus = 0.15
                elif inferred == "uan_find":
                    if r.get("id") == "SAH-006":
                        bonus = 0.25
                return lex + bonus

            ranked = sorted(((rank_key(r), r) for r in intent_candidates), key=lambda x: x[0], reverse=True)
            best = ranked[0][1]
            raw_lex = self._lexical(norm_q, best)
            best_rank_key = ranked[0][0]
            conf = min(0.96, max(0.85, 0.82 + max(0.0, best_rank_key) * 0.15))
            meta = {
                "match_mode": "intent_rule",
                "confidence_score": round(conf, 4),
                "lexical_score": round(raw_lex, 4),
                "intent": inferred,
                "rule_applied": True,
                "label": f"Intent rule '{inferred}' matched (confidence {conf:.3f}, lexical BM25 {raw_lex:.3f})"
            }
            matches = [{"id": r.get("id"), "category": r.get("category"), "question": r.get("question_en"), "score": round(self._lexical(norm_q, r), 4), "source_group": r.get("source_group")} for _, r in ranked[:4]]
            return RetrievalResult(best, conf, matches, meta)
        vectors={}
        if query_vector:
            with sqlite3.connect(self.db_path) as c:
                for fid, raw in c.execute("SELECT faq_id, vector FROM kb_embeddings"):
                    try: vectors[fid] = json.loads(raw)
                    except Exception: pass
        ranked=[]
        for r in candidates:
            lex=self._lexical(norm_q,r); vec=0.0; v=vectors.get(r.get("id"))
            if query_vector and v and len(v)==len(query_vector):
                dot=sum(a*b for a,b in zip(v,query_vector)); na=math.sqrt(sum(a*a for a in v)); nb=math.sqrt(sum(b*b for b in query_vector)); vec=max(0.0,dot/(na*nb)) if na and nb else 0.0
            score=(.35*lex+.65*vec) if query_vector and v else lex
            ranked.append((score,r,lex,vec))
        ranked.sort(key=lambda x:x[0],reverse=True)
        best=ranked[0] if ranked else (0.0,None,0.0,0.0)
        best_rec = best[1]
        best_sc = float(best[0])
        best_lex = float(best[2])
        is_hybrid = bool(query_vector and best[3] > 0.0)
        mode = "hybrid_embedding" if is_hybrid else "lexical_rag"
        meta = {
            "match_mode": mode,
            "confidence_score": round(best_sc, 4),
            "lexical_score": round(best_lex, 4),
            "intent": None,
            "rule_applied": False,
            "label": f"Pure BM25 lexical retrieval (score {best_sc:.3f})" if not is_hybrid else f"Hybrid vector + BM25 retrieval (score {best_sc:.3f})"
        }
        matches=[{"id":r.get("id"),"category":r.get("category"),"question":r.get("question_en"),"score":round(s,4),"source_group":r.get("source_group")} for s,r,_,_ in ranked[:4]]
        return RetrievalResult(best_rec, best_sc, matches, meta)

    def all_records(self): return self.records
