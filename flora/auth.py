from dataclasses import dataclass

import httpx


class AccessDenied(Exception):
    pass


@dataclass(frozen=True)
class Admin:
    id: str
    email: str


class SupabaseAuth:
    def __init__(self, url, key):
        self.url = f"{url}/auth/v1"
        self.key = key

    def request(self, method, endpoint, *, token=None, **kwargs):
        headers = {"apikey": self.key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return httpx.request(method, f"{self.url}{endpoint}", headers=headers, timeout=8, **kwargs)

    def sign_in(self, email, password):
        response = self.request(
            "POST", "/token", params={"grant_type": "password"},
            json={"email": email, "password": password},
        )
        if response.status_code in {400, 401, 403, 422}:
            raise AccessDenied("E-mail ou senha inválidos.")
        response.raise_for_status()
        token = response.json()["access_token"]
        self.require_admin(token)
        return token

    def require_admin(self, token):
        response = self.request("GET", "/user", token=token)
        if response.status_code in {400, 401, 403}:
            raise AccessDenied("Sua sessão expirou. Entre novamente.")
        response.raise_for_status()
        user = response.json()
        if (user.get("app_metadata") or {}).get("role") != "admin":
            raise AccessDenied("Sua conta não tem acesso administrativo.")
        return Admin(user["id"], user["email"])

    def sign_out(self, token):
        response = self.request("POST", "/logout", token=token, params={"scope": "local"})
        response.raise_for_status()
