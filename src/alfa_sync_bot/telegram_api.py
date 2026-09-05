import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


class TelegramApiError(RuntimeError):
    pass


class TelegramHttpClient:
    def __init__(self, token: str, *, timeout_seconds: int = 35):
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._timeout_seconds = timeout_seconds

    def _request(self, method: str, payload: dict[str, Any]) -> Any:
        request = Request(
            f"{self._base_url}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as error:
            raise TelegramApiError("Telegram request failed") from error
        if not isinstance(body, dict) or body.get("ok") is not True:
            raise TelegramApiError("Telegram API returned an error")
        return body.get("result")

    def get_updates(self, offset: int | None) -> list[dict]:
        payload: dict[str, Any] = {"timeout": 30, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        result = self._request("getUpdates", payload)
        return result if isinstance(result, list) else []

    def send_message(
        self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        self._request("sendMessage", payload)
