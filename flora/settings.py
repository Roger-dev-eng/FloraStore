import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    supabase_url: str = ""
    supabase_key: str = ""
    mongodb_uri: str = ""
    mongodb_database: str = "florastore"
    redis_url: str = ""
    whatsapp_number: str = ""


def load_settings(secrets=None):
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
    )
