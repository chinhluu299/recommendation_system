"""
_llm_client.py
Singleton OpenAI-compatible client trỏ tới Gemini API.

Gemini hỗ trợ OpenAI-compatible endpoint:
  https://generativelanguage.googleapis.com/v1beta/openai/

Đặt API key vào biến môi trường:
  export GEMINI_API_KEY="your-key-here"
Hoặc tạo file ver2/.env:
  GEMINI_API_KEY=your-key-here

Model mặc định: gemini-2.0-flash (nhanh, rẻ, đủ dùng cho NL2Cypher/Intent)
Đổi sang gemini-1.5-pro nếu cần reasoning phức tạp hơn.
"""

from __future__ import annotations

import os
import time
import re
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# GEMINI_MODEL    = "gemini-3.1-flash-lite-preview"
GEMINI_MODEL    = "gemini-2.5-flash"

# # LM Studio (local) — comment lại, giữ để rollback nhanh nếu cần
# GEMINI_BASE_URL = "http://localhost:1234/v1"
# GEMINI_MODEL    = "gpt-oss-20b"
# GEMINI_MODEL    = "google/gemma-3-4b"

# Retry config cho 429
_MAX_RETRIES   = 5
_BASE_WAIT     = 15   # giây — theo retryDelay từ Gemini response
_MAX_WAIT      = 120  # giây — không chờ quá 2 phút
_MAX_CONTINUES = 3    # số lần nối thêm nếu output bị cắt giữa chừng


def _load_api_key() -> str:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
    except ImportError:
        # Fallback: đọc .env thủ công nếu python-dotenv chưa cài
        if os.path.isfile(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())
    
    random_keys = [f"GEMINI_API_KEY_{i}" for i in range(1, 6)]
    key = next((os.environ.get(k) for k in random_keys if os.environ.get(k)), "")
    if not key:
        raise EnvironmentError(
            "Thiếu GEMINI_API_KEY.\n"
            "Đặt biến môi trường: export GEMINI_API_KEY='your-key'\n"
            "Hoặc tạo file ver2/.env với dòng: GEMINI_API_KEY=your-key"
        )
    return key


# ── Singleton ─────────────────────────────────────────────────────────────────

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url = GEMINI_BASE_URL,
            api_key  = _load_api_key(),
        )
    return _client


def get_model() -> str:
    return GEMINI_MODEL


# ── Rate-limit-aware chat ─────────────────────────────────────────────────────

def _extract_text(resp) -> str:
    """Lấy text an toàn từ OpenAI-compatible response."""
    content = resp.choices[0].message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(text)
        return "".join(parts)
    return str(content or "")


def _create_completion(client: OpenAI, model: str, messages: list[dict], max_tokens: int, temperature: float):
    """
    Thử nhiều biến thể token param để tương thích tốt hơn giữa các endpoint.
    """
    base = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    payloads = [
        {**base, "max_completion_tokens": max_tokens},
        {**base, "max_tokens": max_tokens},
        {**base, "max_tokens": max_tokens, "extra_body": {"max_output_tokens": max_tokens}},
    ]

    last_type_error = None
    for payload in payloads:
        try:
            return client.chat.completions.create(**payload)
        except TypeError as e:
            last_type_error = e
            continue
        except Exception:
            raise

    if last_type_error is not None:
        raise last_type_error
    raise RuntimeError("Không thể gọi chat completion.")


def _request_with_retry(client: OpenAI, model: str, messages: list[dict], max_tokens: int, temperature: float):
    for attempt in range(_MAX_RETRIES):
        try:
            return _create_completion(
                client=client,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            err_str = str(e)
            is_429  = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str

            if not is_429 or attempt == _MAX_RETRIES - 1:
                raise

            wait = _BASE_WAIT * (2 ** attempt)
            m = re.search(r"retry[_\s]in[_\s]([\d.]+)s", err_str, re.IGNORECASE)
            if m:
                wait = float(m.group(1)) + 2

            wait = min(wait, _MAX_WAIT)
            print(f"  [429] Rate limit — chờ {wait:.0f}s rồi thử lại "
                  f"(lần {attempt + 1}/{_MAX_RETRIES}) ...")
            time.sleep(wait)

    raise RuntimeError("Vẫn lỗi 429 sau tất cả các lần retry.")


def chat(messages: list[dict], max_tokens: int = 2048, temperature: float = 0.1) -> str:
    """
    Gọi Gemini với retry khi gặp 429.
    Nếu output bị cắt do giới hạn token, tự nối thêm tối đa _MAX_CONTINUES lần.
    """
    client = get_client()
    model  = get_model()

    resp = _request_with_retry(
        client=client,
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    full_text = _extract_text(resp)
    finish_reason = getattr(resp.choices[0], "finish_reason", None)

    continue_count = 0
    while finish_reason == "length" and continue_count < _MAX_CONTINUES:
        continue_count += 1
        cont_messages = list(messages) + [
            {"role": "assistant", "content": full_text},
            {
                "role": "user",
                "content": "Tiếp tục đúng từ chỗ đang dở, không lặp lại nội dung đã trả lời.",
            },
        ]
        cont_resp = _request_with_retry(
            client=client,
            model=model,
            messages=cont_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        cont_text = _extract_text(cont_resp)
        if cont_text:
            if full_text and not full_text.endswith(("\n", " ")):
                full_text += " "
            full_text += cont_text
        finish_reason = getattr(cont_resp.choices[0], "finish_reason", None)

    return full_text or ""
