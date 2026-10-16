"""The AI brain — with a FREE default provider.

We use the OpenAI-compatible client for BOTH providers:
  - AI_PROVIDER=groq   -> FREE Groq API (default, no credit card needed)
  - AI_PROVIDER=openai -> Paid OpenAI API (optional upgrade, same code)

Groq free tier (perpetual, no card): https://console.groq.com/docs/rate-limits
  - Whisper: 25 MB per request, 28,800 audio-seconds/day
  - Chat: generous per-minute/per-day token limits
"""

from openai import OpenAI

from app.config import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def make_ai_client() -> OpenAI:
    """One client for both transcription and highlight detection."""
    if settings.ai_provider == "openai":
        return OpenAI(api_key=settings.openai_api_key)
    return OpenAI(api_key=settings.groq_api_key, base_url=GROQ_BASE_URL)


def whisper_model() -> str:
    """Automatic default per provider; override anytime with WHISPER_MODEL."""
    if settings.whisper_model:
        return settings.whisper_model
    return "whisper-1" if settings.ai_provider == "openai" else "whisper-large-v3-turbo"


def chat_model() -> str:
    """Automatic default per provider; override anytime with GPT_MODEL."""
    if settings.gpt_model:
        return settings.gpt_model
    return "gpt-4o" if settings.ai_provider == "openai" else "openai/gpt-oss-120b"
