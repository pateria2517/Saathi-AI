"""Saathi AI — Indic & Multilingual Normalization Engine.

Driven by aliases.json to map spoken/phonetic forms in Hindi, Kannada, and Tamil script
to canonical Latin terms (PF, EPF, EPFO, UAN, ESIC, ESI, passbook, nominee, claim,
withdrawal, KYC, pension, EPS, EDLI, payslip, deduction, HR, supervisor).

Performs Unicode NFC normalization, punctuation cleaning, and Indic question-word suppression.
"""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from config import BASE_DIR

ALIASES_FILE = BASE_DIR / "aliases.json"


def load_aliases() -> dict[str, list[str]]:
    if ALIASES_FILE.is_file():
        try:
            with open(ALIASES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def build_alias_replacements(aliases_data: dict[str, list[str]]) -> list[tuple[re.Pattern, str]]:
    """Build compiled regex replacements ordered by variant length descending."""
    rules = []
    word_char_pattern = r"[\w\u0900-\u0d7f\u0c80-\u0cff]"
    for canonical, variants in aliases_data.items():
        for var in variants:
            v = unicodedata.normalize("NFC", var.strip())
            if not v:
                continue
            escaped = re.escape(v)
            # Use negative lookbehind/lookahead instead of \b so dotted terms (e.g. पी.एफ.) and Indic scripts match cleanly
            pat = re.compile(rf"(?<!{word_char_pattern}){escaped}(?!{word_char_pattern})", re.I | re.UNICODE)
            rules.append((len(v), pat, canonical))
    # Longest match first to prioritize e.g. 'कर्मचारी भविष्य निधि' over 'भविष्य निधि'
    rules.sort(key=lambda x: x[0], reverse=True)
    return [(pat, canonical) for _, pat, canonical in rules]


ALIASES_MAP = load_aliases()
ALIAS_REPLACEMENTS = build_alias_replacements(ALIASES_MAP)

# Common Indic question words, auxiliaries, and copulas to suppress during BM25/lexical matching
INDIC_STOPWORDS = {
    # Hindi
    "क्या", "होता", "होती", "होते", "होना", "है", "हैं", "था", "थी", "थे", "का", "की", "के", "में", "से", "को", "पर", "ने",
    "और", "या", "कृपया", "बताएं", "बताओ", "बताइए", "चाहिए", "सकते", "सकता", "सकती", "मुझे", "मेरा", "मेरी", "मेरे",
    "हमारा", "हमारे", "आप", "आपका", "आपके", "कहा", "कैसे", "कहाँ", "कब", "कितना", "कितनी", "चीज", "बारे", "लिए",
    "करना", "करे", "करें", "सकूं", "सकते_हैं", "हुआ", "हुई", "गया", "गई", "गए",
    # Kannada
    "ಏನು", "ಹೇಗೆ", "ಆಗುತ್ತದೆ", "ಆಗುತ್ತೆ", "ಆಗುವುದು", "ಇದೆ", "ಇತ್ತ", "ಇಲ್ಲ", "ಮಾಡಬೇಕು", "ಮಾಡಲಿ", "ಮಾಡುತ್ತಾರೆ",
    "ಎಲ್ಲಿ", "ಯಾವಾಗ", "ಯಾರು", "ಯಾಕೆ", "ಏಕೆ", "ನನ್ನ", "ನನಗೆ", "ನಮ್ಮ", "ದಯವಿಟ್ಟು", "ಹೇಳಿ", "ತಿಳಿಸಿ", "ಬಗ್ಗೆ",
    "ಅಥವಾ", "ಮತ್ತು", "ಅಂದರೆ", "ಎಂದರೇನು", "ಅಂದ್ರೆ", "ಬೇಕು", "ಬಹುದು", "ಕೊಡಿ", "ಆಗಿದೆ", "ಬಂದಿದೆ",
    # Tamil
    "என்ன", "எப்படி", "ஆகும்", "இருக்கும்", "இல்லை", "எங்கே", "எப்போது", "யார்", "எனக்கு", "என்", "எங்கள்",
    "தயவுசெய்து", "சொல்லுங்கள்", "பற்றி", "அல்லது", "மற்றும்", "வேண்டும்", "என்றால்", "என்பது", "கூறுங்கள்",
    "தெரிந்து", "கொள்ள", "செய்வது", "ஆகிறது", "வந்தது"
}


def normalize_indic_text(text: str) -> str:
    """Normalize Unicode to NFC and clean stray punctuation."""
    if not text:
        return ""
    # 1. Unicode NFC
    t = unicodedata.normalize("NFC", text)
    # 2. Punctuation to space (preserves Indic script characters and Latin alphanumeric)
    t = re.sub(r"[\.,\?!:;\"'״׳\(\)\[\]\{\}_/\\—\-\।\॥]+", " ", t)
    # 3. Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def apply_aliases(text: str) -> str:
    """Map spoken/phonetic Indic and Latin acronym variants to canonical terms."""
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    for pat, canonical in ALIAS_REPLACEMENTS:
        t = pat.sub(canonical, t)
    return t


def full_normalize(text: str) -> str:
    """Full normalization pipeline: NFC -> Aliases -> Cleaned text."""
    nfc = normalize_indic_text(text)
    return apply_aliases(nfc)
