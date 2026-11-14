from __future__ import annotations
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass
import json, re, sqlite3, uuid, io
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Header
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from config import settings, BASE_DIR
from retrieval import KnowledgeBase, DOMAIN_RE, FOLLOWUP_RE
from providers import LLMProvider, ProviderError, embed_texts, make_speech
from mcp_client import mcp_client
from normalization import full_normalize
from payslip_analyzer import PayslipInput, analyze_payslip, extract_payslip_fields_from_text
from telephony import (
    telephony_service,
    get_or_create_session,
    CALL_SESSIONS,
    TELEPHONY_LANGUAGES,
    CONTROL_COMMANDS,
    TelephonyResponse,
)

LANGS={"hi":"Hindi","kn":"Kannada","ta":"Tamil"}
UNCLEAR={
"hi":"माफ़ कीजिए, मैं इस सवाल का जवाब उपलब्ध प्रमाणित जानकारी से नहीं दे पा रहा हूँ। कृपया PF या ESIC से जुड़ा सवाल दोबारा स्पष्ट करें, या HR से संपर्क करें।",
"kn":"ಕ್ಷಮಿಸಿ, ಲಭ್ಯವಿರುವ ಪರಿಶೀಲಿತ ಮಾಹಿತಿಯಿಂದ ಈ ಪ್ರಶ್ನೆಗೆ ಉತ್ತರಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು PF ಅಥವಾ ESIC ಕುರಿತು ಪ್ರಶ್ನೆಯನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಕೇಳಿ, ಅಥವಾ HR ಅನ್ನು ಸಂಪರ್ಕಿಸಿ.",
"ta":"மன்னிக்கவும், கிடைக்கும் சரிபார்க்கப்பட்ட தகவல்களின் அடிப்படையில் இந்தக் கேள்விக்கு பதிலளிக்க முடியவில்லை. PF அல்லது ESIC தொடர்பான கேள்வியைத் தெளிவாக மீண்டும் கேளுங்கள் அல்லது HR-ஐ அணுகுங்கள்."
}
OUT_OF_SCOPE={
"hi":"मैं केवल PF और ESIC से जुड़े सवालों में मदद कर सकता हूँ। कृपया PF, EPFO, UAN या ESIC के बारे में पूछें।",
"kn":"ನಾನು PF ಮತ್ತು ESIC ಸಂಬಂಧಿತ ಪ್ರಶ್ನೆಗಳಿಗೆ ಮಾತ್ರ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ದಯವಿಟ್ಟು PF, EPFO, UAN ಅಥವಾ ESIC ಕುರಿತು ಕೇಳಿ.",
"ta":"PF மற்றும் ESIC தொடர்பான கேள்விகளுக்கு மட்டுமே நான் உதவ முடியும். PF, EPFO, UAN அல்லது ESIC பற்றி கேளுங்கள்."
}
SYSTEM_TEMPLATE="""You are Saathi AI, a careful PF and ESIC benefits assistant for Indian factory and warehouse workers.
Answer ONLY from the supplied retrieved knowledge snippets and any explicitly returned authorised MCP tool results. Never use outside assumptions to fill gaps. Do not invent rules, rates, dates, eligibility, balances, claim status, forms, or employer policy. If sources do not support the answer, say so and recommend HR or the relevant official service. Do not claim to access personal records unless an authenticated MCP tool result explicitly provides them. Never ask for passwords, OTPs, Aadhaar numbers, bank credentials, or sensitive identifiers.
The user-facing response language is {language}. Write in simple, natural {language}; preserve technical tokens PF, UAN, EPFO, ESIC. Do not provide English unless asked as the separate translation field. Answer concisely, with clear next steps where useful. Do not make a financial decision or guarantee claim approval. Do not create tickets; ticket creation requires separate explicit consent in the application."""

records_raw=json.loads(Path(settings.knowledge_path).read_text(encoding="utf-8"))
if isinstance(records_raw,dict): records_raw=records_raw.get("records",[])
KB=KnowledgeBase(records_raw,settings.database_path)
LLM=LLMProvider()
DB=settings.database_path
CONVERSATIONS:dict[str,list[dict]]={}

app=FastAPI(title="Saathi AI",version="2.0.0")

class AskBody(BaseModel):
    question:str=Field(min_length=1,max_length=1000)
    language:str="hi"
    conversation_id:str|None=None
    include_english:bool=True
    source:str|None="user_chat"

class TicketBody(BaseModel):
    consent:bool=False
    question:str=Field(default="",max_length=1600)
    title:str=Field(default="",max_length=100)
    description:str=Field(default="",max_length=1500)
    category:str=Field(default="PF / EPFO",max_length=80)
    faqId:str=Field(default="",max_length=40)
    language:str="hi"
    source:str="employee-created"

class StatusBody(BaseModel): status:str


def db_init():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL,question TEXT NOT NULL,
        category TEXT NOT NULL,faq_id TEXT NOT NULL,language TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Open','Closed')),source TEXT NOT NULL,
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL,external_id TEXT NOT NULL DEFAULT '')""")
        c.commit()

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def row_ticket(r):
    return {"id":r[0],"title":r[1],"description":r[2],"question":r[3],"category":r[4],"faqId":r[5],"language":r[6],"status":r[7],"source":r[8],"createdAt":r[9],"updatedAt":r[10],"externalId":r[11]}
def get_record(fid): return next((r for r in KB.records if r.get("id")==fid),None)
INDIC_ESIC_WORDS = re.compile(
    r"(esic|esi|employee state insurance|कर्मचारी राज्य बीमा|राज्य बीमा|ईएसआईसी|ईएसआई|इएसआईसी|इएसआई|"
    r"ಇಎಸ್ಐ|ಇಎಸ್ಐಸಿ|ಇಎಸ್‌ಐ|ಇಎಸ್‌ಐಸಿ|ನೌಕರರ ರಾಜ್ಯ ವಿಮೆ|ರಾಜ್ಯ ವಿಮೆ|ವೈದ್ಯಕೀಯ ಸೌಲಭ್ಯ|"
    r"இஎஸ்ஐ|இஎஸ்ஐசி|தொழிலாளர் அரசு காப்பீடு|அரசு காப்பீடு|காப்பீட்டுக் கழகம்)",
    re.I
)

INDIC_PF_WORDS = re.compile(
    r"(pf|epf|provident fund|epfo|uan|passbook|epfigms|"
    r"भविष्य निधि|भविष्यनिधि|कर्मचारी भविष्य निधि|पीएफ|ईपीएफ|ईपीएफओ|यूएएन|युएएन|पेंशन|ईपीएस|ईडीएलआई|"
    r"ಪ್ರಾವಿಡೆಂಟ್ ಫಂಡ್|ಭವಿಷ್ಯ ನಿಧಿ|ಪಿಎಫ್|ಇಪಿಎಫ್|ಇಪಿಎಫ್‌ಒ|ಇಪಿಎಫ್ಒ|ಯುಎಎನ್|ಯುಎನ್|ಪಿಂಚಣಿ|ಇಪಿಎಸ್|ಇಡಿಎಲ್ಐ|"
    r"வருங்கால வைப்பு நிதி|வருங்கால வைப்புநிதி|ப்ரோவிடென்ட் ஃபண்ட்|பிஎஃப்|இபிஎஃப்|இபிஎஃப்ஓ|யுஏஎன்|யூஏஎன்|ஓய்வூதியம்|இபிஎஸ்|இடிஎல்ஐ)",
    re.I
)

INDIC_CONTRIBUTION_WORDS = re.compile(
    r"(employer contribution|company contribution|employer share|statutory deduction|salary deduction|payslip deduction|"
    r"नियोक्ता का हिस्सा|कंपनी का अंशदान|मालिक का अंशदान|कंपनी का हिस्सा|वेतन कटौती|सैलरी कटौती|"
    r"ಮಾಲೀಕರ ಕೊಡುಗೆ|ಕಂಪನಿ ಪಾಲು|ಮಾಲೀಕರ ಪಾಲು|ವೇತನ ಕಡಿತ|ಸಂಬಳ ಕಡಿತ|"
    r"முதலாளி பங்களிப்பு|நிறுவன பங்களிப்பு|சம்பள பிடித்தம்)",
    re.I
)

NEAR_MISS_PATTERNS = {
    "income_tax": re.compile(
        r"(\b(income tax|tds|tax return|itr|form 16|advance tax|gst|income tax slab|tax slab|tax refund)\b|"
        r"इनकम टैक्स|इन्कम टैक्स|टीडीएस|टैक्स रिफंड|आयकर|टैक्स रिटर्न|आईटीआर|"
        r"ಆದಾಯ ತೆರಿಗೆ|ಟಿಡಿಎಸ್|ಟ್ಯಾಕ್ಸ್|ಐಟಿ ರಿಟರ್ನ್|ತೆರಿಗೆ ಕಡಿತ|"
        r"வருமான வரி|டிடிஎஸ்|வரி பிடித்தம்|வரி ரீபண்ட்|ஐடிஆர்)",
        re.I
    ),
    "lic_private_insurance": re.compile(
        r"(\b(lic|life insurance corporation|lic policy|term insurance|private insurance|car insurance|bike insurance|jeevan bima)\b|"
        r"एलआईसी|एल आई सी|जीवन बीमा|पॉलिसी प्रीमियम|टर्म इंश्योरेंस|गाड़ी का बीमा|"
        r"ಎಲ್ಐಸಿ|ಎಲ್ ಐ ಸಿ|ಜೀವ ವಿಮೆ|ಪಾಲಿಸಿ ಪ್ರೀಮಿಯಂ|ಟರ್ಮ್ ಇನ್ಶೂರೆನ್ಸ್|ವಾಹನ ವಿಮೆ|"
        r"எல்ஐசி|எல் ஐ சி|ஆயுள் காப்பீடு|ஆயுள் காப்பீட்டு|பாலிசி பிரீமியம்|லைஃப் இன்சூரன்ஸ்|வாகன காப்பீடு)",
        re.I
    ),
    "bank_loan": re.compile(
        r"(\b(bank loan|personal loan|home loan|car loan|gold loan|credit card loan|emi loan|loan interest)\b|"
        r"बैंक लोन|पर्सनल लोन|होम लोन|गोल्ड लोन|कर्ज चाहिए|लोन कैसे मिलेगा|लोन चाहिए|ऋण चाहिए|"
        r"ಬ್ಯಾಂಕ್ ಸಾಲ|ಪರ್ಸನಲ್ ಲೋನ್|ಹೋಮ್ ಲೋನ್|ಚಿನ್ನದ ಸಾಲ|ಸಾಲ ಬೇಕು|ಸಾಲ ಹೇಗೆ ಪಡೆಯುವುದು|"
        r"வங்கி கடன்|தனிநபர் கடன்|வீட்டுக் கடன்|நகைக் கடன்|கடன் வேண்டும்|கடன் எப்படி பெறுவது)",
        re.I
    ),
    "job_search": re.compile(
        r"(\b(job vacancy|job opening|hiring|recruitment|need a job|looking for a job|warehouse vacancy|apply for job)\b|"
        r"नई नौकरी|नौकरी चाहिए|वैकेंसी|जॉब ओपनिंग|भर्ती चाहिए|काम चाहिए|नौकरी कैसे मिलेगी|काम ढूंढ रहा|"
        r"ಹೊಸ ಕೆಲಸ|ಕೆಲಸ ಬೇಕು|ಖಾಲಿ ಹುದ್ದೆ|ಉದ್ಯೋಗಾವಕಾಶ|ಕೆಲಸ ಹುಡುಕಾಟ|ಕೆಲಸ ಹೇಗೆ ಸಿಗುತ್ತದೆ|ಕೆಲಸ ಕೊಡಿಸಿ|"
        r"புதிய வேலை|வேலை வேண்டும்|காலி பணியிடம்|வேலை வாய்ப்பு|வேலை தேடுதல்|வேலை கிடைக்குமா|வேலை சேர்க்கை)",
        re.I
    ),
    "coworker_salary": re.compile(
        r"(\b(supervisor|manager|coworker|colleague|other employee|someone else|boss|"
        r"सुपरवाइजर|मैनेजर|सहकर्मी|दूसरे|बॉस|"
        r"ಸೂಪರ್‌ವೈಸರ್|ಮೇಲ್ವಿಚಾರಕ|ಮ್ಯಾನೇಜರ್|ಸಹೋದ್ಯೋಗಿ|ಇತರರ|"
        r"மேற்பார்வையாளர்|மேலாளர்|சக ஊழியர்|மற்றவர்).{0,50}"
        r"(salary|pay|wage|earning|वेतन|सैलरी|कमाई|तनख्वाह|ಸಂಬಳ|ವೇತನ|ಗಳಿಕೆ|சம்பளம்|ஊதியம்)|"
        r"(salary|pay|wage|earning|वेतन|सैलरी|कमाई|तनख्वाह|ಸಂಬಳ|ವೇತನ|ಗಳಿಕೆ|சம்பளம்|ஊதியம்).{0,50}"
        r"(supervisor|manager|coworker|colleague|other employee|someone else|boss|"
        r"सुपरवाइजर|मैनेजर|सहकर्मी|दूसरे|बॉस|"
        r"ಸೂಪರ್‌ವೈಸರ್|ಮೇಲ್ವಿಚಾರಕ|ಮ್ಯಾನೇಜರ್|ಸಹೋದ್ಯೋಗಿ|ಇತರರ|"
        r"மேற்பார்வையாளர்|மேலாளர்|சக ஊழியர்|மற்றவர்))",
        re.I
    )
}

NEAR_MISS_EXPLANATIONS = {
    "income_tax": {
        "hi": "साथी AI केवल पीएफ (EPFO) और ईएसआईसी (ESIC) कटौती में सहायता करता है। इनकम टैक्स (ITR) या टीडीएस के लिए कृपया अपने फाइनेंस विभाग या टैक्स सलाहकार से संपर्क करें।",
        "kn": "ಸಾಥಿ AI ಕೇವಲ ಪಿಎಫ್ (EPFO) ಮತ್ತು ಇಎಸ್ಐಸಿ (ESIC) ಶಾಸನಬದ್ಧ ಕಡಿತಗಳಿಗೆ ಮಾತ್ರ ನೆರವು ನೀಡುತ್ತದೆ. ಆದಾಯ ತೆರಿಗೆ (ITR) ಅಥವಾ ಟಿಡಿಎಸ್ ಮಾಹಿತಿಗಾಗಿ ದಯವಿಟ್ಟು ಹಣಕಾಸು ವಿಭಾಗವನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        "ta": "சாத்தி AI பிஎஃப் (EPFO) மற்றும் இஎஸ்ஐசி (ESIC) சட்டப்பூர்வ பிடித்தங்களுக்கு மட்டுமே உதவ முடியும். வருமான வரி (ITR) அல்லது டிடிஎஸ் தகவலுக்கு உங்கள் நிதிப் பிரிவை அணுகவும்.",
        "en": "Saathi AI only assists with statutory PF (EPFO) and ESIC deductions. For Income Tax or TDS, please contact your payroll finance department."
    },
    "lic_private_insurance": {
        "hi": "साथी AI केवल सरकारी ईएसआईसी (कर्मचारी राज्य बीमा) और ईपीएफओ के लिए है। एलआईसी या व्यक्तिगत जीवन बीमा के लिए कृपया सीधे एलआईसी शाखा से संपर्क करें।",
        "kn": "ಸಾಥಿ AI ಕೇವಲ ಸರಕಾರಿ ಇಎಸ್ಐಸಿ (ಉದ್ಯೋಗಿ ರಾಜ್ಯ ವಿಮೆ) ಮತ್ತು ಪಿಎಫ್ ಸೌಲಭ್ಯಗಳಿಗೆ ಮಾತ್ರ. ಎಲ್ಐಸಿ ಅಥವಾ ವೈಯಕ್ತಿಕ ಜೀವ ವಿಮೆಗೆ ದಯವಿಟ್ಟು ಎಲ್ಐಸಿ ಕಚೇರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        "ta": "சாத்தி AI அரசு இஎஸ்ஐசி மற்றும் பிஎஃப் சேவைகளுக்கு மட்டுமே. எல்ஐசி அல்லது தனிநபர் ஆயுள் காப்பீட்டுக்கு தயவுசெய்து எல்ஐசி கிளையை நேரடியாக அணுகவும்.",
        "en": "Saathi AI only supports statutory ESIC and EPFO benefits. For LIC or private life insurance, please contact LIC directly."
    },
    "bank_loan": {
        "hi": "साथी AI पीएफ एडवांस (अग्रिम निकासी) की प्रक्रिया समझा सकता है, लेकिन बैंक लोन या पर्सनल लोन प्रदान नहीं करता। लोन के लिए कृपया अपने बैंक से संपर्क करें।",
        "kn": "ಸಾಥಿ AI ಪಿಎಫ್ ಮುಂಗಡ ಹಿಂಪಡೆಯುವ ಹಂತಗಳನ್ನು ವಿವರಿಸಬಲ್ಲದು, ಆದರೆ ಬ್ಯಾಂಕ್ ಸಾಲ ಅಥವಾ ಪರ್ಸನಲ್ ಲೋನ್ ನೀಡುವುದಿಲ್ಲ. ಸಾಲಕ್ಕಾಗಿ ದಯವಿಟ್ಟು ನಿಮ್ಮ ಬ್ಯಾಂಕ್ ಸಂಪರ್ಕಿಸಿ.",
        "ta": "சாத்தி AI பிஎஃப் முன்பணம் எடுக்கும் முறையை விளக்கும், ஆனால் வங்கி கடன் அல்லது தனிநபர் கடன் வழங்காது. கடனுக்கு உங்கள் வங்கியை அணுகவும்.",
        "en": "Saathi AI explains PF advances, but does not provide or process bank/personal loans. Please contact your bank directly."
    },
    "job_search": {
        "hi": "साथी AI वर्तमान कर्मचारियों के पीएफ और ईएसआईसी अधिकारों के लिए सहायता सहायक है, यह नई नौकरी भर्ती पोर्टल नहीं है। नौकरियों के लिए कंपनी के एचआर या करियर पोर्टल पर जाएं।",
        "kn": "ಸಾಥಿ AI ಪ್ರಸ್ತುತ ಉದ್ಯೋಗಿಗಳ ಪಿಎಫ್ ಮತ್ತು ಇಎಸ್ಐಸಿ ಹಕ್ಕುಗಳ ಸಹಾಯವಾಣಿಯಾಗಿದೆ, ಇದು ಹೊಸ ಉದ್ಯೋಗ ನೇಮಕಾತಿ ಪೋರ್ಟಲ್ ಅಲ್ಲ. ಉದ್ಯೋಗಾವಕಾಶಗಳಿಗಾಗಿ ಕಂಪನಿಯ ಎಚ್‌ಆರ್ ಸಂಪರ್ಕಿಸಿ.",
        "ta": "சாத்தி AI தற்போதைய ஊழியர்களின் பிஎஃப் மற்றும் இஎஸ்ஐசி உரிமைகளுக்கான உதவி தளம், இது புதிய வேலைவாய்ப்பு போர்டல் அல்ல. வேலைகளுக்கு நிறுவனத்தின் HR-ஐ அணுகவும்.",
        "en": "Saathi AI assists current employees with PF and ESIC rights, not job hiring. For vacancies, please contact company HR."
    },
    "coworker_salary": {
        "hi": "कंपनी की गोपनीयता नीति के अनुसार सुपरवाइजर, मैनेजर या अन्य सहकर्मियों के वेतन और कटौती की जानकारी साझा नहीं की जा सकती।",
        "kn": "ಕಂಪನಿಯ ಗೌಪ್ಯತಾ ನೀತಿಯ ಪ್ರಕಾರ ಸೂಪರ್‌ವೈಸರ್, ಮ್ಯಾನೇಜರ್ ಅಥವಾ ಸಹೋದ್ಯೋಗಿಗಳ ಸಂಬಳ ಮತ್ತು ಕಡಿತದ ವಿವರಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಲಾಗುವುದಿಲ್ಲ.",
        "ta": "நிறுவனத்தின் ரகசியத்தன்மை விதிகளின்படி மேற்பார்வையாளர், மேலாளர் அல்லது சக ஊழியர்களின் சம்பள விவரங்களை பகிர முடியாது.",
        "en": "Per privacy policies, supervisor, manager, or coworker salary and deduction details cannot be disclosed."
    }
}

def mask_pii(text: str) -> str:
    """Masks UAN, Aadhaar, PAN, phone numbers, and OTPs to protect worker privacy."""
    if not text:
        return ""
    # Mask 12-digit IDs (Aadhaar or UAN, with optional spaces/dashes)
    s = re.sub(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b", "[ID_MASKED_12DIGIT]", text)
    # Mask Indian mobile numbers (10 digits starting 6-9, optional +91)
    s = re.sub(r"(\+91[- ]?)?[6-9]\d{9}\b", "[PHONE_MASKED]", s)
    # Mask PAN (5 letters, 4 digits, 1 letter)
    s = re.sub(r"\b[A-Za-z]{5}\d{4}[A-Za-z]{1}\b", "[PAN_MASKED]", s)
    # Mask OTPs (4-6 digits near otp/pin/code/password in en/hi/kn/ta)
    s = re.sub(r"(?i)\b(otp|code|pin|पासवर्ड|ओटीपी|ಪಾಸ್‌ವರ್ಡ್|கடவுச்சொல்)[:\s-]*\d{4,6}\b", r"\1:[OTP_MASKED]", s)
    s = re.sub(r"(?i)\b\d{4,6}\s*(otp|code|pin|पासवर्ड|ओटीपी|ಪಾಸ್‌ವರ್ಡ್|கடவுச்சொல்)\b", r"[OTP_MASKED] \1", s)
    return s

def is_in_scope_pf_esic_query(raw_q: str, norm_q: str) -> bool:
    """Checks if the query has specific in-scope context that overrides near-miss triggers."""
    text = (raw_q + " " + norm_q).lower()
    has_pf = bool(re.search(r"\b(pf|epf|epfo|provident fund)\b|पीएफ|भविष्य निधि|ಪಿಎಫ್|ಇಪಿಎಫ್|ಭವಿಷ್ಯ ನಿಧಿ|பிஎஃப்|இபிஎஃப்|வருங்கால வைப்பு", text))
    has_esic = bool(re.search(r"\b(esic|esi)\b|ईएसआईसी|ईएसआई|इएसआईसी|ಇಎಸ್ಐ|ಇಎಸ್ಐಸಿ|இஎஸ்ஐ|இஎஸ்ಐசி", text))
    has_tax = bool(re.search(r"\b(tds|tax|income tax|itr)\b|टीडीएस|टैक्स|इनकम टैक्स|आयकर|ತೆರಿಗೆ|ಟಿಡಿಎಸ್|வரி|டிடிஎஸ்", text))
    has_withdrawal = bool(re.search(r"\b(withdraw|withdrawal)\b|निकासी|निकाल|ಹಿಂಪಡೆಯ|ತೆಗೆಯ|எடு|திரும்பப் பெற", text))
    has_transfer = bool(re.search(r"\b(transfer)\b|ट्रांसफर|बदली|ವರ್ಗಾವಣೆ|மாற்ற|மாற்று", text))
    has_supervisor = bool(re.search(r"\b(supervisor|manager|boss)\b|सुपरवाइजर|मैनेजर|ಮೇಲ್ವಿಚಾರಕ|ಸೂಪರ್‌ವೈಸರ್|மேற்பார்வையாளர்|மேலாளர்", text))
    has_deduction_issue = bool(re.search(r"(not deduct|cut|कटा नहीं|कटौती नहीं|नहीं कट|कटेगा|ಕಡಿತವಾಗುವುದಿಲ್ಲ|ಕಡಿತವಾಗಿಲ್ಲ|ಕಟ್ ಆಗಿಲ್ಲ|ಹಿಡಿಯುವುದಿಲ್ಲ|பிடித்தம் செய்யப்படாது|பிடித்தம் செய்யப்படவில்லை|பிடிக்கவில்லை)", text))

    # TDS or income tax on PF withdrawal is in-scope
    if has_tax and (has_pf or has_withdrawal):
        return True
    # ESIC questions are in-scope even if mentioning insurance
    if has_esic:
        return True
    # Job change PF transfer is in-scope
    if has_pf and has_transfer:
        return True
    # Supervisor says own PF not deducted is in-scope
    if has_supervisor and has_pf and has_deduction_issue:
        return True
    return False

def detect_out_of_scope_near_miss(raw_q: str, norm_q: str | None = None) -> tuple[bool, str | None]:
    s1 = raw_q or ""
    s2 = norm_q or full_normalize(s1)
    if is_in_scope_pf_esic_query(s1, s2):
        return False, None
    for category, pat in NEAR_MISS_PATTERNS.items():
        if pat.search(s1) or pat.search(s2):
            return True, category
    return False, None

SPEECH_TRANSCRIPTS_PATH = BASE_DIR / "speech_transcripts.jsonl"

def log_speech_transcript(
    source: str,
    raw_transcript: str,
    language: str,
    call_id: str = "",
    normalized_text: str = "",
    scope: str = "",
    faq_id: str = "",
    confidence_score: float = 0.0,
    lexical_score: float = 0.0,
    match_mode: str = ""
):
    try:
        masked_raw = mask_pii(raw_transcript)
        masked_norm = mask_pii(normalized_text)
        rec = {
            "timestamp": now(),
            "source": source,
            "call_id": call_id,
            "language": language,
            "raw_transcript": masked_raw,
            "normalized_text": masked_norm,
            "scope": scope,
            "faq_id": faq_id or "",
            "confidence_score": round(confidence_score, 4) if confidence_score else 0.0,
            "lexical_score": round(lexical_score, 4) if lexical_score else 0.0,
            "match_mode": match_mode
        }
        with open(SPEECH_TRANSCRIPTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log speech transcript: {e}")

def topic_from(q: str, previous: str|None=None) -> str|None:
    norm_q = full_normalize(q or "")
    is_near_miss, _ = detect_out_of_scope_near_miss(q or "", norm_q)
    if is_near_miss:
        return None
    if INDIC_ESIC_WORDS.search(norm_q) or INDIC_ESIC_WORDS.search(q):
        return "esic"
    if (INDIC_PF_WORDS.search(norm_q) or INDIC_PF_WORDS.search(q) or 
        INDIC_CONTRIBUTION_WORDS.search(norm_q) or INDIC_CONTRIBUTION_WORDS.search(q)):
        return "pf"
    if previous and FOLLOWUP_RE.search(norm_q):
        return previous
    return None

def needs_ticket(q: str, record: dict|None):
    if not q: return False
    problem=re.search(r"\b(wrong|incorrect|missing|not deposited|not credited|not showing|not reflected|discrepancy|complaint|complain|grievance|rejected|rejection|not paid|deducted twice|double deduction|injury|problem|issue|pending too long|delay|delayed)\b",q,re.I)
    return bool(problem or (record and record.get("human_escalation_recommended")))

def source_payload(record: dict|None):
    if not record: return []
    # Dataset source groups are not verified URLs; don't manufacture citations.
    return [{"id":record.get("id"),"name":record.get("source_group") or "Uploaded FAQ dataset","category":record.get("category"),"url":None,"verification":"Source URL and policy section were not supplied with the uploaded dataset; requires HR review."}]

async def query_embedding(q: str):
    try: return (await embed_texts([q]))[0]
    except Exception: return None

def retrieve_reviewed_document_chunks(question: str, topic: str, query_vector: list[float] | None = None, limit: int = 3):
    """Only admin-reviewed uploaded policy chunks can support answers."""
    try:
        with sqlite3.connect(DB) as c:
            rows=c.execute("SELECT id,source_name,domain,content,source_urls,review_status,embedding FROM knowledge_chunks WHERE review_status='reviewed_by_admin'").fetchall()
    except sqlite3.OperationalError:
        return []
    qset=set(re.findall(r"[a-z0-9]+",question.lower()))
    out=[]
    for row in rows:
        rid,source,domain,content,urls,status,raw_vector=row
        if topic == "pf" and domain not in {"PF","PF/ESIC"}: continue
        if topic == "esic" and domain not in {"ESIC","PF/ESIC"}: continue
        words=set(re.findall(r"[a-z0-9]+",content.lower()))
        overlap=len(qset & words)/max(1,len(qset))
        vector_score=0.0
        if query_vector and raw_vector:
            try:
                import math
                vec=json.loads(raw_vector)
                dot=sum(a*b for a,b in zip(vec,query_vector)); na=math.sqrt(sum(a*a for a in vec)); nb=math.sqrt(sum(a*a for a in query_vector))
                vector_score=max(0.0,dot/(na*nb)) if na and nb and len(vec)==len(query_vector) else 0.0
            except Exception: vector_score=0.0
        score=max(overlap,vector_score)
        if score >= 0.10:
            try: url_list=json.loads(urls or "[]")
            except Exception: url_list=[]
            out.append({"source_name":source,"content":content,"source_urls":url_list,"review_status":status,"lexical_overlap":round(overlap,3),"vector_similarity":round(vector_score,3)})
    out.sort(key=lambda x:max(x["lexical_overlap"],x["vector_similarity"]),reverse=True)
    return out[:limit]

async def execute_mcp_pipeline(question: str, language: str, topic: str | None = None) -> tuple[list[dict], list[dict]]:
    """
    Executes authorized read-only MCP tools by default for /api/ask and telephony.
    Returns: (evidence_items, mcp_tool_calls_log)
    """
    evidence_items = []
    mcp_tool_calls = []
    
    # 1. search_policy tool (grounding across 710 canonical FAQs)
    search_args = {"query": question, "language": language}
    search_res = await mcp_client.call_tool("search_policy", search_args)
    sc = search_res.get("structuredContent") or {}
    matched_id = ""
    if isinstance(sc, dict) and sc.get("matches"):
        first_m = sc["matches"][0]
        matched_id = first_m.get("id", "")
        summary_txt = f"Matched {matched_id} ({first_m.get('question_en', '')[:40]}) score {first_m.get('score')}"
        for m in sc["matches"][:2]:
            evidence_items.append({
                "mcp_tool": "search_policy",
                "id": m.get("id"),
                "category": m.get("category"),
                "source_group": m.get("source_group"),
                "answer": m.get("answer"),
                "answer_en": m.get("answer_en")
            })
    else:
        summary_txt = "No high-confidence policy matches"
        
    mcp_tool_calls.append({
        "tool": "search_policy",
        "arguments": search_args,
        "status": "error" if search_res.get("isError") else "success",
        "output_summary": summary_txt,
        "matched_faq_id": matched_id
    })

    # 2. get_worker_payroll_record tool (if question references Lakshmi or payroll records)
    if re.search(r"\b(lakshmi|packer|my salary|my payslip|my deduction|warehouse payroll|payroll record|employee record|ಲಕ್ಷ್ಮಿ|लक्ष्मी|லட்சுமி)\b", question, re.I):
        rec_args = {"worker_id": "EMP-LAKSHMI-001"}
        rec_res = await mcp_client.call_tool("get_worker_payroll_record", rec_args)
        rsc = rec_res.get("structuredContent") or {}
        rec_summary = f"Retrieved MOCK record for Lakshmi (Basic: Rs {rsc.get('record', {}).get('basic_wage', 11500)}, Status: {rsc.get('record', {}).get('remittance_status', 'Pending')})"
        mcp_tool_calls.append({
            "tool": "get_worker_payroll_record",
            "arguments": rec_args,
            "status": "error" if rec_res.get("isError") else "success",
            "output_summary": rec_summary
        })
        if rsc.get("found"):
            evidence_items.append({
                "mcp_tool": "get_worker_payroll_record",
                "payroll_record": rsc["record"]
            })

    # 3. get_pf_howto tool (if question asks for self-service procedures)
    if re.search(r"\b(how to check balance|check.*balance|balance.*check|बैलेंस|ಬ್ಯಾಲೆನ್ಸ್|இருப்பு|uan activate|activate uan|claim|withdrawal|advance|form 31|form 19|transfer|job transfer|job change)\b", question, re.I):
        q_low = question.lower()
        subtopic = "passbook"
        if "transfer" in q_low or "ವರ್ಗಾವಣೆ" in q_low or "மாற்று" in q_low:
            subtopic = "transfer"
        elif "activate" in q_low or "ಆಕ್ಟಿವೇಟ್" in q_low or "செயல்படுத்து" in q_low:
            subtopic = "uan_activation"
        elif "claim" in q_low or "withdraw" in q_low or "advance" in q_low or "ಕ್ಲೇಮ್" in q_low:
            subtopic = "claim_withdrawal"
            
        howto_args = {"topic": subtopic, "language": language}
        howto_res = await mcp_client.call_tool("get_pf_howto", howto_args)
        hsc = howto_res.get("structuredContent") or {}
        howto_summary = f"Retrieved official guidance for {subtopic}: {hsc.get('title', '')} (Honest: no public balance API)"
        mcp_tool_calls.append({
            "tool": "get_pf_howto",
            "arguments": howto_args,
            "status": "error" if howto_res.get("isError") else "success",
            "output_summary": howto_summary
        })
        if hsc:
            evidence_items.append({
                "mcp_tool": "get_pf_howto",
                "procedure": hsc.get("procedure_details"),
                "disclaimer": hsc.get("official_disclaimer")
            })

    # 4. get_ticket_status tool (if question contains a ticket ID)
    ticket_match = re.search(r"\b(SAT-\d{8}-[A-F0-9]{6,8})\b", question, re.I)
    if ticket_match:
        t_id = ticket_match.group(1).upper()
        status_args = {"ticket_id": t_id}
        status_res = await mcp_client.call_tool("get_ticket_status", status_args)
        tsc = status_res.get("structuredContent") or {}
        t_summary = f"Ticket {t_id} status: {tsc.get('ticket', {}).get('status', 'Not found')}"
        mcp_tool_calls.append({
            "tool": "get_ticket_status",
            "arguments": status_args,
            "status": "error" if status_res.get("isError") else "success",
            "output_summary": t_summary
        })
        if tsc.get("found"):
            evidence_items.append({
                "mcp_tool": "get_ticket_status",
                "ticket_status": tsc["ticket"]
            })

    return evidence_items, mcp_tool_calls

@app.get("/")
async def home():
    for f in ["index.html", "saathi_ai_trained.html"]:
        p = BASE_DIR / f
        if p.is_file(): return FileResponse(p)
    return JSONResponse({"status":"Saathi AI backend active","version":"2.0.0"})

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.get("/api/featured")
async def featured():
    return {
        "questions": [
            "Why is PF deducted from my salary every month?",
            "How can I check my PF balance?",
            "My payslip shows PF deduction but no passbook credit. What should I do?",
            "I changed jobs. How do I transfer my old PF account?",
            "Can I withdraw my full PF amount whenever I want?",
            "My PF claim was rejected. What should I do next?",
            "What is ESIC and what does it cover?",
            "Can my spouse and children receive ESIC benefits?",
            "How do I complain about a PF issue to EPFO?",
            "What should my family do to claim PF benefits if I die?"
        ]
    }

@app.get("/api/health")
async def health():
    mcp_status=await mcp_client.connect() if mcp_client.configured else {"connected":False,"reason":"not configured","tools":[]}
    return {"ok":True,"service":"Saathi AI","knowledge_records_total":len(records_raw),"pf_esic_records_indexed":len(KB.records),"llm_provider":settings.llm_provider,"llm_configured":bool((settings.llm_api_key or settings.anthropic_api_key or settings.gemini_api_key) and settings.llm_provider!="none"),"embedding_provider":settings.embedding_provider,"mcp":mcp_status,"tts_provider":settings.tts_provider,"ticket_store":"SQLite demo; remote HR ticketing only if configured MCP tool is available"}
@app.get("/api/knowledge-base")
async def knowledge_base(): return {"record_count":len(KB.records),"languages":["hi","kn","ta"],"scope":["PF","EPFO","UAN","ESIC"],"retrieval":"hybrid lexical + optional vector embeddings","llm_provider":settings.llm_provider}

@app.post("/api/ask")
async def ask(body:AskBody):
    raw_q=body.question.strip(); lang=body.language.lower()
    if lang not in LANGS: raise HTTPException(400,"Choose Hindi, Kannada or Tamil")
    if not raw_q: raise HTTPException(400,"Please enter a question")
    q = full_normalize(raw_q)
    cid=(body.conversation_id or uuid.uuid4().hex)[:80]
    
    # 0. Check hard out-of-scope near-miss guardrails before any topic extraction
    is_near_miss, near_miss_cat = detect_out_of_scope_near_miss(raw_q, q)
    if is_near_miss:
        ans_indic = NEAR_MISS_EXPLANATIONS.get(near_miss_cat, {}).get(lang, OUT_OF_SCOPE[lang])
        ans_en = NEAR_MISS_EXPLANATIONS.get(near_miss_cat, {}).get("en", "I can only help with PF and ESIC questions.")
        log_speech_transcript(
            source=body.source or "api_ask",
            raw_transcript=raw_q,
            language=lang,
            call_id=cid,
            normalized_text=q,
            scope="out_of_scope",
            faq_id="",
            confidence_score=0.0,
            lexical_score=0.0,
            match_mode=f"near_miss_guardrail:{near_miss_cat}"
        )
        return {
            "understood": False,
            "scope": "out_of_scope",
            "out_of_scope_category": near_miss_cat,
            "answer": ans_indic,
            "english_translation": ans_en,
            "sources": [],
            "ticket_suggested": False,
            "conversation_id": cid,
            "confidence_score": 0.0,
            "lexical_score": 0.0,
            "match_mode": "out_of_scope_guardrail",
            "retrieval_score": 0.0,
            "retrieval_label": f"Out-of-scope near-miss ({near_miss_cat})"
        }

    history=CONVERSATIONS.setdefault(cid,[])
    previous_topic=next((x.get("topic") for x in reversed(history) if x.get("topic")),None)
    topic=topic_from(q,previous_topic)
    if not topic:
        rec_probe,sc_probe,_=KB.retrieve(q)
        if rec_probe and sc_probe >= settings.min_retrieval_score:
            topic="esic" if "esic" in (rec_probe.get("category","")+" "+rec_probe.get("question_en","")).lower() else "pf"
        else:
            log_speech_transcript(
                source=body.source or "api_ask",
                raw_transcript=raw_q,
                language=lang,
                call_id=cid,
                normalized_text=q,
                scope="out_of_scope",
                faq_id="",
                confidence_score=0.0,
                lexical_score=0.0,
                match_mode="none"
            )
            return {
                "understood": False,
                "scope": "out_of_scope",
                "answer": OUT_OF_SCOPE[lang],
                "english_translation": "I can only help with PF and ESIC questions. Please ask about PF, EPFO, UAN or ESIC.",
                "sources": [],
                "ticket_suggested": False,
                "conversation_id": cid,
                "confidence_score": 0.0,
                "lexical_score": 0.0,
                "match_mode": "out_of_scope",
                "retrieval_score": 0.0,
                "retrieval_label": "No PF/ESIC topic detected"
            }
    effective_query=q if DOMAIN_RE.search(q) else (q + (" PF" if topic=="pf" else " ESIC" if topic=="esic" else ""))
    qvec=await query_embedding(effective_query)
    retrieval_res=KB.retrieve(effective_query,qvec,topic)
    record,score,matches = retrieval_res[0], retrieval_res[1], retrieval_res[2]
    meta = getattr(retrieval_res, "meta", {})
    confidence_score = float(meta.get("confidence_score", score))
    lexical_score = float(meta.get("lexical_score", score))
    match_mode = str(meta.get("match_mode", "lexical_rag"))
    retrieval_label = str(meta.get("label", "Evidence match"))

    # Run through MCP pipeline by default
    mcp_evidence, mcp_tool_calls = await execute_mcp_pipeline(q, lang, topic)
    evidence=[]
    if record:
        a=record.get("answers",{})
        evidence.append({"id":record.get("id"),"category":record.get("category"),"source_group":record.get("source_group"),"question":record.get("question_en"),"answer_en":a.get("en"),"answer_hi":a.get("hi"),"answer_kn":a.get("kn"),"answer_ta":a.get("ta")})
    reviewed_chunks=retrieve_reviewed_document_chunks(effective_query,topic,qvec)
    for chunk in reviewed_chunks:
        evidence.append({"uploaded_policy_document":chunk["source_name"],"content":chunk["content"],"source_urls":chunk["source_urls"],"review_status":chunk["review_status"]})
    evidence.extend(mcp_evidence)
    threshold=settings.min_retrieval_score
    if not record or score < threshold or not evidence:
        log_speech_transcript(
            source=body.source or "api_ask",
            raw_transcript=raw_q,
            language=lang,
            call_id=cid,
            normalized_text=q,
            scope="pf_esic",
            faq_id=record.get("id") if record else "",
            confidence_score=confidence_score,
            lexical_score=lexical_score,
            match_mode=match_mode
        )
        return {
            "understood": False,
            "scope": "pf_esic",
            "answer": UNCLEAR[lang],
            "english_translation": "I could not verify an answer from the available PF/ESIC knowledge. Please rephrase or contact HR.",
            "sources": [],
            "ticket_suggested": needs_ticket(q, record),
            "conversation_id": cid,
            "confidence_score": round(confidence_score, 4),
            "lexical_score": round(lexical_score, 4),
            "match_mode": match_mode,
            "retrieval_score": round(confidence_score, 4),
            "retrieval_label": "Insufficient evidence",
            "mcp_used": bool(mcp_tool_calls),
            "mcp_tool_calls": mcp_tool_calls
        }
    answer_source="retrieved_faq"
    english=record.get("answers",{}).get("en","")
    answer=record.get("answers",{}).get(lang,"")
    llm_used=False
    provider_error=None
    if settings.llm_provider!="none":
        context=json.dumps(evidence,ensure_ascii=False)
        system=SYSTEM_TEMPLATE.format(language=LANGS[lang])
        user=f"User question: {q}\nSelected topic: {topic}\nRetrieved evidence (JSON):\n{context}\n\nWrite only a grounded response in {LANGS[lang]}. If evidence is inadequate, explicitly say that it cannot be verified."
        try:
            generated=await LLM.generate(system=system,user=user,history=history)
            if generated and len(generated)<5000:
                answer=generated; llm_used=True; answer_source="llm_grounded_rag"
                if body.include_english:
                    en_user=f"Translate the following answer faithfully into simple English. Preserve PF, UAN, EPFO and ESIC. Do not add facts:\n{generated}"
                    english=await LLM.generate(system="You are a faithful translator. Do not add information.",user=en_user,history=[])
        except Exception as e:
            provider_error=str(e)[:240]
    if not answer:
        log_speech_transcript(
            source=body.source or "api_ask",
            raw_transcript=raw_q,
            language=lang,
            call_id=cid,
            normalized_text=q,
            scope="pf_esic",
            faq_id=record.get("id"),
            confidence_score=confidence_score,
            lexical_score=lexical_score,
            match_mode=match_mode
        )
        return {
            "understood": False,
            "scope": "pf_esic",
            "answer": UNCLEAR[lang],
            "english_translation": "I could not verify an answer from the available PF/ESIC knowledge. Please contact HR.",
            "sources": [],
            "ticket_suggested": needs_ticket(q, record),
            "conversation_id": cid,
            "confidence_score": round(confidence_score, 4),
            "lexical_score": round(lexical_score, 4),
            "match_mode": match_mode,
            "retrieval_score": round(confidence_score, 4),
            "retrieval_label": "Insufficient evidence"
        }
    sources=source_payload(record)
    for chunk in reviewed_chunks:
        sources.append({"name":chunk["source_name"],"url":(chunk["source_urls"] or [None])[0],"verification":chunk["review_status"]})
    ticket=needs_ticket(q,record)
    history.extend([{"role":"user","content":q,"topic":topic},{"role":"assistant","content":answer,"topic":topic}]); del history[:-8]
    log_speech_transcript(
        source=body.source or "api_ask",
        raw_transcript=raw_q,
        language=lang,
        call_id=cid,
        normalized_text=q,
        scope="pf_esic",
        faq_id=record.get("id"),
        confidence_score=confidence_score,
        lexical_score=lexical_score,
        match_mode=match_mode
    )
    return {
        "understood": True,
        "scope": "pf_esic",
        "answer": answer,
        "english_translation": english if body.include_english else "",
        "faq_id": record.get("id"),
        "category": record.get("category"),
        "sources": sources,
        "retrieved_matches": matches[:3],
        "confidence_score": round(confidence_score, 4),
        "lexical_score": round(lexical_score, 4),
        "match_mode": match_mode,
        "retrieval_score": round(confidence_score, 4),
        "retrieval_label": retrieval_label,
        "answer_mode": answer_source,
        "llm_used": llm_used,
        "llm_error": provider_error,
        "mcp_used": bool(mcp_tool_calls),
        "mcp_tool_calls": mcp_tool_calls,
        "ticket_suggested": ticket,
        "conversation_id": cid
    }

@app.post("/api/tts")
async def tts(request:Request):
    data=await request.json(); text=str(data.get("text","")).strip(); lang=str(data.get("language","hi"))
    if lang not in LANGS: raise HTTPException(400,"Unsupported speech language")
    if not text or len(text)>1800: raise HTTPException(400,"Speech text must be 1 to 1800 characters")
    try: audio=await make_speech(text,lang)
    except Exception as e: raise HTTPException(503,"Cloud speech is not configured or unavailable; use browser speech fallback")
    return Response(content=audio,media_type="audio/mpeg",headers={"Cache-Control":"no-store"})

@app.post("/api/payslip/explain")
async def payslip_explain(body: PayslipInput):
    """Analyzes a payslip with deterministic statutory checks and provides multilingual explanation."""
    return analyze_payslip(body)

@app.post("/api/payslip/upload-ocr")
async def payslip_upload_ocr(file: UploadFile = File(...)):
    """Optional OCR/PDF parser. NEVER stores files; extracts text in-memory and falls back gracefully."""
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "Payslip file must be under 5 MB.")
    
    filename = (file.filename or "").lower()
    
    # Check for raster image uploads
    if filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        return {
            "success": False,
            "status": "ocr_not_installed",
            "message": "Direct image OCR is not installed in this environment. pypdf only reads digital PDF text.",
            "how_to_install": (
                "To enable optical character recognition for photos/scanned slips: "
                "1) Run 'pip install pytesseract pillow pdf2image', "
                "2) Install the Tesseract OCR engine (https://github.com/UB-Mannheim/tesseract/wiki), "
                "3) Configure TESSDATA_PREFIX. In the meantime, please use the recommended manual field entry."
            ),
            "manual_entry_recommended": True,
            "extracted_fields": {
                "basic_wage": None,
                "gross_salary": None,
                "employee_pf_deducted": None,
                "employee_esic_deducted": None,
                "employer_pf_contribution": None
            },
            "document_format": "raster_image",
            "privacy_guarantee": "Uploaded payslip was analyzed in volatile memory and was not written to disk."
        }
        
    extracted_text = ""
    if filename.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw))
            for page in reader.pages[:3]:
                extracted_text += (page.extract_text() or "") + "\n"
        except Exception:
            try:
                extracted_text = raw.decode("latin1", errors="ignore")
            except Exception:
                pass
    elif filename.endswith((".txt", ".csv")):
        try:
            extracted_text = raw.decode("utf-8", errors="ignore")
        except Exception:
            pass

    fields = extract_payslip_fields_from_text(extracted_text) if extracted_text else {
        "basic_wage": None,
        "gross_salary": None,
        "employee_pf_deducted": None,
        "employee_esic_deducted": None,
        "employer_pf_contribution": None
    }
    
    found_any = any(v is not None for v in fields.values())
    return {
        "success": found_any,
        "status": "success" if found_any else ("scanned_pdf_no_text" if filename.endswith(".pdf") else "no_fields_found"),
        "extracted_fields": fields,
        "manual_entry_recommended": not found_any,
        "message": (
            "Extracted numbers found from digital PDF text. Please review and confirm fields in manual entry."
            if found_any else
            ("This PDF has no digital text layer (scanned). Direct image OCR is not installed. Please use manual entry."
             if filename.endswith(".pdf") else
             "Automated extraction could not reliably identify payslip fields. Please use manual entry below.")
        ),
        "how_to_install": (
            "To enable optical character recognition for scanned PDFs: "
            "1) Run 'pip install pytesseract pillow pdf2image', "
            "2) Install the Tesseract OCR engine (https://github.com/UB-Mannheim/tesseract/wiki)."
            if not found_any and filename.endswith(".pdf") else ""
        ),
        "privacy_guarantee": "Uploaded payslip was analyzed in volatile memory and was not written to disk."
    }

def sync_query_benefits(question: str, language: str) -> dict:
    raw_q = (question or "").strip()
    lang = language.lower() if language in LANGS else "kn"
    if not raw_q:
        return {"understood": False, "answer": UNCLEAR.get(lang, ""), "ticket_suggested": False, "faq_id": "", "scope": "pf_esic", "mcp_tool_calls": []}
    q = full_normalize(raw_q)
    
    # Check in-scope exception prior to near-miss filter
    if not is_in_scope_pf_esic_query(raw_q, q):
        is_near_miss, near_miss_cat = detect_out_of_scope_near_miss(raw_q, q)
        if is_near_miss:
            ans_indic = NEAR_MISS_EXPLANATIONS.get(near_miss_cat, {}).get(lang, OUT_OF_SCOPE.get(lang, ""))
            log_speech_transcript("telephony_turn", raw_q, lang, normalized_text=q, scope="out_of_scope", match_mode=f"near_miss:{near_miss_cat}")
            return {"understood": False, "answer": ans_indic, "ticket_suggested": False, "faq_id": "", "scope": "out_of_scope", "mcp_tool_calls": []}
            
    mcp_tool_calls = []
    try:
        import saathi_mcp
        search_res = saathi_mcp.execute_mcp_tool("search_policy", {"query": q, "language": lang})
        mcp_tool_calls.append({"tool": "search_policy", "status": "success"})
        if re.search(r"\b(lakshmi|packer|my salary|my passbook|ಲಕ್ಷ್ಮಿ|लक्ष्मी|லட்சுமி)\b", q, re.I):
            rec_res = saathi_mcp.execute_mcp_tool("get_worker_payroll_record", {"worker_id": "EMP-LAKSHMI-001"})
            mcp_tool_calls.append({"tool": "get_worker_payroll_record", "status": "success"})
        if re.search(r"\b(balance|बैलेंस|ಬ್ಯಾಲೆನ್ಸ್|இருப்பு|activate|claim|withdraw|transfer)\b", q, re.I):
            howto_res = saathi_mcp.execute_mcp_tool("get_pf_howto", {"topic": "passbook", "language": lang})
            mcp_tool_calls.append({"tool": "get_pf_howto", "status": "success"})
    except Exception:
        pass

    topic = topic_from(q)
    if not topic:
        rec_probe, sc_probe, _ = KB.retrieve(q)
        if rec_probe and sc_probe >= settings.min_retrieval_score:
            topic = "esic" if "esic" in (rec_probe.get("category", "") + " " + rec_probe.get("question_en", "")).lower() else "pf"
        else:
            log_speech_transcript("telephony_turn", raw_q, lang, normalized_text=q, scope="out_of_scope", match_mode="out_of_scope")
            return {"understood": False, "answer": OUT_OF_SCOPE.get(lang, ""), "ticket_suggested": False, "faq_id": "", "scope": "out_of_scope", "mcp_tool_calls": mcp_tool_calls}
    effective_query = q if DOMAIN_RE.search(q) else (q + (" PF" if topic == "pf" else " ESIC"))
    res = KB.retrieve(effective_query, topic=topic)
    record, score, matches = res[0], res[1], res[2]
    meta = getattr(res, "meta", {})
    confidence_score = float(meta.get("confidence_score", score))
    lexical_score = float(meta.get("lexical_score", score))
    match_mode = str(meta.get("match_mode", "lexical_rag"))
    if not record or score < settings.min_retrieval_score:
        log_speech_transcript("telephony_turn", raw_q, lang, normalized_text=q, scope="pf_esic", match_mode="unclear")
        return {"understood": False, "answer": UNCLEAR.get(lang, ""), "ticket_suggested": needs_ticket(q, record), "faq_id": "", "scope": "pf_esic", "mcp_tool_calls": mcp_tool_calls}
    answers = record.get("answers", {})
    ans = answers.get(lang) or answers.get("en") or ""
    log_speech_transcript("telephony_turn", raw_q, lang, normalized_text=q, scope="pf_esic", faq_id=record.get("id"), confidence_score=confidence_score, lexical_score=lexical_score, match_mode=match_mode)
    return {
        "understood": True,
        "answer": ans,
        "ticket_suggested": needs_ticket(q, record),
        "faq_id": record.get("id"),
        "category": record.get("category"),
        "confidence_score": round(confidence_score, 4),
        "lexical_score": round(lexical_score, 4),
        "match_mode": match_mode,
        "retrieval_score": round(confidence_score, 4),
        "scope": "pf_esic",
        "mcp_tool_calls": mcp_tool_calls
    }

async def _parse_telephony_payload(request: Request) -> tuple[dict, bool]:
    ct = request.headers.get("content-type", "").lower()
    ua = request.headers.get("user-agent", "").lower()
    is_twiml = "twilio" in ua or "form" in ct or "xml" in request.headers.get("accept", "").lower()
    data: dict[str, Any] = {}
    if "json" in ct:
        try:
            data = await request.json()
        except Exception:
            data = {}
    elif "form" in ct:
        form = await request.form()
        data = dict(form)
    else:
        try:
            data = await request.json()
        except Exception:
            data = dict(request.query_params)
    return data, is_twiml

def _render_telephony(resp: TelephonyResponse, is_twiml: bool):
    if is_twiml:
        return Response(content=resp.to_twiml(), media_type="application/xml")
    return JSONResponse(resp.to_dict())

class SimulateBody(BaseModel):
    action: str = Field(default="start", description="start | digit | speech | command | hangup")
    call_id: str | None = None
    input: str = ""
    language: str | None = None

@app.api_route("/api/telephony/incoming", methods=["GET", "POST"])
async def telephony_incoming(request: Request):
    params, is_twiml = await _parse_telephony_payload(request)
    resp = telephony_service.incoming_call(params)
    return _render_telephony(resp, is_twiml)

@app.post("/api/telephony/language")
async def telephony_language(request: Request):
    params, is_twiml = await _parse_telephony_payload(request)
    call_sid = params.get("CallSid") or params.get("call_id") or "MOCK_CALL"
    digits = str(params.get("Digits") or params.get("digits") or "")
    speech = str(params.get("SpeechResult") or params.get("speech_text") or "")
    session = get_or_create_session(call_sid)
    resp = telephony_service.process_language_choice(session, digits, speech)
    return _render_telephony(resp, is_twiml)

@app.post("/api/telephony/gather")
async def telephony_gather(request: Request):
    params, is_twiml = await _parse_telephony_payload(request)
    call_sid = params.get("CallSid") or params.get("call_id") or "MOCK_CALL"
    speech = str(params.get("SpeechResult") or params.get("speech_text") or params.get("text") or "")
    session = get_or_create_session(call_sid)
    log_speech_transcript(
        source="telephony_ivr_webhook",
        raw_transcript=speech,
        language=session.language,
        call_id=call_sid,
        normalized_text=full_normalize(speech),
        scope=session.state,
        match_mode="telephony_gather"
    )
    resp = telephony_service.process_speech_turn(session, speech, sync_query_benefits)
    return _render_telephony(resp, is_twiml)

@app.post("/api/telephony/simulate")
async def telephony_simulate(body: SimulateBody):
    cid = body.call_id or f"CALL-{uuid.uuid4().hex[:8].upper()}"
    session = get_or_create_session(cid, caller_number="+91-9876543210 (Lakshmi - Warehouse)")
    if body.language and body.language in LANGS:
        session.language = body.language

    action = (body.action or "start").lower()
    if action == "start":
        resp = telephony_service.incoming_call({"call_id": cid})
    elif action in ("digit", "language"):
        resp = telephony_service.process_language_choice(session, body.input, "")
    elif action in ("speech", "command"):
        log_speech_transcript(
            source="browser_mic_simulator",
            raw_transcript=body.input or "",
            language=session.language,
            call_id=cid,
            normalized_text=full_normalize(body.input or ""),
            scope=session.state,
            match_mode="mic_simulator_turn"
        )
        resp = telephony_service.process_speech_turn(session, body.input, sync_query_benefits)
    elif action == "hangup":
        session.state = "ENDED"
        resp = TelephonyResponse(
            message="ಧನ್ಯವಾದಗಳು. ನಿಮ್ಮ ಕರೆ ಮುಕ್ತಾಯಗೊಂಡಿದೆ. / Call ended.",
            gather_speech=False,
            language=session.language,
            hangup=True
        )
    else:
        raise HTTPException(400, f"Unknown simulation action: {action}")

    return {
        "call_id": cid,
        "session": session.to_dict(),
        "response": resp.to_dict()
    }

@app.get("/api/speech-transcripts")
async def get_speech_transcripts(
    request: Request,
    limit: int = 50,
    authorization: str | None = Header(default=None),
    action: str | None = None
):
    # Security: Allow localhost or require valid admin Bearer token
    client_host = request.client.host if request.client else ""
    is_localhost = client_host in ("127.0.0.1", "::1", "localhost", "testclient")
    expected_token = settings.admin_token
    is_admin = bool(expected_token and authorization == f"Bearer {expected_token}")

    if not (is_localhost or is_admin):
        raise HTTPException(403, "Access to speech transcripts is restricted to localhost or authorized admin bearer token.")

    if action == "delete":
        if SPEECH_TRANSCRIPTS_PATH.is_file():
            SPEECH_TRANSCRIPTS_PATH.unlink()
        return {
            "ok": True,
            "message": "Speech transcripts purged successfully.",
            "retention_policy": "Transcripts are retained locally up to 30 days for quality assurance and human review. Purge anytime via ?action=delete or by deleting speech_transcripts.jsonl."
        }

    lines = []
    if SPEECH_TRANSCRIPTS_PATH.is_file():
        with open(SPEECH_TRANSCRIPTS_PATH, "r", encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    try:
                        lines.append(json.loads(l.strip()))
                    except Exception:
                        pass
    return {
        "total": len(lines),
        "transcripts": lines[-limit:],
        "privacy_note": "PII (UAN, Aadhaar, PAN, phone numbers, OTPs) is automatically masked prior to persistence.",
        "retention_policy": "Transcripts are retained locally up to 30 days for quality assurance and human review. Purge anytime via ?action=delete or by deleting speech_transcripts.jsonl."
    }

@app.get("/api/telephony/session/{call_id}")
async def telephony_session(call_id: str):
    if call_id not in CALL_SESSIONS:
        raise HTTPException(404, "Session not found")
    sess = CALL_SESSIONS[call_id]
    return {
        "call_id": call_id,
        "session": sess.to_dict(),
        "transcript": sess.history
    }

@app.get("/api/tickets")
async def list_tickets():
    with sqlite3.connect(DB) as c: rows=c.execute("SELECT id,title,description,question,category,faq_id,language,status,source,created_at,updated_at,external_id FROM tickets ORDER BY created_at DESC").fetchall()
    return {"tickets":[row_ticket(r) for r in rows]}
@app.post("/api/tickets")
async def create_ticket(body:TicketBody):
    if body.consent is not True: raise HTTPException(403,"Explicit employee permission is required")
    if body.language not in LANGS: raise HTTPException(400,"Invalid response language")
    category=body.category.strip()
    if not re.search(r"\b(PF|EPFO|ESIC|UAN)\b",category,re.I): raise HTTPException(400,"Only PF/EPFO/ESIC tickets are accepted")
    title=(body.title or category).strip(); description=(body.description or body.question).strip(); question=(body.question or (title+" — "+description)).strip()
    if len(question)<4: raise HTTPException(400,"Ticket details are required")
    external_id=""
    try:
        remote=await mcp_client.create_ticket(title,description,category,body.language)
        if remote and not remote.get("isError"):
            sc=remote.get("structuredContent") or {}
            external_id=str(sc.get("ticket_id") or sc.get("id") or "MCP_SUBMITTED")
    except Exception: external_id=""
    ticket_id="SAT-"+datetime.now().strftime("%Y%m%d")+"-"+uuid.uuid4().hex[:8].upper(); ts=now()
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO tickets (id,title,description,question,category,faq_id,language,status,source,created_at,updated_at,external_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(ticket_id,title,description,question,category,body.faqId,body.language,"Open",body.source,ts,ts,external_id));c.commit()
        row=c.execute("SELECT id,title,description,question,category,faq_id,language,status,source,created_at,updated_at,external_id FROM tickets WHERE id=?",(ticket_id,)).fetchone()
    return JSONResponse({"ticket":row_ticket(row),"delivery":"connected_hr" if external_id else "local_demo_only","message":"Ticket routed to connected HR MCP service." if external_id else "Saved locally for demonstration only. No HR system is connected."},status_code=201)
@app.patch("/api/tickets/{ticket_id}")
async def patch_ticket(ticket_id:str,body:StatusBody):
    if body.status not in {"Open","Closed"}: raise HTTPException(400,"Status must be Open or Closed")
    with sqlite3.connect(DB) as c:
        cur=c.execute("UPDATE tickets SET status=?,updated_at=? WHERE id=?",(body.status,now(),ticket_id));c.commit()
        if not cur.rowcount: raise HTTPException(404,"Ticket not found")
        row=c.execute("SELECT id,title,description,question,category,faq_id,language,status,source,created_at,updated_at,external_id FROM tickets WHERE id=?",(ticket_id,)).fetchone()
    return {"ticket":row_ticket(row)}

@app.get("/api/admin/status")
async def admin_status():
    mcp=await mcp_client.connect() if mcp_client.configured else {"connected":False,"reason":"not configured","tools":[]}
    return {"llm_provider":settings.llm_provider,"llm_configured":settings.llm_provider!="none" and bool(settings.llm_api_key or settings.anthropic_api_key or settings.gemini_api_key),"embedding_provider":settings.embedding_provider,"mcp":mcp,"tts_provider":settings.tts_provider,"tts_configured":settings.tts_provider=="openai" and bool(settings.tts_api_key or settings.llm_api_key)}

@app.post("/api/admin/ingest")
async def admin_ingest(files: list[UploadFile] = File(...), authorization: str | None = Header(default=None)):
    expected=settings.admin_token
    if not expected or authorization != "Bearer " + expected:
        raise HTTPException(401,"Admin bearer token required")
    from ingest import extract, chunks
    upload_dir=BASE_DIR/"uploads"; upload_dir.mkdir(exist_ok=True)
    added=0; details=[]
    for f in files:
        suffix=Path(f.filename or "").suffix.lower()
        if suffix not in {".pdf",".docx",".txt",".md",".html",".htm",".json",".csv",".xlsx"}:
            raise HTTPException(415,f"Unsupported document type: {suffix}")
        raw=await f.read()
        if len(raw)>12*1024*1024: raise HTTPException(413,"Each document must be smaller than 12 MB")
        safe=re.sub(r"[^a-zA-Z0-9._-]","_",Path(f.filename or "upload").name)
        dest=upload_dir/(uuid.uuid4().hex[:8]+"_"+safe); dest.write_bytes(raw)
        try:
            text=extract(dest); parts=chunks(text)
            with sqlite3.connect(DB) as c:
                c.execute("CREATE TABLE IF NOT EXISTS knowledge_chunks (id TEXT PRIMARY KEY, source_name TEXT, chunk_index INTEGER, domain TEXT, content TEXT, source_urls TEXT, review_status TEXT, verification_date TEXT, embedding TEXT, embedding_model TEXT)")
                for ix,content in enumerate(parts):
                    has_pf=bool(re.search(r"\b(pf|epf|provident fund|epfo|uan)\b",content,re.I))
                    has_esic=bool(re.search(r"\b(esic|esi|employee state insurance)\b",content,re.I))
                    if not (has_pf or has_esic): continue
                    domain="PF/ESIC" if has_pf and has_esic else "PF" if has_pf else "ESIC"
                    cid=uuid.uuid4().hex
                    urls=re.findall(r"https?://[^\s)\]>]+",content)
                    c.execute("INSERT INTO knowledge_chunks (id,source_name,chunk_index,domain,content,source_urls,review_status) VALUES (?,?,?,?,?,?,?)",(cid,f.filename,ix,domain,content,json.dumps(urls),"pending_review"));added+=1
                c.commit()
            details.append({"filename":f.filename,"status":"uploaded_pending_review","chunks":len(parts)})
        except Exception as e:
            details.append({"filename":f.filename,"status":"failed","error":str(e)[:200]})
    return {"ok":True,"chunks_added":added,"documents":details,"note":"Uploaded chunks are not used in answers until a policy owner reviews and marks them approved."}

# No permissive CORS by default. Deploy same-origin behind HTTPS/reverse proxy.
db_init()
