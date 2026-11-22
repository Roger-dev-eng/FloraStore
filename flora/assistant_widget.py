from urllib.parse import urlsplit

import httpx
import streamlit as st


def send_question(settings, question, history):
    response = httpx.post(
        settings.n8n_webhook_url, timeout=65,
        headers={"X-Flora-Key": settings.assistant_api_key},
        json={"question": question, "history": history},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str) or not payload["answer"].strip():
        raise ValueError("Resposta inválida do assistente.")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []
    return {"role": "assistant", "content": payload["answer"], "sources": sources}


def show_sources(sources):
    if not sources:
        return
    with st.expander("Fontes consultadas"):
        for source in sources[:6]:
            if not isinstance(source, dict):
                continue
            title = str(source.get("title", "Catálogo FloraStore"))
            number = source.get("number", "")
            url = str(source.get("url", ""))
            if urlsplit(url).scheme == "https":
                st.link_button(f"[{number}] {title}", url)
            else:
                st.text(f"[{number}] {title}")


@st.fragment
def show_assistant(settings):
    with st.container(key="assistant_launcher"):
        with st.popover(
            "Conversar com a FloraStore", icon=":material/chat_bubble:",
            type="primary", key="assistant_popover",
        ):
            with st.container(key="assistant_panel"):
                title, action = st.columns([4, 1])
                with title:
                    st.subheader("Assistente FloraStore")
                with action:
                    clear = st.button("Nova conversa", icon=":material/delete_sweep:", key="assistant_clear",
                                      type="tertiary", help="Apagar esta conversa")
                if clear:
                    st.session_state.assistant_messages = []
                messages = st.session_state.setdefault("assistant_messages", [])
                with st.container(height=290, key="assistant_history", autoscroll=True):
                    if not messages:
                        st.chat_message("assistant").write("Olá! Posso ajudar a conhecer as plantas e escolher entre os produtos da loja. O que você procura?")
                    for message in messages:
                        with st.chat_message(message["role"]):
                            if message.get("error"):
                                st.error(message["content"])
                            else:
                                st.write(message["content"])
                                show_sources(message.get("sources", []))
                    pending = st.empty()
                configured = bool(settings.n8n_webhook_url and settings.assistant_api_key)
                if not configured:
                    st.caption("O atendimento virtual estará disponível em breve.")
                question = st.chat_input("Pergunte sobre as plantas…", max_chars=1000,
                                         disabled=not configured, key="assistant_question")
                if question and question.strip():
                    history = [{"role": item["role"], "content": item["content"]}
                               for item in messages[-8:] if not item.get("error")]
                    messages.append({"role": "user", "content": question.strip()})
                    with pending.container():
                        st.chat_message("user").write(question.strip())
                        with st.spinner("Consultando as plantas…"):
                            try:
                                answer = send_question(settings, question.strip(), history)
                            except (httpx.HTTPError, ValueError):
                                answer = {"role": "assistant", "error": True,
                                          "content": "O assistente está indisponível agora. Tente novamente em instantes."}
                    messages.append(answer)
                    st.session_state.assistant_messages = messages[-24:]
                    st.rerun(scope="fragment")
