from __future__ import annotations
import base64
import json
import re
from typing import Any
import httpx
from config import settings

class ProviderError(RuntimeError):
    pass

class LLMProvider:
    """Provider-independent text generation adapter (OpenAI-compatible, Anthropic, Gemini)."""
    async def generate(self, *, system: str, user: str, history: list[dict] | None = None) -> str:
        provider = settings.llm_provider
        history = history or []
        if provider in {"openai", "openai-compatible", "groq", "openrouter", "custom"}:
            key = settings.llm_api_key
            if not key:
                raise ProviderError("LLM_API_KEY is not configured")
            base = settings.llm_base_url.rstrip("/")
            messages = [{"role": "system", "content": system}]
            messages.extend({"role": x["role"], "content": x["content"]} for x in history[-6:] if x.get("role") in {"user", "assistant"})
            messages.append({"role": "user", "content": user})
            payload = {"model": settings.llm_model, "messages": messages, "temperature": 0.15}
            async with httpx.AsyncClient(timeout=45) as client:
                res = await client.post(base + "/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=payload)
                res.raise_for_status(); data = res.json()
            return str(data["choices"][0]["message"]["content"]).strip()
        if provider == "anthropic":
            key = settings.anthropic_api_key or settings.llm_api_key
            if not key: raise ProviderError("ANTHROPIC_API_KEY is not configured")
            messages = [{"role": x["role"], "content": x["content"]} for x in history[-6:] if x.get("role") in {"user", "assistant"}]
            messages.append({"role": "user", "content": user})
            payload = {"model": settings.llm_model, "max_tokens": 700, "system": system, "messages": messages, "temperature": 0.15}
            async with httpx.AsyncClient(timeout=45) as client:
                res = await client.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=payload)
                res.raise_for_status(); data = res.json()
            return "\n".join(p.get("text", "") for p in data.get("content", []) if p.get("type") == "text").strip()
        if provider == "gemini":
            key = settings.gemini_api_key or settings.llm_api_key
            if not key: raise ProviderError("GEMINI_API_KEY is not configured")
            history_text = "\n".join(f"{x['role']}: {x['content']}" for x in history[-6:] if x.get("role") in {"user", "assistant"})
            prompt = f"{system}\n\nConversation context:\n{history_text}\n\nUser question:\n{user}"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.llm_model}:generateContent?key={key}"
            async with httpx.AsyncClient(timeout=45) as client:
                res = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.15, "maxOutputTokens": 700}})
                res.raise_for_status(); data = res.json()
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
        raise ProviderError("No LLM provider configured")

async def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider not in {"openai", "openai-compatible"} or not settings.embedding_api_key:
        raise ProviderError("Embedding provider is not configured")
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(settings.embedding_base_url.rstrip("/") + "/embeddings", headers={"Authorization": f"Bearer {settings.embedding_api_key}"}, json={"model": settings.embedding_model, "input": texts})
        res.raise_for_status(); data = res.json()
    return [x["embedding"] for x in sorted(data["data"], key=lambda x: x["index"])]

async def make_speech(text: str, lang: str) -> bytes:
    key = settings.tts_api_key or settings.llm_api_key
    if settings.tts_provider != "openai" or not key:
        raise ProviderError("Cloud TTS is not configured; use the browser voice fallback")
    instructions = {
        "hi": "Speak clear, natural Hindi at a calm, slightly slower pace. Keep PF, UAN, EPFO and ESIC pronounced clearly.",
        "kn": "Speak clear, natural Kannada at a calm, slightly slower pace. Keep PF, UAN, EPFO and ESIC pronounced clearly.",
        "ta": "Speak clear, natural Tamil at a calm, slightly slower pace. Keep PF, UAN, EPFO and ESIC pronounced clearly."
    }[lang]
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(settings.tts_base_url.rstrip("/") + "/audio/speech", headers={"Authorization": f"Bearer {key}"}, json={"model": settings.tts_model, "voice": settings.tts_voice, "input": text, "instructions": instructions, "speed": 0.86, "response_format": "mp3"})
        res.raise_for_status(); return res.content
