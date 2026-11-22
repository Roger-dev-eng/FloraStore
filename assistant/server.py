import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from hmac import compare_digest
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from assistant.config import load_assistant_settings
from assistant.groq_client import GroqClient
from assistant.rag import MODEL_NAME, VectorKnowledgeBase


LOGGER = logging.getLogger(__name__)
REQUEST_TTL = 180


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=5000)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[Message] = Field(default_factory=list, max_length=8)


class AnswerRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=50)


class AssistantService:
    def __init__(self, settings):
        self.knowledge = VectorKnowledgeBase(settings)
        self.llm = GroqClient(settings.groq_key, settings.groq_model)
        try:
            self.count = self.knowledge.sync()
        except Exception:
            self.close()
            raise
        self.pending = {}
        self.lock = Lock()

    def retrieve(self, question):
        text = question.question.strip()
        if not text:
            raise HTTPException(422, "Digite uma pergunta.")
        previous_question = next((item.content for item in reversed(question.history) if item.role == "user"), "")
        retrieval = self.knowledge.retrieve(text, previous_question)
        self.count = retrieval.indexed_documents
        request_id = uuid4().hex
        with self.lock:
            now = monotonic()
            self.pending = {key: value for key, value in self.pending.items() if value[0] > now}
            if len(self.pending) >= 64:
                raise HTTPException(429, "Aguarde um instante e tente novamente.")
            self.pending[request_id] = (now + REQUEST_TTL, retrieval, question.history)
        return {"request_id": request_id, **asdict(retrieval), "embedding_model": MODEL_NAME}

    def answer(self, request_id):
        with self.lock:
            pending = self.pending.pop(request_id, None)
        if pending is None or pending[0] <= monotonic():
            raise HTTPException(409, "Esta consulta expirou. Faça a pergunta novamente.")
        _, retrieval, history = pending
        if retrieval.sources:
            answer = self.llm.answer(retrieval.question, retrieval.context, history)
        else:
            answer = "Não encontrei essa informação na base da FloraStore. Pode detalhar sua dúvida ou confirmar com a loja pelo WhatsApp?"
        return {"answer": answer, "sources": retrieval.sources, "retrieval": {
            "database": "Supabase pgvector", "embedding_model": MODEL_NAME,
            "matched_documents": len(retrieval.sources), "indexed_documents": retrieval.indexed_documents,
        }}

    def close(self):
        self.llm.close()
        self.knowledge.close()


@asynccontextmanager
async def lifespan(app):
    app.state.service = None
    app.state.startup_error = None
    app.state.settings = load_assistant_settings()

    async def initialize():
        try:
            app.state.service = await asyncio.to_thread(AssistantService, app.state.settings)
        except Exception as error:
            app.state.startup_error = type(error).__name__
            status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else ""
            LOGGER.error("Inicialização do RAG falhou (%s %s). Confira o SQL e a chave Secret do Supabase.", type(error).__name__, status)

    task = asyncio.create_task(initialize())
    yield
    await task
    if app.state.service is not None:
        app.state.service.close()


app = FastAPI(title="FloraStore RAG local", lifespan=lifespan, docs_url=None, redoc_url=None)


def authorize(x_flora_key: str = Header(default="")):
    if not compare_digest(x_flora_key, app.state.settings.api_key):
        raise HTTPException(401, "Acesso não autorizado.")


def service():
    if app.state.service is None:
        raise HTTPException(503, "O assistente está iniciando ou precisa de configuração. Confira /health.")
    return app.state.service


@app.get("/health")
def health():
    ready = app.state.service is not None
    return {"ready": ready, "database": "Supabase pgvector", "error": app.state.startup_error,
            "indexed_documents": app.state.service.count if ready else 0}


@app.post("/retrieve", dependencies=[Depends(authorize)])
def retrieve(question: Question):
    try:
        return service().retrieve(question)
    except (httpx.HTTPError, PyMongoError, ValueError) as error:
        LOGGER.warning("Recuperação vetorial falhou (%s)", type(error).__name__)
        raise HTTPException(503, "Não foi possível consultar a base de plantas.") from None


@app.post("/answer", dependencies=[Depends(authorize)])
def answer(request: AnswerRequest):
    try:
        return service().answer(request.request_id)
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as error:
        LOGGER.warning("Geração de resposta falhou (%s)", type(error).__name__)
        raise HTTPException(503, "Não foi possível gerar a resposta. Tente novamente em instantes.") from None
