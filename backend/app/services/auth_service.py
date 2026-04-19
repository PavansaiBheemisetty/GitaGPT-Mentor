import httpx

from app.services.chat_repository import AuthUser


class SupabaseAuthService:
    def __init__(
        self,
        *,
        supabase_url: str | None,
        supabase_anon_key: str | None,
        supabase_service_role_key: str | None,
    ) -> None:
        self._supabase_url = (supabase_url or "").rstrip("/")
        self._supabase_anon_key = supabase_anon_key
        self._supabase_service_role_key = supabase_service_role_key

    @property
    def enabled(self) -> bool:
        return bool(self._supabase_url and (self._supabase_anon_key or self._supabase_service_role_key))

    async def resolve_user(self, access_token: str | None) -> AuthUser | None:
        if not access_token:
            return None
        if not self.enabled:
            return None

        api_key = self._supabase_service_role_key or self._supabase_anon_key
        headers = {
            "Authorization": f"Bearer {access_token}",
            "apikey": str(api_key),
        }

        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(f"{self._supabase_url}/auth/v1/user", headers=headers)

        if response.status_code in (401, 403):
            return None
        response.raise_for_status()
        payload = response.json()
        user_id = payload.get("id")
        email = payload.get("email") or payload.get("user_metadata", {}).get("email")
        if not user_id or not email:
            return None
        return AuthUser(id=str(user_id), email=str(email))
