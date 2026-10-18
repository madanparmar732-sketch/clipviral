"""Central configuration. Every setting can be overridden with an environment variable."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OpusClip Clone API"

    # Secrets / external services
    openai_api_key: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""

    # Networking
    cors_origins: str = "http://localhost:3000"

    # Storage / files
    media_dir: str = "./media"
    clips_bucket: str = "clips"
    max_upload_mb: int = 512

    # AI provider: "groq" = FREE (default, no credit card) | "openai" = paid upgrade
    ai_provider: str = "groq"
    groq_api_key: str = ""
    openai_api_key: str = ""
    whisper_model: str = ""  # empty = automatic per provider
    gpt_model: str = ""      # empty = automatic per provider
    chat_temperature: float = 0.3  # low temperature keeps the AI's JSON answers valid
    top_n_clips: int = 6
    clip_min_seconds: int = 15
    clip_max_seconds: int = 40  # shorter = much faster renders + better for shorts
    # Keep only the newest N videos per account; older ones are auto-deleted.
    max_videos_per_account: int = 4
    # Free plan: how many videos per calendar month (Pro = unlimited)
    free_videos_per_month: int = 3
    # Comma-separated Pro activation codes (owner hands these out after payment)
    pro_codes: str = "CLIP-N28E-HCC7,CLIP-R635-UAAW,CLIP-E264-B49K,CLIP-XZYX-F65R,CLIP-ASYK-7DKY,CLIP-DHVV-2XVS,CLIP-SM47-3Z8S,CLIP-T3G3-G4E4,CLIP-CV77-4VYE,CLIP-ZTD4-8K67"

    # When 1: this box SKIPS job execution — a Termux phone worker owns
    # jobs instead (app/services/lease.py). Render dashboard env var CLIPVIRAL_PHONE_WORKER=1.
    phone_worker: bool = False

    # ---- NIGHT BATCH / LAZY RENDERING (the "100 videos on a tiny CPU" trick) ----
    # Analysis + clip CARDS land instantly; the heavy encoder for the clips the
    # user isn't watching right now runs in the quiet night window instead.
    night_batch: bool = False            # enable via CLIPVIRAL_NIGHT_BATCH=1
    night_start_hour: float = 1.5        # IST hour the night window opens
    night_end_hour: float = 6.5          # ...and closes
    night_copy_first: int = 3            # render this many clips eagerly (top scores)

    # Extra "recap reel" made with MoviePy (needs more RAM, off by default)
    recap_enabled: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
