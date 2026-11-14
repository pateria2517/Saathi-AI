"""Saathi AI — Telephony Layer & Phone Call Pipeline.

Provides IVR flows, speech handling, control commands ("repeat", "slower", "talk to human"),
and webhook adapters for telephony platforms (Twilio / Exotel / Mock Provider).

NOTE ON TELEPHONY STT SUPPORT:
Do not assume or claim which Indic languages (Kannada, Hindi, Tamil) an external telephony provider's
built-in speech-to-text engine supports. Verify Kannada/Hindi/Tamil STT support, acoustic model availability,
and streaming audio capabilities directly with your chosen provider (e.g. Twilio Media Streams, Exotel Voice API,
or external STT bridges like Google Cloud Speech-to-Text).
"""
from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from config import settings


# Supported Telephony Languages
TELEPHONY_LANGUAGES: Dict[str, Dict[str, str]] = {
    "1": {"code": "hi", "name": "Hindi", "stt_locale": "hi-IN", "prompt": "नमस्ते, साथी AI में आपका स्वागत है। आप PF या ESIC के बारे में क्या जानना चाहते हैं?"},
    "2": {"code": "kn", "name": "Kannada", "stt_locale": "kn-IN", "prompt": "ನಮಸ್ಕಾರ, ಸಾಥಿ AI ಗೆ ಸ್ವಾಗತ. ನಿಮ್ಮ PF ಅಥವಾ ESIC ಕುರಿತು ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ."},
    "3": {"code": "ta", "name": "Tamil", "stt_locale": "ta-IN", "prompt": "வணக்கம், சாத்தி AI-க்கு வரவேற்கிறோம். உங்கள் PF அல்லது ESIC பற்றிய கேள்வியைக் கேளுங்கள்."}
}

IVR_WELCOME_PROMPT = (
    "Welcome to Saathi AI workplace benefits helpline. "
    "हिंदी के लिए 1 दबाएं। "
    "ಕನ್ನಡಕ್ಕಾಗಿ 2 ಒತ್ತಿರಿ. "
    "தமிழுக்கு 3 அழுத்தவும். "
    "Press 1 for Hindi, 2 for Kannada, 3 for Tamil. Or simply speak your question."
)

CONTROL_COMMANDS = {
    "repeat": re.compile(r"(\b(repeat|again|once more|tell me again|pardon)\b|ಮತ್ತೆ ಹೇಳಿ|ಪುನಃ ಹೇಳಿ|ಇನ್ನೊಮ್ಮೆ|ಮತ್ತೊಮ್ಮೆ|फिर से बोलो|दोबारा बोलो|மீண்டும் சொல்லுங்கள்|இன்னொரு முறை)", re.I),
    "slower": re.compile(r"(\b(slower|slowly|too fast|speak slowly)\b|ನಿಧಾನವಾಗಿ|ಮೆಲ್ಲಗೆ|ವೇಗ ಕಡಿಮೆ|धीरे बोलो|धीमे बोलो|धीरे|மெதுவாகப் பேசுங்கள்|மெதுவாக)", re.I),
    "human": re.compile(r"(\b(human|operator|supervisor|agent|person|helpdesk|hr|representative)\b|ಮಾನವ|ಮೇಲ್ವಿಚಾರಕ|ಅಧಿಕಾರಿ|ಸುಪರ್ವೈಸರ್|ಮಾನವ ಸಹಾಯ|सुपरवाइजर|इंसान|अधिकारी|बात करनी है|மனிதன்|மேற்பார்வையாளர்|அதிகாரி)", re.I),
}


class CallSession:
    """Tracks state and conversational history for a phone call."""
    def __init__(self, call_sid: str, caller_number: str = "MOCK_CALLER"):
        self.call_sid = call_sid
        self.caller_number = caller_number
        self.language: str = "kn"  # Default to Kannada for warehouse worker persona
        self.state: str = "MENU"  # MENU -> CONVERSATION -> HUMAN_ESCALATED -> ENDED
        self.history: list[dict] = []
        self.last_answer: str = ""
        self.last_question: str = ""
        self.speech_rate: float = 0.80  # Slower speed for low-literacy clarity
        self.human_escalated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_sid": self.call_sid,
            "caller_number": self.caller_number,
            "language": self.language,
            "state": self.state,
            "speech_rate": self.speech_rate,
            "human_escalated": self.human_escalated,
            "history_count": len(self.history)
        }


# In-memory call session registry (suitable for single-instance demo)
CALL_SESSIONS: Dict[str, CallSession] = {}


def get_or_create_session(call_sid: str, caller_number: str = "MOCK_CALLER") -> CallSession:
    if call_sid not in CALL_SESSIONS:
        CALL_SESSIONS[call_sid] = CallSession(call_sid, caller_number)
    return CALL_SESSIONS[call_sid]


class TelephonyResponse:
    """Generic representation of a telephony instruction."""
    def __init__(self, message: str, gather_speech: bool = True, gather_digits: bool = False,
                 language: str = "kn", speed: float = 0.80, hangup: bool = False,
                 mcp_tool_calls: Optional[List[Dict[str, Any]]] = None):
        self.message = message
        self.gather_speech = gather_speech
        self.gather_digits = gather_digits
        self.language = language
        self.speed = speed
        self.hangup = hangup
        self.mcp_tool_calls = mcp_tool_calls or []

    def to_twiml(self) -> str:
        """Render response as standard TwiML XML."""
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<Response>"]
        # SSML pacing pauses
        spoken = self.message.replace(".", '.<break time="500ms"/> ').replace(",", ',<break time="250ms"/> ')
        
        if self.gather_digits:
            xml.append('  <Gather numDigits="1" action="/api/telephony/language" method="POST" timeout="6">')
            xml.append(f'    <Say language="en-IN">{self.message}</Say>')
            xml.append("  </Gather>")
            xml.append('  <Redirect>/api/telephony/incoming</Redirect>')
        elif self.gather_speech:
            xml.append('  <Gather input="speech" action="/api/telephony/gather" method="POST" speechTimeout="auto" timeout="7">')
            xml.append(f'    <Say><prosody rate="{int(self.speed * 100)}%">{spoken}</prosody></Say>')
            xml.append("  </Gather>")
            xml.append('  <Say>We did not hear your question. Please call again or contact your HR.</Say>')
        else:
            xml.append(f'  <Say><prosody rate="{int(self.speed * 100)}%">{spoken}</prosody></Say>')
            
        if self.hangup:
            xml.append("  <Hangup/>")
        xml.append("</Response>")
        return "\n".join(xml)

    def to_exotel_json(self) -> Dict[str, Any]:
        """Render response in Exotel callback structure."""
        return {
            "select": {
                "text": self.message,
                "timeout": 6,
                "options": "123" if self.gather_digits else ""
            },
            "speed": self.speed,
            "language": self.language,
            "hangup": self.hangup,
            "mcp_tool_calls": self.mcp_tool_calls
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "gather_speech": self.gather_speech,
            "gather_digits": self.gather_digits,
            "language": self.language,
            "speed": self.speed,
            "hangup": self.hangup,
            "twiml": self.to_twiml(),
            "mcp_tool_calls": self.mcp_tool_calls
        }


class BaseTelephonyProvider(ABC):
    """Abstract interface for telephony platforms."""
    @abstractmethod
    def incoming_call(self, params: Dict[str, Any]) -> TelephonyResponse:
        pass

    @abstractmethod
    def process_language_choice(self, session: CallSession, digits: str, speech_text: str = "") -> TelephonyResponse:
        pass

    @abstractmethod
    def process_speech_turn(self, session: CallSession, speech_text: str, kb_query_fn: Any) -> TelephonyResponse:
        pass


class MockTelephonyProvider(BaseTelephonyProvider):
    """Production-grade mock provider for tests, browser simulator, and local demo."""

    def incoming_call(self, params: Dict[str, Any]) -> TelephonyResponse:
        call_sid = params.get("CallSid") or params.get("call_id") or f"CALL-{uuid.uuid4().hex[:8].upper()}"
        caller = params.get("From") or params.get("caller") or "+91-9876543210 (Lakshmi - Warehouse)"
        session = get_or_create_session(call_sid, caller)
        session.state = "MENU"
        return TelephonyResponse(
            message=IVR_WELCOME_PROMPT,
            gather_digits=True,
            gather_speech=True,
            language="en"
        )

    def process_language_choice(self, session: CallSession, digits: str, speech_text: str = "") -> TelephonyResponse:
        choice = digits.strip()
        if not choice and speech_text:
            low = speech_text.lower()
            if "kannada" in low or "ಕನ್ನಡ" in low: choice = "2"
            elif "hindi" in low or "हिंदी" in low: choice = "1"
            elif "tamil" in low or "தமிழ்" in low: choice = "3"

        if choice in TELEPHONY_LANGUAGES:
            cfg = TELEPHONY_LANGUAGES[choice]
            session.language = cfg["code"]
            session.state = "CONVERSATION"
            prompt = cfg["prompt"]
            return TelephonyResponse(
                message=prompt,
                gather_speech=True,
                gather_digits=False,
                language=session.language,
                speed=session.speech_rate
            )
        
        # Invalid input fallback
        return TelephonyResponse(
            message="Invalid selection. Press 1 for Hindi, 2 for Kannada, 3 for Tamil.",
            gather_digits=True,
            gather_speech=False,
            language="en"
        )

    def process_speech_turn(self, session: CallSession, speech_text: str, kb_query_fn: Any) -> TelephonyResponse:
        q = (speech_text or "").strip()
        lang = session.language
        
        # 1. Check Control Commands
        if CONTROL_COMMANDS["repeat"].search(q):
            reply = session.last_answer or (
                "ನಾನು ಇನ್ನೂ ಯಾವುದೇ ಉತ್ತರ ನೀಡಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ." if lang == "kn" else
                "मैंने अभी तक कोई उत्तर नहीं दिया है। कृपया अपना सवाल पूछें।" if lang == "hi" else
                "நான் இன்னும் பதிலளிக்கவில்லை. உங்கள் கேள்வியைக் கேளுங்கள்."
            )
            return TelephonyResponse(message=reply, gather_speech=True, language=lang, speed=session.speech_rate)

        if CONTROL_COMMANDS["slower"].search(q):
            session.speech_rate = max(0.65, session.speech_rate - 0.15)
            ack = (
                f"ಖಂಡಿತ, ನಾನು ನಿಧಾನವಾಗಿ ಮಾತನಾಡುತ್ತೇನೆ. {session.last_answer}" if lang == "kn" else
                f"ज़रूर, मैं और धीरे बोलूँगा। {session.last_answer}" if lang == "hi" else
                f"நிச்சயமாக, மெதுவாகப் பேசுகிறேன். {session.last_answer}"
            )
            return TelephonyResponse(message=ack, gather_speech=True, language=lang, speed=session.speech_rate)

        if CONTROL_COMMANDS["human"].search(q):
            session.human_escalated = True
            session.state = "HUMAN_ESCALATED"
            msg = (
                "ನಿಮ್ಮ ಸಮಸ್ಯೆಯನ್ನು ಮಾನವ HR ಅಧಿಕಾರಿಗೆ ವರ್ಗಾಯಿಸಲು ವಿನಂತಿ ಸಿದ್ಧಪಡಿಸಲಾಗಿದೆ. "
                "ನಾವು HR ಟಿಕೆಟ್ ರಚಿಸಬೇಕೇ? ದಯವಿಟ್ಟು ಒಪ್ಪಿಗೆ ನೀಡಲು 'ಹೌದು' ಅಥವಾ 'ಸರಿ' ಎಂದು ಹೇಳಿ." if lang == "kn" else
                "आपकी समस्या को मानव HR प्रतिनिधि को भेजने के लिए अनुरोध तैयार है। "
                "क्या हम HR टिकट दर्ज करें? कृपया सहमति के लिए 'हाँ' कहें।" if lang == "hi" else
                "உங்கள் கோரிக்கையை மனித HR அதிகாரியிடம் ஒப்படைக்க ஏற்பாடு செய்யப்பட்டுள்ளது. "
                "HR டிக்கெட் பதிவு செய்யவா? தயவுசெய்து 'ஆம்' என்று கூறுங்கள்."
            )
            return TelephonyResponse(message=msg, gather_speech=True, language=lang, speed=session.speech_rate)

        # 2. Query Knowledge Base through Pipeline
        res = kb_query_fn(q, lang)
        answer = res.get("answer") or ""
        session.last_question = q
        session.last_answer = answer
        session.history.append({"role": "user", "text": q})
        session.history.append({"role": "assistant", "text": answer})

        # Append human escalation advice if flagged by KB
        if res.get("ticket_suggested"):
            note = (
                " ಈ ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಲು HR ಟಿಕೆಟ್ ಅಗತ್ಯವಿದೆ. ಟಿಕೆಟ್ ರಚಿಸಲು 'ಮಾನವ ಸಹಾಯ' ಎಂದು ಹೇಳಿ." if lang == "kn" else
                " इस मामले की जाँच के लिए HR टिकट की सलाह दी जाती है। टिकट के लिए 'HR से बात' कहें।" if lang == "hi" else
                " இதைச் சரிபார்க்க HR டிக்கெட் பரிந்துரைக்கப்படுகிறது. டிக்கெட் உருவாக்க 'HR உதவி' என்று கூறுங்கள்."
            )
            answer += note

        mcp_calls = res.get("mcp_tool_calls", [])
        return TelephonyResponse(
            message=answer,
            gather_speech=True,
            language=lang,
            speed=session.speech_rate,
            mcp_tool_calls=mcp_calls
        )


# Instantiate default provider (MockTelephonyProvider by default for offline robustness)
telephony_service = MockTelephonyProvider()
