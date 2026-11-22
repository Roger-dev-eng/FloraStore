"""Conversa com RAG executada no próprio processo do Streamlit."""

from dataclasses import dataclass

from assistant.groq_client import GroqClient
from assistant.rag import VectorKnowledgeBase


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class ChatAssistant:
    def __init__(self, settings):
        self.knowledge = VectorKnowledgeBase(settings)
        self.llm = GroqClient(settings.groq_key, settings.groq_model)

    def answer(self, question, history):
        question = question.strip()
        if not question or len(question) > 1000:
            raise ValueError("Digite uma pergunta de até 1000 caracteres.")
        messages = [
            ChatMessage(item["role"], str(item["content"])[:5000])
            for item in history[-8:]
            if item.get("role") in {"user", "assistant"} and item.get("content")
        ]
        previous = next((item.content for item in reversed(messages) if item.role == "user"), "")
        retrieval = self.knowledge.retrieve(question, previous)
        answer = (
            self.llm.answer(question, retrieval.context, messages)
            if retrieval.sources else
            "Não encontrei essa informação na base da FloraStore. Pode detalhar sua dúvida "
            "ou confirmar com a loja pelo WhatsApp?"
        )
        return {"role": "assistant", "content": answer, "sources": retrieval.sources}

    def close(self):
        self.llm.close()
        self.knowledge.close()
