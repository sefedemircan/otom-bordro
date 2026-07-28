"""Small Supabase REST client for server-side operations."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseError(RuntimeError):
    """Raised when a Supabase REST request fails."""


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SupabaseError(f"Eksik ortam değişkeni: {name}")
    return value


def _encode_filter_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return parse.quote(str(value), safe="-_.~")


@dataclass(slots=True)
class SupabaseClient:
    """Minimal PostgREST / RPC wrapper backed by service role credentials."""

    url: str
    service_key: str

    @classmethod
    def from_env(cls) -> "SupabaseClient":
        return cls(
            url=_require_env("NEXT_PUBLIC_SUPABASE_URL").rstrip("/"),
            service_key=_require_env("SUPABASE_SERVICE_ROLE_KEY"),
        )

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        body: Any | None = None,
        prefer: str | None = None,
    ) -> Any:
        url = f"{self.url}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        payload = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(url, data=payload, method=method, headers=self._headers(prefer=prefer))
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8").strip()
        except error.HTTPError as exc:  # pragma: no cover - network surface
            raw = exc.read().decode("utf-8", errors="replace")
            raise SupabaseError(f"Supabase HTTP {exc.code}: {raw}") from exc
        except error.URLError as exc:  # pragma: no cover - network surface
            raise SupabaseError(f"Supabase erişim hatası: {exc.reason}") from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def insert_row(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        data = self._request(
            "POST",
            f"/rest/v1/{table}",
            body=row,
            prefer="return=representation",
        )
        if not isinstance(data, list) or not data:
            raise SupabaseError(f"{table} insert sonucu beklenmeyen formatta döndü.")
        return data[0]

    def insert_rows(self, table: str, rows: list[dict[str, Any]], *, returning: str = "minimal") -> Any:
        if not rows:
            return []
        return self._request(
            "POST",
            f"/rest/v1/{table}",
            body=rows,
            prefer=f"return={returning}",
        )

    def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, tuple[str, Any]] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, str] = {"select": columns}
        if filters:
            for key, (operator, value) in filters.items():
                query[key] = f"{operator}.{_encode_filter_value(value)}"
        if order:
            query["order"] = order
        if limit is not None:
            query["limit"] = str(limit)
        data = self._request("GET", f"/rest/v1/{table}", query=query)
        if not isinstance(data, list):
            raise SupabaseError(f"{table} select sonucu beklenmeyen formatta döndü.")
        return data

    def select_single(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, tuple[str, Any]] | None = None,
        order: str | None = None,
    ) -> dict[str, Any] | None:
        rows = self.select_rows(table, columns=columns, filters=filters, order=order, limit=1)
        return rows[0] if rows else None

    def update_rows(
        self,
        table: str,
        values: dict[str, Any],
        *,
        filters: dict[str, tuple[str, Any]],
        returning: str = "representation",
    ) -> list[dict[str, Any]]:
        data = self._request(
            "PATCH",
            f"/rest/v1/{table}",
            query={key: f"{operator}.{_encode_filter_value(value)}" for key, (operator, value) in filters.items()},
            body=values,
            prefer=f"return={returning}",
        )
        if data is None:
            return []
        if not isinstance(data, list):
            raise SupabaseError(f"{table} update sonucu beklenmeyen formatta döndü.")
        return data

    def delete_rows(
        self,
        table: str,
        *,
        filters: dict[str, tuple[str, Any]],
        returning: str = "minimal",
    ) -> Any:
        return self._request(
            "DELETE",
            f"/rest/v1/{table}",
            query={key: f"{operator}.{_encode_filter_value(value)}" for key, (operator, value) in filters.items()},
            prefer=f"return={returning}",
        )

    def rpc(self, function_name: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", f"/rest/v1/rpc/{function_name}", body=payload)

