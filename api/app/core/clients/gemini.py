import json
import re
from typing import Any

import httpx

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiClientError(Exception):
    pass


class GeminiClient:
    def __init__(self, *, api_key: str, model: str = "gemini-2.0-flash", timeout_seconds: float = 12.0):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def generate_text(self, prompt: str, *, temperature: float = 0.2) -> str:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        url = GEMINI_API_URL.format(model=self.model)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, params={"key": self.api_key}, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GeminiClientError(f"Gemini request failed: {exc}") from exc

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise GeminiClientError("Gemini returned empty candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise GeminiClientError("Gemini returned empty content parts")

        text = parts[0].get("text", "")
        if not text:
            raise GeminiClientError("Gemini returned empty text")
        return text

    async def generate_json(self, prompt: str, *, temperature: float = 0.1) -> dict[str, Any]:
        text = await self.generate_text(prompt, temperature=temperature)
        return self._extract_json_object(text)

    async def generate_structured_json(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any],
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """
        Generate structured JSON using Gemini schema-constrained output.

        Example schema:
        {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer"},
                            "score": {"type": "number"},
                        },
                        "required": ["product_id", "score"],
                    },
                }
            },
            "required": ["items"],
        }
        """
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            },
        }
        url = GEMINI_API_URL.format(model=self.model)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, params={"key": self.api_key}, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GeminiClientError(f"Gemini structured request failed: {exc}") from exc

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise GeminiClientError("Gemini returned empty candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise GeminiClientError("Gemini returned empty content parts")

        text = parts[0].get("text", "")
        if not text:
            raise GeminiClientError("Gemini returned empty text")
        return self._extract_json_object(text)

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
        if fenced_match:
            cleaned = fenced_match.group(1).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GeminiClientError(f"Gemini response is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise GeminiClientError("Gemini JSON response must be an object")
        return parsed
