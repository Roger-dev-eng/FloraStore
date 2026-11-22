"""Prepara segredos locais e a credencial do fluxo n8n sem exibi-los no terminal."""

import json
import os
import secrets
import tomllib

from dotenv import dotenv_values

from flora.settings import PROJECT_ROOT


def main():
    env_path = PROJECT_ROOT / ".env"
    local_env = dotenv_values(env_path) if env_path.exists() else {}
    secrets_path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    content = secrets_path.read_text(encoding="utf-8-sig") if secrets_path.exists() else ""
    store = tomllib.loads(content)
    additions = {}
    key = os.getenv("ASSISTANT_API_KEY") or local_env.get("ASSISTANT_API_KEY") or store.get("ASSISTANT_API_KEY")
    if not key:
        key = secrets.token_urlsafe(32)
    if not store.get("ASSISTANT_API_KEY"):
        additions["ASSISTANT_API_KEY"] = key
    if not store.get("N8N_WEBHOOK_URL"):
        additions["N8N_WEBHOOK_URL"] = "http://localhost:5678/webhook/florastore-assistant"
    if additions:
        with secrets_path.open("a", encoding="utf-8") as output:
            output.write("\n# Assistente local\n")
            output.writelines(f"{name} = {json.dumps(value)}\n" for name, value in additions.items())

    if not local_env.get("GROQ_API_KEY") and not os.getenv("GROQ_API_KEY"):
        chatbot_env = PROJECT_ROOT.parent / "ChatBot" / ".env"
        if chatbot_env.exists():
            groq_key = dotenv_values(chatbot_env).get("GROQ_API_KEY")
            if groq_key:
                with env_path.open("a", encoding="utf-8") as output:
                    output.write(f"\nGROQ_API_KEY={json.dumps(groq_key)}\n")
                print("Chave Groq reaproveitada do ChatBot no arquivo .env local.")
            else:
                print("Configure GROQ_API_KEY no arquivo .env local.")
        else:
            print("Configure GROQ_API_KEY no arquivo .env local.")

    directory = PROJECT_ROOT / ".assistant_data" / "n8n"
    directory.mkdir(parents=True, exist_ok=True)
    credentials = [{
        "id": "floraAssistantHeader", "name": "FloraStore local",
        "type": "httpHeaderAuth", "data": {"name": "X-Flora-Key", "value": key},
    }]
    (directory / "credentials.json").write_text(json.dumps(credentials), encoding="utf-8")
    print("Credencial local do n8n preparada em .assistant_data/n8n/credentials.json.")
    print("Execute scripts/setup_vectors.sql no Supabase e preencha SUPABASE_SERVICE_KEY em .streamlit/secrets.toml.")


if __name__ == "__main__":
    main()
