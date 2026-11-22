import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    supabase_url: str = ""
    supabase_key: str = ""
    mongodb_uri: str = ""
    mongodb_database: str = "florastore"
    redis_url: str = ""
    whatsapp_number: str = ""
    groq_key: str = field(default="", repr=False)
    groq_model: str = "qwen/qwen3.8-27b"
    supabase_service_key: str = field(default="", repr=False)


def load_settings(secrets=None):
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    if secrets is None:
        path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
        secrets = tomllib.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}

    def value(name, default=""):
        return str(os.environ.get(name, secrets.get(name, default))).strip()

    return Settings(
        supabase_url=value("SUPABASE_URL").rstrip("/"),
        supabase_key=value("SUPABASE_KEY"),
        mongodb_uri=value("MONGODB_URI"),
        mongodb_database=value("MONGODB_DATABASE", "florastore") or "florastore",
        redis_url=value("REDIS_URL"),
        whatsapp_number=value("WHATSAPP_NUMBER"),
        groq_key=value("GROQ_API_KEY"),
        groq_model=value("GROQ_MODEL", "qwen/qwen3.8-27b") or "qwen/qwen3.8-27b",
        supabase_service_key=value("SUPABASE_SERVICE_KEY"),
    )
