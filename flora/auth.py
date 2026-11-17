import json
import logging
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from time import time

import httpx
from redis.exceptions import RedisError


LOGGER = logging.getLogger(__name__)
ADMIN_CACHE_TTL = 30


class AccessDenied(Exception):
    pass


@dataclass(frozen=True)
class Admin:
    id: str
    email: str


@dataclass(frozen=True)
class AdminSession:
    access_token: str = field(repr=False)
    expires_at: float


class SupabaseAuth:
    def __init__(self, url, key, cache=None):
        self.url = f"{url}/auth/v1"
        self.key = key
        self.cache = cache

    def request(self, method, endpoint, *, token=None, **kwargs):
        headers = {"apikey": self.key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return httpx.request(method, f"{self.url}{endpoint}", headers=headers, timeout=8, **kwargs)

    def sign_in(self, email, password):
        started_at = time()
        response = self.request(
            "POST", "/token", params={"grant_type": "password"},
            json={"email": email, "password": password},
        )
        if response.status_code in {400, 401, 403, 422}:
            raise AccessDenied("E-mail ou senha inválidos.")
        response.raise_for_status()
        data = response.json()
        token = data["access_token"]
        if not isinstance(token, str) or not token:
            raise ValueError("Token de sessão inválido.")
        session = AdminSession(token, started_at + int(data["expires_in"]))
        self._check_expiration(session)
        if data.get("user") is None:
            self.require_admin(session, fresh=True)
        else:
            admin = self._admin_from_user(data["user"])
            self._remember_admin(session, admin)
        return session

    def require_admin(self, session, *, fresh=False):
        self._check_expiration(session)
        if not fresh:
            admin = self._cached_admin(session)
            if admin is not None:
                self._check_expiration(session)
                return admin

        try:
            response = self.request("GET", "/user", token=session.access_token)
            if response.status_code in {400, 401, 403}:
                raise AccessDenied("Sua sessão expirou. Entre novamente.")
            response.raise_for_status()
            self._check_expiration(session)
            admin = self._admin_from_user(response.json())
        except AccessDenied:
            self._forget_admin(session)
            raise

        self._remember_admin(session, admin)
        return admin

    def sign_out(self, session):
        self._forget_admin(session)
        response = self.request("POST", "/logout", token=session.access_token, params={"scope": "local"})
        response.raise_for_status()

    @staticmethod
    def _admin_from_user(user):
        if not isinstance(user, dict):
            raise ValueError("Perfil de usuário inválido.")
        metadata = user.get("app_metadata")
        if not isinstance(metadata, dict) or metadata.get("role") != "admin":
            raise AccessDenied("Sua conta não tem acesso administrativo.")
        user_id, email = user["id"], user["email"]
        if not isinstance(user_id, str) or not isinstance(email, str):
            raise ValueError("Perfil de usuário inválido.")
        return Admin(user_id, email)

    @staticmethod
    def _check_expiration(session):
        if session.expires_at <= time():
            raise AccessDenied("Sua sessão expirou. Entre novamente.")

    def _cache_key(self, session):
        digest = sha256(f"{self.url}\0{session.access_token}".encode()).hexdigest()
        return f"florastore:admin:{digest}"

    def _cached_admin(self, session):
        if self.cache is None:
            return None
        try:
            value = self.cache.get(self._cache_key(session))
            if value is not None:
                admin = Admin(**json.loads(value))
                if isinstance(admin.id, str) and isinstance(admin.email, str):
                    return admin
        except (RedisError, TypeError, ValueError) as error:
            LOGGER.warning("Leitura da sessão no Redis falhou (%s)", type(error).__name__)
        return None

    def _remember_admin(self, session, admin):
        ttl = min(ADMIN_CACHE_TTL, int(session.expires_at - time()))
        if self.cache is None or ttl <= 0:
            return
        try:
            self.cache.set(self._cache_key(session), json.dumps(asdict(admin)), ex=ttl)
        except RedisError as error:
            LOGGER.warning("Cache da sessão no Redis falhou (%s)", type(error).__name__)

    def _forget_admin(self, session):
        if self.cache is None:
            return
        try:
            self.cache.delete(self._cache_key(session))
        except RedisError as error:
            LOGGER.warning("Exclusão da sessão no Redis falhou (%s)", type(error).__name__)
