from datetime import date, datetime
import json
import re
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


REQUIRED_OFFER_KEYS = {
    "name",
    "date",
    "start",
    "end",
    "duration_minutes",
    "replacement_type",
}
REPLACEMENT_HINT = re.compile(r"\bзамен|\d{1,2}:\d{2}|\d+\s*минут", re.IGNORECASE)


def should_use_fallback(text: str) -> bool:
    return bool(REPLACEMENT_HINT.search(text))


class GeminiFallback:
    def __init__(self, api_key: str, model: str):
        self._url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )

    def canonicalize(self, text: str, reference_date: date | None) -> str | None:
        if reference_date is None:
            return None
        request_body: dict[str, Any] = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Extract only replacement lessons. Return JSON object with "
                            "an offers array. Every offer must have exactly: name, date "
                            "(YYYY-MM-DD), start (HH:MM), end (HH:MM), duration_minutes "
                            "(integer), replacement_type. Ignore unrelated text and "
                            "struck-out offers. Do not invent data."
                        )
                    }
                ]
            },
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        request = Request(
            self._url,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=20) as response:
                response_body = json.loads(response.read().decode("utf-8"))
            draft = response_body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError, ValueError, OSError, URLError):
            return None
        return parse_gemini_draft(draft, reference_date=reference_date)


def parse_gemini_draft(payload: str, *, reference_date: date) -> str | None:
    try:
        draft = json.loads(payload)
        offers = draft["offers"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(offers, list) or not offers:
        return None

    canonical_lines: list[str] = []
    for offer in offers:
        if not isinstance(offer, dict) or set(offer) != REQUIRED_OFFER_KEYS:
            return None
        name = offer["name"]
        replacement_type = offer["replacement_type"]
        duration = offer["duration_minutes"]
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(replacement_type, str)
            or not isinstance(duration, int)
            or duration <= 0
        ):
            return None
        try:
            parsed_date = datetime.strptime(offer["date"], "%Y-%m-%d").date()
            start = datetime.strptime(offer["start"], "%H:%M").time()
            end = datetime.strptime(offer["end"], "%H:%M").time()
        except (TypeError, ValueError):
            return None
        actual_minutes = int(
            (
                datetime.combine(reference_date, end)
                - datetime.combine(reference_date, start)
            ).total_seconds()
            // 60
        )
        if actual_minutes <= 0:
            return None
        canonical_lines.extend(
            [
                f"{parsed_date:%d.%m.%Y} {replacement_type.strip()}",
                f"{name.strip()} ({duration} минут) {start:%H:%M} — {end:%H:%M}",
            ]
        )
    return "\n".join(canonical_lines)
