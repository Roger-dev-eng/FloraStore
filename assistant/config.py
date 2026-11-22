import os
import tomllib
from dataclasses import dataclass, field

from dotenv import load_dotenv

from flora.settings import PROJECT_ROOT, load_settings


@dataclass(frozen=True)
class AssistantSettings:
    api_key: str = field(repr=False)
    groq_key: str = field(repr=False)
    groq_model: str
    supabase_url: str
    supabase_service_key: str = field(repr=False)
    mongodb_uri: str = field(repr=False)
    mongodb_database: str


def load_assistant_settings():
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    store = load_settings()
    values = {
        "ASSISTANT_API_KEY": os.getenv("ASSISTANT_API_KEY", ""),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
        "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY", ""),
    }
    path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    local = tomllib.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    for key in values:
        values[key] = values[key] or str(local.get(key, ""))
    missing = [key for key, value in values.items() if not value]
    if not store.supabase_url:
        missing.append("SUPABASE_URL")
    if not store.mongodb_uri:
        missing.append("MONGODB_URI")
    if missing:
        raise ValueError(f"Configure {', '.join(missing)} para iniciar o assistente.")
    return AssistantSettings(
        api_key=values["ASSISTANT_API_KEY"], groq_key=values["GROQ_API_KEY"],
        groq_model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        supabase_url=store.supabase_url,
        supabase_service_key=values["SUPABASE_SERVICE_KEY"],
        mongodb_uri=store.mongodb_uri, mongodb_database=store.mongodb_database,
    )
