"""Saathi AI — Application Configuration & Settings.

Loads environment variables from .env with fallback defaults for a zero-key offline demo.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent

# Optional: Try loading from .env file
def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'").strip()
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

_load_env_file(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        # Paths
        self.base_dir: Path = BASE_DIR
        self.knowledge_path: str = os.getenv(
            "KNOWLEDGE_PATH",
            str(BASE_DIR / "Saathi_AI_combined_710_faq_1.json")
        )
        self.database_path: str = os.getenv(
            "DATABASE_PATH",
            str(BASE_DIR / "saathi_demo.sqlite3")
        )
        self.static_dir: str = os.getenv(
            "STATIC_DIR",
            str(BASE_DIR)
        )

        # Host and Port
        self.host: str = os.getenv("HOST", "127.0.0.1")
        self.port: int = int(os.getenv("PORT", "8000"))

        # Offline & Provider Modes
        # Default is "none" for offline local operation without any paid keys
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "none").lower()
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

        # Embeddings
        self.embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "none").lower()
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")
        self.embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")

        # Text-To-Speech (TTS)
        # Default: "browser" (zero-key web SpeechSynthesis fallback)
        self.tts_provider: str = os.getenv("TTS_PROVIDER", "browser").lower()
        self.tts_api_key: str = os.getenv("TTS_API_KEY", "")
        self.tts_base_url: str = os.getenv("TTS_BASE_URL", "https://api.openai.com/v1")
        self.tts_model: str = os.getenv("TTS_MODEL", "tts-1")
        self.tts_voice: str = os.getenv("TTS_VOICE", "coral")

        # MCP Configuration
        self.mcp_server_url: str = os.getenv("MCP_SERVER_URL", "")
        self.mcp_auth_token: str = os.getenv("MCP_AUTH_TOKEN", "")
        self.mcp_protocol_version: str = os.getenv("MCP_PROTOCOL_VERSION", "2024-11-05")

        # Admin & Security
        self.admin_token: str = os.getenv("ADMIN_TOKEN", "saathi_dev_admin_secret_token")

        # Retrieval Calibration
        # Calibrated minimum score (replaces uncalibrated 0.80)
        self.min_retrieval_score: float = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.35"))

        # Telephony Simulation / Provider Keys
        self.telephony_provider: str = os.getenv("TELEPHONY_PROVIDER", "simulator").lower()
        self.telephony_account_sid: str = os.getenv("TELEPHONY_ACCOUNT_SID", "")
        self.telephony_auth_token: str = os.getenv("TELEPHONY_AUTH_TOKEN", "")
        self.telephony_phone_number: str = os.getenv("TELEPHONY_PHONE_NUMBER", "")


settings = Settings()
