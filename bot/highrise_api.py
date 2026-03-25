import asyncio
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode

import aiohttp


class HighriseApiError(Exception):
    pass


class HighriseUserNotFound(HighriseApiError):
    pass


@dataclass
class HighriseProfile:
    user_id: str
    username: str
    bio: str


class HighriseApiClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 VictorBot/1.0 (+https://create.highrise.game/learn/web-api)",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get_json(self, path: str, query: Optional[dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(headers=self._headers(), timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 404:
                    raise HighriseApiError("Highrise Web API returned 404 for this endpoint.")
                if response.status == 403:
                    raise HighriseApiError("Highrise Web API denied the request (403).")
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "5")
                    raise HighriseApiError(f"Highrise Web API rate limited the request. Retry after {retry_after}s.")
                if response.status >= 400:
                    body = await response.text()
                    raise HighriseApiError(f"Highrise Web API error {response.status}: {body[:200]}")
                return await response.json()

    async def find_user_by_username(self, username: str) -> HighriseProfile:
        data = await self._get_json(
            "/users",
            {"username": username, "limit": 10, "sort_order": "asc"},
        )

        users = data.get("users") if isinstance(data, dict) else None
        if not isinstance(users, list):
            raise HighriseApiError("Highrise Web API returned an unexpected users payload.")

        exact_match = next(
            (
                user
                for user in users
                if isinstance(user, dict)
                and str(user.get("username", "")).casefold() == username.casefold()
            ),
            None,
        )
        if not exact_match:
            raise HighriseUserNotFound(f"Highrise user `{username}` was not found.")

        user_id = str(exact_match.get("user_id") or "")
        if not user_id:
            raise HighriseApiError("Highrise Web API did not return a user_id for that profile.")

        return await self.fetch_user_profile(user_id)

    async def fetch_user_profile(self, user_id: str) -> HighriseProfile:
        data = await self._get_json(f"/users/{user_id}")
        user = data.get("user") if isinstance(data, dict) else None
        if not isinstance(user, dict):
            raise HighriseApiError("Highrise Web API returned an unexpected user payload.")

        return HighriseProfile(
            user_id=str(user.get("user_id") or user_id),
            username=str(user.get("username") or ""),
            bio=str(user.get("bio") or ""),
        )

    async def fetch_profile_by_username(self, username: str) -> HighriseProfile:
        return await self.find_user_by_username(username)
