#!/usr/bin/env python3
"""
Saathi AI local demo backend
- Serves the original Saathi AI HTML prototype.
- Answers by retrieving from the reconciled 710-record multilingual FAQ knowledge base.
- Saves demo HR tickets in SQLite only after explicit consent.
- Does NOT connect to EPFO, ESIC, payroll, or an employer HR system.
Standard library only: python server.py
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from difflib import get_close_matches
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

BASE = Path(__file__).resolve().parent
HTML_PATH = BASE / "saathi_ai_trained.html"
KB_PATH = BASE / "saathi_ai_710_knowledge_base.json"
DB_PATH = BASE / "saathi_demo_tickets.sqlite3"
THRESHOLD = 0.80
LANGS = {"hi", "kn", "ta"}

UNCLEAR = {
    "hi": "माफ़ कीजिए, आपका सवाल स्पष्ट रूप से समझ नहीं आया। कृपया इसे दूसरे शब्दों में पूछें या सुझाए गए सवालों में से चुनें।",
    "kn": "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಬೇರೆ ರೀತಿಯಲ್ಲಿ ಕೇಳಿ ಅಥವಾ ಸೂಚಿಸಿದ ಪ್ರಶ್ನೆಗಳಲ್ಲಿ ಒಂದನ್ನು ಆಯ್ಕೆಮಾಡಿ.",
    "ta": "மன்னிக்கவும், உங்கள் கேள்வியை தெளிவாகப் புரிந்துகொள்ள முடியவில்லை. வேறு வார்த்தைகளில் கேளுங்கள் அல்லது பரிந்துரைக்கப்பட்ட கேள்விகளில் ஒன்றைத் தேர்ந்தெடுக்கவும்.",
}

STOP = set(("a an the is are am do does did how what why when where who can could should would i my me we our you your it this that these those to of for from in on at by with and or if then else as be been being have has had will shall may might about into after before under over account please tell explain show check find get give want need help there their them they he she his her not no yes").split())

ALIASES = {
    "pf": ["provident", "epf", "fund"], "provident": ["pf", "epf"], "epf": ["pf", "provident"],
    "deduct": ["deduction", "cut", "salary"], "deduction": ["deduct", "cut", "payslip"],
    "cut": ["deduct", "deduction", "salary"], "salary": ["pay", "payslip", "wage"],
    "pay": ["salary", "payslip", "wage"], "payslip": ["salary", "pay"],
    "balance": ["passbook", "account"], "passbook": ["balance", "credit", "entry"],
    "credit": ["deposit", "credited", "contribution"], "deposit": ["credit", "contribution", "remittance"],
    "missing": ["not", "show", "entry", "credit", "deposit"],
    "transfer": ["job", "move", "changed", "company", "employment"],
    "move": ["transfer", "job", "change"], "moved": ["transfer", "job", "change"],
    "changed": ["transfer", "job", "change"], "change": ["transfer", "job"],
    "job": ["transfer", "employment", "company"], "jobs": ["job", "transfer"],
    "company": ["employer", "job", "workplace"], "employer": ["company", "job"],
    "withdraw": ["withdrawal", "claim", "settlement", "cash", "take"],
    "withdrawal": ["withdraw", "claim"], "claim": ["withdraw", "application"],
    "rejected": ["reject", "denied", "declined", "claim"], "declined": ["reject", "rejected", "claim"],
    "denied": ["reject", "rejected"], "reject": ["rejected", "declined"],
    "esic": ["esi", "insurance", "medical", "benefit"], "esi": ["esic", "insurance"],
    "spouse": ["family", "dependant", "dependent"], "wife": ["family", "spouse"],
    "husband": ["family", "spouse"], "children": ["family", "dependant"],
    "child": ["family", "dependant"], "kids": ["children", "family"],
    "dependant": ["family", "dependent"], "dependent": ["family", "dependant"],
    "family": ["spouse", "children", "dependant"],
    "die": ["death", "family", "nominee"], "died": ["death", "family", "nominee"],
    "death": ["die", "family", "nominee"], "nominee": ["nomination", "family", "death"],
    "nomination": ["nominee", "family"], "complain": ["grievance", "complaint", "issue"],
    "complaint": ["grievance", "complain"], "grievance": ["complaint", "issue"],
    "wrong": ["incorrect", "error", "mismatch", "deduction", "discrepancy"],
    "incorrect": ["wrong", "error", "mismatch"], "mismatch": ["wrong", "incorrect", "kyc"],
    "medical": ["treatment", "hospital", "dispensary"], "treatment": ["medical", "hospital"],
    "hospital": ["medical", "treatment", "esic"], "sickness": ["sick", "medical", "benefit"],
    "accident": ["injury", "workplace", "report"], "injury": ["accident", "workplace"],
    "maternity": ["pregnancy", "benefit"], "otp": ["password", "security", "fraud"],
    "password": ["otp", "security"], "security": ["otp", "password"],
    "card": ["pehchan", "insurance", "esic"], "pehchan": ["card", "esic"],
    "uan": ["universal", "account", "number"], "activation": ["activate", "uan"],
    "activate": ["activation", "uan"], "tax": ["income", "withdrawal"],
    "ticket": ["hr", "request", "followup"], "manager": ["supervisor", "hr"],
    "supervisor": ["manager", "hr"], "private": ["privacy", "confidential"],
    "confidential": ["privacy", "private", "hr"], "different": ["change", "new", "job"],
    "new": ["change", "job", "employer"], "old": ["previous", "transfer"],
    "account": ["uan", "passbook"], "number": ["uan", "member"],
    "forgot": ["find", "recover", "uan"], "take": ["withdraw", "advance"],
    "money": ["fund", "balance", "withdrawal"], "bill": ["medical", "expense", "treatment"],
    "bills": ["medical", "expense", "treatment"], "rate": ["interest", "contribution"],
    "sent": ["deposit", "remittance", "contribution"], "payment": ["contribution", "deposit"],
    "paid": ["deposit", "contribution"], "balence": ["balance"], "balnce": ["balance"],
    "hospitol": ["hospital"], "medcal": ["medical"], "dedcuted": ["deducted", "deduction"],
}

IRREGULAR = {
    "moved": "move", "changed": "change", "withdrawal": "withdraw",
    "withdrawn": "withdraw", "withdrawing": "withdraw", "rejected": "reject",
    "declined": "reject", "denied": "reject", "complained": "complain",
    "complaining": "complain", "died": "death", "dying": "death",
    "deducted": "deduct", "deducting": "deduct", "deposited": "deposit",
    "credited": "credit", "kids": "child", "children": "child",
}

def norm_question(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def tokenize(s: str) -> list[str]:
    raw = re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip().split()
    out = []
    for word in raw:
        if word in STOP:
            continue
        w = IRREGULAR.get(word, word)
        if w.endswith("ies") and len(w) > 5:
            w = w[:-3] + "y"
        elif w.endswith("ing") and len(w) > 5:
            w = w[:-3]
        elif w.endswith("ed") and len(w) > 4:
            w = w[:-2]
        elif w.endswith("s") and len(w) > 4:
            w = w[:-1]
        out.append(w)
    return out

def features(s: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for raw in tokenize(s):
        w = raw
        if w in ("provident", "epf"):
            w = "pf"
        if w == "esi":
            w = "esic"
        out[w] = max(out.get(w, 0), 1.0)
        for alias in ALIASES.get(w, []):
            out[alias] = max(out.get(alias, 0), 0.38)
    return out

# Rules are only used to select a topic already present in the uploaded knowledge base.
ADVANCED_RULES = [
    ("epf_interest_rate", r"\b(pf|epf|provident)\b.*\b(interest rate|rate of interest|current rate|annual rate)\b"),
    ("epf_interest_rate", r"\b(interest rate|rate of interest)\b.*\b(pf|epf|provident)\b"),
    ("interest_credit_delay", r"\b(pf|epf|provident)\b.*\b(interest|credited)\b.*\b(not credited|not added|delay|late)\b"),
    ("epf_interest", r"\b(pf|epf|provident)\b.*\b(interest|interest calculation)\b"),
    ("vpf", r"\b(vpf|voluntary provident fund)\b"),
    ("wage_ceiling", r"\b(pf|epf|provident)\b.*\b(wage ceiling|salary ceiling|basic wage limit|contribution ceiling)\b"),
    ("eligibility_new_employee", r"\b(pf|epf|provident)\b.*\b(probation|new employee|new joiner|joining|first job)\b"),
    ("interns_contract", r"\b(pf|epf|provident)\b.*\b(intern|trainee|contract staff|contract worker|temporary worker)\b"),
    ("account_merge", r"\b(pf|epf|provident|uan)\b.*\b(merge|combine|one account|two accounts|multiple accounts)\b"),
    ("inoperative_account", r"\b(pf|epf|provident)\b.*\b(inoperative|inactive account|dormant account)\b"),
    ("unclaimed_deposit", r"\b(pf|epf|provident)\b.*\b(unclaimed|unclaimed deposit|unclaimed amount)\b"),
    ("pf_number_format", r"\b(uan|member id)\b.*\b(difference|format|number)\b"),
    ("aadhaar_seeding_deadline", r"\b(aadhaar|aadhar)\b.*\b(seeding|linking|deadline|last date)\b"),
    ("pf_joint_declaration", r"\b(joint declaration|joint correction)\b"),
    ("multiple_employers_same_time", r"\b(two jobs|two employers|multiple employers|simultaneous jobs|both jobs)\b.*\b(pf|epf|provident)\b"),
    ("multiple_employers_same_time", r"\b(pf|epf|provident)\b.*\b(two jobs|two employers|multiple employers|simultaneous jobs|both jobs)\b"),
    ("pf_nps_comparison", r"\b(epf|pf|provident)\b.*\b(nps|national pension)\b"),
    ("form19", r"\b(form[\s-]*19)\b"), ("form10c", r"\b(form[\s-]*10c)\b"),
    ("form31", r"\b(form[\s-]*31)\b"), ("form11", r"\b(form[\s-]*11)\b"),
    ("composite_claim", r"\b(composite claim|combined claim form|composite form)\b"),
    ("pf_home_loan", r"\b(pf|epf|provident)\b.*\b(home loan|house purchase|buy a house|build a house|housing)\b"),
    ("pf_medical_withdrawal", r"\b(pf|epf|provident)\b.*\b(medical|hospital|treatment|health emergency|medical bills)\b"),
    ("pf_education_withdrawal", r"\b(pf|epf|provident)\b.*\b(education|school|college|tuition|child education)\b"),
    ("pf_marriage_withdrawal", r"\b(pf|epf|provident)\b.*\b(marriage|wedding)\b"),
    ("pf_unemployment_withdrawal", r"\b(pf|epf|provident)\b.*\b(unemployed|jobless|lost my job|without a job)\b"),
    ("pf_covid_advance", r"\b(pf|epf|provident)\b.*\b(covid|pandemic)\b"),
    ("pf_app", r"\b(umang|epfo app|mobile app)\b"),
    ("pf_portal_login", r"\b(pf|epfo)\b.*\b(login|log in|sign in|password|portal error)\b"),
    ("pf_statement_download", r"\b(pf|epfo)\b.*\b(download|pdf|statement)\b"),
    ("higher_pension_scheme", r"\b(higher pension|higher eps|pension option)\b"),
    ("minimum_pension", r"\b(minimum pension|minimum monthly pension)\b"),
    ("pension_certificate", r"\b(pension scheme certificate|scheme certificate)\b"),
    ("international_worker", r"\b(international worker|foreign worker|overseas worker)\b"),
    ("employer_registration_pf", r"\b(register my company|employer registration|register establishment)\b.*\b(pf|epf|provident)\b"),
    ("employer_registration_pf", r"\b(pf|epf|provident)\b.*\b(register my company|employer registration|register establishment)\b"),
    ("employer_compliance_pf", r"\b(pf|epf|provident)\b.*\b(employer|company)\b.*\b(not depositing|not deposited|not remitting|not paying|not sent|hasn.t sent|didn.t send|compliance|report)\b"),
    ("esic_wage_ceiling", r"\b(esic|esi)\b.*\b(wage ceiling|salary ceiling|eligibility ceiling)\b"),
    ("esic_contribution_rate", r"\b(esic|esi)\b.*\b(contribution rate|employee rate|employer rate|percentage contribution)\b"),
    ("esic_registration_process", r"\b(esic|esi)\b.*\b(register|registration|enrol|enroll|new employee)\b"),
    ("esic_super_specialty", r"\b(esic|esi)\b.*\b(super specialty|super-specialty|speciality hospital|specialty hospital)\b"),
    ("esic_unemployment_benefit", r"\b(esic|esi)\b.*\b(unemployment|unemployment allowance|job loss allowance)\b"),
    ("esic_disablement_benefit", r"\b(esic|esi)\b.*\b(disablement|permanent disability|temporary disability)\b"),
    ("esic_dependent_benefit", r"\b(esic|esi)\b.*\b(dependent benefit|dependants benefit|family benefit|death at work|workplace death)\b"),
    ("esic_funeral_expense", r"\b(esic|esi)\b.*\b(funeral|funeral expense|funeral expenses)\b"),
    ("esic_confinement_expense", r"\b(esic|esi)\b.*\b(confinement expense|confinement expenses|delivery expenses)\b"),
    ("esic_online_portal", r"\b(esic|esi)\b.*\b(online portal|website login|esic portal)\b"),
    ("esic_contribution_period", r"\b(esic|esi)\b.*\b(contribution period|benefit period|period of contribution)\b"),
    ("gratuity_basics", r"\b(gratuity)\b"),
    ("bonus_basics", r"\b(statutor(y|ily) bonus|bonus entitlement|annual bonus)\b"),
    ("leave_encashment", r"\b(leave encashment|unused leave|unutilized leave|unutilised leave)\b"),
    ("full_final_settlement", r"\b(full and final|full & final|fnf|final settlement)\b"),
]

BASE_RULES = [
    ("uan_find", r"\b(pf|epf|provident fund)\b.*\b(forgot|forgotten|lost|cannot remember|can.t remember)\b.*\b(account|number|member|uan)\b"),
    ("uan_find", r"\b(forgot|forgotten|lost|cannot remember|can.t remember)\b.*\b(pf|epf|provident fund|uan)\b.*\b(account|number|member|uan)\b"),
    ("esic_card", r"\b(esic|esi)\b.*\b(record|show|add|update|missing|not listed)\b.*\b(dependant|dependent|dependants|dependents|family member)\b"),
    ("esic_card", r"\b(esic|esi)\b.*\b(dependant|dependent|dependants|dependents|family member)\b.*\b(record|show|add|update|missing|not listed)\b"),
    ("passbook", r"\b(pf|epf|provident fund)\b.*\b(see|check|view|look up|find)\b"),
    ("passbook", r"\b(see|check|view|look up|find)\b.*\b(pf|epf|provident fund)\b"),
    ("transfer", r"\b(pf|epf|provident fund)\b.*\b(left|leaving|leave my job|leave the company|resigned|resign)\b"),
    ("employer_compliance_pf", r"\b(employer|company)\b.*\b(hasn.t sent|not sent|didn.t send|not remitting|not depositing|not deposited)\b.*\b(pf|epf|provident)\b"),
    ("reject", r"\b(claim|application)\b.*\b(refused|turned down|not accepted)\b"),
    ("hr", r"\b(hr|supervisor|manager)\b.*\b(ignore|ignored|ignores|not answering|not explain)\b"),
    ("workinjury", r"\b(accident|injur|hurt at work|workplace incident)\b"),
    ("esic_benefits", r"\b(esic|esi)\b.*\b(maternity|pregnan|birth|delivery|sick|ill|medical leave|cash benefit|sickness)\b"),
    ("esic_claim", r"\b(esic|esi)\b.*\b(claim|status|pending|track|follow up)\b"),
    ("esic_medical", r"\b(esic|esi)\b.*\b(spouse|wife|husband|children|child|parents|dependants|dependents|family)\b.*\b(benefit|benefits|receive|eligible|cover|covered)\b"),
    ("esic_card", r"\b(esic|esi)\b.*\b(add|update|change)\b.*\b(family|member|dependant|dependent)\b"),
    ("esic_grievance", r"\b(esic|esi)\b.*\b(complain|complaint|grievance)\b"),
    ("esic_medical", r"\b(esic|esi)\b.*\b(hospital|doctor|dispensary|medicine|specialist|treatment|referral)\b"),
    ("esic_card", r"\b(esic|esi)\b.*\b(card|pehchan|insurance number|lost|missing|address|name)\b"),
    ("esic_eligibility", r"\b(esic|esi)\b.*\b(eligible|eligibility|registered|coverage|dependant|dependent|parents|family)\b"),
    ("why", r"\b(esic|esi)\b.*\b(deduct|deduction|cut|payslip|salary)\b"),
    ("esic", r"\b(esic|esi)\b"),
    ("missing", r"\b(pf|epf|provident)\b.*\b(passbook|credit|deposit|deposited|missing|not showing|not reflected|not credited|not paid)\b"),
    ("reject", r"\b(pf|epf|provident)\b.*\b(reject|rejected|rejection|denied|declined|refused|turned down|not accepted)\b"),
    ("claimstatus", r"\b(pf|epf|provident)\b.*\b(claim|status|pending|delayed|approved|approval)\b"),
    ("transfer", r"\b(pf|epf|provident)\b.*\b(transfer|new job|changed jobs|change job|resign|resigned|previous company)\b"),
    ("advance", r"\b(pf|epf|provident)\b.*\b(withdraw|withdrawal|take out|cash out|settlement)\b.*\b(advance|emergency|partial)\b"),
    ("withdraw", r"\b(pf|epf|provident)\b.*\b(withdraw|withdrawal|take out|cash out|settlement)\b"),
    ("employer", r"\b(pf|epf|provident)\b.*\b(contribution|employer share|company contribution)\b"),
    ("why", r"\b(pf|epf|provident)\b.*\b(deduct|deduction|cut|salary|payslip)\b"),
    ("personal_data", r"\b(pf|epf)\b.*\b(actual|exact|personal|my own)\b.*\b(balance|amount|how much|check|see)\b"),
    ("passbook", r"\b(pf|epf|provident)\b.*\b(balance|check|view|see|passbook)\b"),
    ("uan_find", r"\b(uan|universal account)\b.*\b(forgot|find|lost)\b"),
    ("activation", r"\b(uan|universal account)\b.*\b(activat|first time)\b"),
    ("duplicate", r"\b(uan|universal account)\b.*\b(two|duplicate|multiple)\b"),
    ("kyc", r"\b(pf|epfo|uan)\b.*\b(kyc|aadhaar|aadhar|date of birth|bank detail|mobile number|otp)\b"),
    ("nomination", r"\b(nominee|nomination)\b"),
    ("grievance", r"\b(pf|epfo)\b.*\b(grievance|complaint|complain|issue with epfo|helpdesk)\b"),
    ("docs", r"\b(pf|epf)\b.*\b(document|paper|what to keep ready)\b"),
    ("ticket", r"\b(ticket|raise a request|hr request)\b"),
    ("no_decision", r"\b(make a financial decision|approve my claim|guarantee.*claim|decide.*eligible)\b"),
    ("personal_data", r"\b(read my salary slip|access my payroll|with my permission|permission to access)\b"),
    ("security", r"\b(otp|password|pin|fraud|fake call|suspicious link|fee to release)\b"),
    ("privacy", r"\b(bank account|aadhaar|pan|personal details|privacy|store my information|share my details)\b"),
    ("hr", r"\b(supervisor|manager|afraid to ask|nervous asking|not answering|not explain|ignores hr)\b"),
    ("human", r"\b(human|speak to a person|call me|complex|sensitive)\b"),
]

def classify_intent(query: str) -> str | None:
    q = (query or "").lower()
    for intent, pattern in ADVANCED_RULES:
        if re.search(pattern, q):
            return intent
    for intent, pattern in BASE_RULES:
        if re.search(pattern, q):
            return intent
    return None

def levenshtein_one(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 5:
        return False
    if a == b:
        return True
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1; j += 1
        else:
            edits += 1
            if edits > 1:
                return False
            if len(a) > len(b): i += 1
            elif len(b) > len(a): j += 1
            else: i += 1; j += 1
    edits += (len(a) - i) + (len(b) - j)
    return edits <= 1

class KnowledgeIndex:
    def __init__(self, records: list[dict]):
        self.records = records
        self.corpus = [features(r.get("question_en", "") + " " + r.get("category", "")) for r in records]
        self.df = Counter()
        self.by_intent = {}
        for i, (record, feat) in enumerate(zip(records, self.corpus)):
            self.df.update(feat.keys())
            self.by_intent.setdefault(record.get("intent"), []).append(i)
        self.vocab = set(self.df)

    def rarity(self, word: str) -> float:
        return math.log(1 + (len(self.records) + 1) / (self.df.get(word, 0) + 1))

    def query_features(self, query: str) -> dict[str, float]:
        q = features(query)
        # Correct a single clear spelling error only when it maps to a known FAQ vocabulary term.
        for word in list(q):
            if word in self.vocab or len(word) < 5:
                continue
            close = get_close_matches(word, self.vocab, n=1, cutoff=0.86)
            if close and levenshtein_one(word, close[0]):
                q[close[0]] = max(q.get(close[0], 0), q[word])
        return q

    def lexical_score(self, q: dict, index: int) -> tuple[float, float]:
        c = self.corpus[index]
        shared = q_total = c_total = 0.0
        for w, v in q.items():
            wt = self.rarity(w)
            q_total += v * wt
            if w in c:
                shared += min(v, c[w]) * wt
        for w, v in c.items():
            c_total += v * self.rarity(w)
        coverage = shared / q_total if q_total else 0.0
        jaccard = shared / (q_total + c_total - shared) if (q_total + c_total - shared) else 0.0
        return (0.84 * coverage + 0.16 * jaccard, coverage)

    def retrieve(self, query: str) -> tuple[dict | None, float]:
        # Prevent generic workplace words (for example, "I work two jobs") from
        # matching a benefits FAQ through synonym expansion alone.
        domain_signal = re.search(
            r"\b(pf|epf|provident|esic|esi|epfo|uan|passbook|payslip|salary|payroll|deduction|contribution|"
            r"gratuity|bonus|leave|maternity|sickness|pension|nominee|nomination|kyc|claim|insurance|"
            r"employee|employer|hr|benefit|benefits|workplace|accident|injury|epfigms|umang|"
            r"wage|settlement|eps|edli|provident fund|aadhaar|aadhar|otp|bank account|form\s*(19|10c|31|11)|"
            r"complaint|grievance|helpdesk|medical|treatment|illness|health|specialist|portal|login|"
            r"personal details|personal information|privacy|assistant|chatbot|voice|language|accent|translation|"
            r"english meaning|simple words|do not know the answer|don.t know the answer|cannot answer|store my information|sahayak|saathi|manager)\b",
            (query or "").lower()
        )
        if not domain_signal:
            return None, 0.0
        nq = norm_question(query)
        for record in self.records:
            if nq == norm_question(record.get("question_en", "")):
                return record, 1.0
        q = self.query_features(query)
        if not q:
            return None, 0.0
        intent = classify_intent(query)
        if intent and intent in self.by_intent:
            best_idx, best_lex = None, -1.0
            for idx in self.by_intent[intent]:
                _, lex = self.lexical_score(q, idx)
                if lex > best_lex:
                    best_idx, best_lex = idx, lex
            # The intent rule must have matched a topic already present in this knowledge base.
            return self.records[best_idx], 0.82 + min(0.15, max(0.0, best_lex) * 0.15)
        ranked = []
        for idx in range(len(self.records)):
            score, _ = self.lexical_score(q, idx)
            ranked.append((score, idx))
        score, best_idx = max(ranked, default=(0.0, -1))
        return (self.records[best_idx], score) if best_idx >= 0 else (None, 0.0)

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            question TEXT NOT NULL,
            category TEXT NOT NULL,
            faq_id TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Open','Closed')),
            source TEXT NOT NULL DEFAULT 'assistant-suggested',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        conn.commit()

def ticket_row(row):
    return {
        "id": row[0], "title": row[1], "description": row[2], "question": row[3],
        "category": row[4], "faqId": row[5], "language": row[6], "status": row[7],
        "source": row[8], "createdAt": row[9], "updatedAt": row[10]
    }

with KB_PATH.open("r", encoding="utf-8") as f:
    KB = json.load(f)
RECORDS = KB["records"] if isinstance(KB, dict) else KB
INDEX = KnowledgeIndex(RECORDS)
init_db()

class Handler(BaseHTTPRequestHandler):
    server_version = "SaathiDemo/1.0"

    def log_message(self, fmt, *args):
        # Keep request logs compact; do not log submitted ticket contents.
        print("%s - %s" % (self.address_string(), fmt % args))

    def _send(self, status: int, payload, content_type="application/json; charset=utf-8"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 20000:
            raise ValueError("Request too large")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/saathi_ai_trained.html"):
            self._send(200, HTML_PATH.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/health":
            self._send(200, {"ok": True, "service": "Saathi AI local demo", "faq_records": len(RECORDS), "ticket_store": "SQLite local demo"})
            return
        if path == "/api/knowledge-base":
            self._send(200, {"record_count": len(RECORDS), "languages": ["hi", "kn", "ta"], "sources": ["uploaded combined JSON", "uploaded XLSX All 710 QA", "uploaded updated HTML"], "model_finetuning": False})
            return
        if path == "/api/tickets":
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute("SELECT id,title,description,question,category,faq_id,language,status,source,created_at,updated_at FROM tickets ORDER BY created_at DESC").fetchall()
            self._send(200, {"tickets": [ticket_row(r) for r in rows]})
            return
        self._send(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self._body()
        except Exception as e:
            self._send(400, {"error": str(e)})
            return
        if path == "/api/ask":
            question = str(data.get("question", "")).strip()
            language = str(data.get("language", "hi")).lower()
            if not question or len(question) > 500:
                self._send(400, {"error": "Question must contain 1 to 500 characters"})
                return
            if language not in LANGS:
                self._send(400, {"error": "Choose Hindi, Kannada or Tamil"})
                return
            if re.search(r"[\u0900-\u0DFF\u0C80-\u0CFF]", question):
                self._send(400, {"error": "Please enter the question in English; select a supported language for the answer."})
                return
            record, score = INDEX.retrieve(question)
            if not record or score < THRESHOLD:
                self._send(200, {"understood": False, "answer": UNCLEAR[language], "faq_id": None, "language": language, "retrieval_score": None})
                return
            answers = record.get("answers", {})
            answer = answers.get(language)
            if not answer:
                self._send(200, {"understood": False, "answer": UNCLEAR[language], "faq_id": None, "language": language, "retrieval_score": None})
                return
            self._send(200, {
                "understood": True, "answer": answer, "faq_id": record.get("id"),
                "category": record.get("category"), "source_group": record.get("source_group"),
                "language": language, "retrieval_score": round(score, 4),
                "human_escalation_recommended": bool(record.get("human_escalation_recommended")),
                "authenticated_data_required": bool(record.get("authenticated_data_required"))
            })
            return
        if path == "/api/tickets":
            if data.get("consent") is not True:
                self._send(403, {"error": "Explicit consent is required before saving a ticket"})
                return
            question = str(data.get("question", "")).strip()
            title = str(data.get("title", "")).strip()
            description = str(data.get("description", "")).strip()
            category = str(data.get("category", "HR review")).strip()[:80]
            language = str(data.get("language", "hi")).lower()
            faq_id = str(data.get("faqId", "")).strip()[:40]
            source = str(data.get("source", "assistant-suggested")).strip()[:40]
            if not question or len(question) > 1600:
                self._send(400, {"error": "Ticket description must contain 1 to 1600 characters"})
                return
            if language not in LANGS:
                self._send(400, {"error": "Invalid response language"})
                return
            if not category:
                self._send(400, {"error": "Please choose a ticket category"})
                return
            now = utc_now()
            ticket_id = "SAT-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8].upper()
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO tickets (id,title,description,question,category,faq_id,language,status,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (ticket_id, title, description, question, category, faq_id, language, "Open", source, now, now)
                )
                conn.commit()
                row = conn.execute("SELECT id,title,description,question,category,faq_id,language,status,source,created_at,updated_at FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            self._send(201, {"ticket": ticket_row(row), "message": "Saved to the local demonstration ticket queue; not sent to HR."})
            return
        self._send(404, {"error": "Not found"})

    def do_PATCH(self):
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/tickets/([^/]+)", path)
        if not match:
            self._send(404, {"error": "Not found"})
            return
        try:
            data = self._body()
        except Exception as e:
            self._send(400, {"error": str(e)})
            return
        status = data.get("status")
        if status not in ("Open", "Closed"):
            self._send(400, {"error": "Status must be Open or Closed"})
            return
        ticket_id = unquote(match.group(1))
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute("UPDATE tickets SET status=?, updated_at=? WHERE id=?", (status, utc_now(), ticket_id))
            conn.commit()
            if cur.rowcount == 0:
                self._send(404, {"error": "Ticket not found"})
                return
            row = conn.execute("SELECT id,title,description,question,category,faq_id,language,status,source,created_at,updated_at FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        self._send(200, {"ticket": ticket_row(row)})

def main():
    parser = argparse.ArgumentParser(description="Run Saathi AI local demo backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Saathi AI demo running at http://{args.host}:{args.port}")
    print(f"Knowledge base loaded: {len(RECORDS)} FAQ records; supported response languages: Hindi, Kannada, Tamil")
    print("Ticket actions are stored locally in SQLite and are not sent to an employer HR system.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Saathi AI demo...")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
