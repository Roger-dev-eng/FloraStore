from urllib.parse import urlsplit
import logging

import streamlit as st


LOGGER = logging.getLogger(__name__)


@st.cache_resource(max_entries=1, show_spinner=False)
def get_assistant(settings):
    # Importa e carrega o modelo somente quando o cliente faz uma pergunta.
    from assistant.service import ChatAssistant

    return ChatAssistant(settings)


def send_question(settings, question, history):
    return get_assistant(settings).answer(question, history)


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
                configured = bool(settings.supabase_url and settings.supabase_service_key
                                  and settings.mongodb_uri and settings.groq_key)
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
                            except Exception as error:
                                # Registra só o tipo: URLs de conexão e chaves não vão para os logs.
                                LOGGER.warning("Assistente indisponível (%s)", type(error).__name__)
                                answer = {"role": "assistant", "error": True,
                                          "content": "O assistente está indisponível agora. Tente novamente em instantes."}
                        with st.chat_message("assistant"):
                            if answer.get("error"):
                                st.error(answer["content"])
                            else:
                                st.write(answer["content"])
                                show_sources(answer.get("sources", []))
                    messages.append(answer)
                    st.session_state.assistant_messages = messages[-24:]
